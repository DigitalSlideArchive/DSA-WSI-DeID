import os
import sys

import girder.utility.config
from girder.models import getDbConnection
from girder.models.assetstore import Assetstore
from girder.models.collection import Collection
from girder.models.folder import Folder
from girder.models.setting import Setting
from girder.models.upload import Upload
from girder.models.user import User
from girder.utility.server import configureServer
from girder_large_image.constants import PluginSettings as liSettings


def provision():  # noqa
    import wsi_deid
    from wsi_deid.constants import PluginSettings
    print('Provisioning')
    # If there is are no users, create an admin user
    if User().findOne() is None:
        User().createUser('admin', 'password', 'Admin', 'Admin', 'admin@nowhere.nil')
    adminUser = User().findOne({'admin': True})

    # Set branding
    Setting().set('core.brand_name', 'WSI DeID')
    homepagePath = os.path.join(os.path.dirname(__file__), 'homepage.md')
    homepage = open(homepagePath).read() + ("""
---
WSI DeID Version: %s
    """ % (wsi_deid.__version__))
    Setting().set('homepage.markdown', homepage)
    # Make sure we have an assetstore
    if Assetstore().findOne() is None:
        Assetstore().createFilesystemAssetstore('Assetstore', '/assetstore')

    # Make sure we have the WSI DeID collection
    collName = 'WSI DeID'
    if Collection().findOne({'lowerName': collName.lower()}) is None:
        Collection().createCollection(collName, adminUser)
    wsi_deidCollection = Collection().findOne({'lowerName': collName.lower()})
    if wsi_deidCollection['name'] != collName:
        wsi_deidCollection['name'] = collName
        wsi_deidCollection = Collection().save(wsi_deidCollection)
    # Create default folders.  Set the settings to those folders
    folders = {
        PluginSettings.HUI_INGEST_FOLDER: ('AvailableToProcess', True),
        PluginSettings.HUI_QUARANTINE_FOLDER: ('Quarantined', True),
        PluginSettings.HUI_PROCESSED_FOLDER: ('Redacted', True),
        PluginSettings.HUI_REJECTED_FOLDER: ('Rejected', True),
        PluginSettings.HUI_ORIGINAL_FOLDER: ('Original', True),
        PluginSettings.HUI_FINISHED_FOLDER: ('Approved', True),
        PluginSettings.HUI_REPORTS_FOLDER: ('Reports', True),
        PluginSettings.WSI_DEID_SCHEMA_FOLDER: ('Schema', True),
    }
    configDict = girder.utility.config.getConfig().get('wsi_deid', {})
    matchTextFields = configDict.get('import_text_association_columns', [])
    print('matchTextFields', matchTextFields)
    if matchTextFields:
        # if this setting is not an empty list, then we will provision the Unfiled folder,
        # since it is likely we will need to support a schema with no file names
        folders[PluginSettings.WSI_DEID_UNFILED_FOLDER] = ('Unfiled', True)
    for settingKey, (folderName, public) in folders.items():
        print('Ensuring folder %s exists' % folderName)
        folder = None
        folderId = Setting().get(settingKey)
        if folderId:
            folder = Folder().load(folderId, force=True)
        if not folder:
            if settingKey == 'wsi_deid.schema_folder':
                folder = Folder().createFolder(
                    wsi_deidCollection, folderName, parentType='collection',
                    public=public, creator=adminUser, reuseExisting=True)
                Folder().createFolder(
                    folder, 'Disabled', parentType='folder',
                    public=public, creator=adminUser, reuseExisting=True,
                )
                Upload().uploadFromFile(
                    open('wsi_deid/schema/importManifestSchema.json', 'rb'),
                    os.path.getsize('wsi_deid/schema/importManifestSchema.json'),
                    name='importManifestSchema.json',
                    parentType='folder',
                    parent=folder,
                    user=adminUser)
            else:
                folder = Folder().createFolder(
                    wsi_deidCollection, folderName, parentType='collection',
                    public=public, creator=adminUser, reuseExisting=True)

            Setting().set(settingKey, str(folder['_id']))
        elif folder['name'] != folderName or folder['public'] != public:
            folder['name'] = folderName
            folder['public'] = public
            Folder().save(folder)
    if os.environ.get('PROVISION') == 'tasks':
        taskCollName = 'Tasks'
        if Collection().findOne({'lowerName': taskCollName.lower()}) is None:
            Collection().createCollection(taskCollName, adminUser)
        taskCollection = Collection().findOne({'lowerName': taskCollName.lower()})
        taskFolder = Folder().createFolder(
            taskCollection, 'Slicer CLI Web Tasks', parentType='collection',
            public=True, creator=adminUser, reuseExisting=True)
        Setting().set('slicer_cli_web.task_folder', str(taskFolder['_id']))
        Setting().set('worker.broker', 'amqp://guest:guest@rabbitmq')
        Setting().set('worker.backend', 'rpc://guest:guest@rabbitmq')
        Setting().set('worker.api_url', 'http://girder:8080/api/v1')
        try:
            os.chmod('/var/run/docker.sock', 0o777)
        except Exception:
            pass
    # Set default import/export paths
    if not Setting().get(PluginSettings.WSI_DEID_IMPORT_PATH):
        Setting().set(PluginSettings.WSI_DEID_IMPORT_PATH, '/import')
    if not Setting().get(PluginSettings.WSI_DEID_EXPORT_PATH):
        Setting().set(PluginSettings.WSI_DEID_EXPORT_PATH, '/export')
    # Show label and macro images, plus tile and internal metadata for all users
    Setting().set(liSettings.LARGE_IMAGE_SHOW_EXTRA_ADMIN, '{"images": ["label", "macro"]}')
    Setting().set(liSettings.LARGE_IMAGE_SHOW_EXTRA, '{"images": ["label", "macro"]}')
    Setting().set(liSettings.LARGE_IMAGE_SHOW_ITEM_EXTRA_ADMIN,
                  '{"metadata": ["tile", "internal"], "images": ["label", "macro", "*"]}')
    Setting().set(liSettings.LARGE_IMAGE_SHOW_ITEM_EXTRA,
                  '{"metadata": ["tile", "internal"], "images": ["label", "macro", "*"]}')
    Setting().set(liSettings.LARGE_IMAGE_MERGE_DICOM, True)
    # Set default SFTP/Export mode
    if not Setting().get(PluginSettings.WSI_DEID_SFTP_MODE):
        Setting().set(PluginSettings.WSI_DEID_SFTP_MODE, 'local')
    # Mongo compatibility version
    try:
        db = getDbConnection()
    except Exception:
        print('Could not connect to mongo.')
    try:
        # In mongo shell, this is functionally
        #   db.adminCommand({setFeatureCompatibilityVersion:
        #     db.version().split('.').slice(0, 2).join('.')})
        db.admin.command({'setFeatureCompatibilityVersion': '.'.join(
            db.server_info()['version'].split('.')[:2]), 'confirm': True})
    except Exception:
        try:
            db.admin.command({'setFeatureCompatibilityVersion': '.'.join(
                db.server_info()['version'].split('.')[:2])})
        except Exception:
            print('Could not set mongo feature compatibility version.')


if __name__ == '__main__':
    if os.environ.get('PROVISION') == 'worker':
        try:
            os.chmod('/var/run/docker.sock', 0o777)
        except Exception:
            pass
        sys.exit(0)
    # This loads plugins, allowing setting validation
    configureServer()
    provision()
