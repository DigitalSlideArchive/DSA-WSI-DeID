import os

from girder.models.assetstore import Assetstore
from girder.models.collection import Collection
from girder.models.folder import Folder
from girder.models.setting import Setting
from girder.models.user import User
from girder.utility.server import configureServer

from girder_large_image.constants import PluginSettings as liSettings


def provision():
    import wsi_deid
    from wsi_deid.constants import PluginSettings

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
    }
    for settingKey, (folderName, public) in folders.items():
        folder = None
        folderId = Setting().get(settingKey)
        if folderId:
            folder = Folder().load(folderId, force=True)
        if not folder:
            folder = Folder().createFolder(
                wsi_deidCollection, folderName, parentType='collection',
                public=public, creator=adminUser, reuseExisting=True)
            Setting().set(settingKey, str(folder['_id']))
        elif folder['name'] != folderName or folder['public'] != public:
            folder['name'] = folderName
            folder['public'] = public
            Folder().save(folder)
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
    # Set default SFTP/Export mode
    if not Setting().get(PluginSettings.WSI_DEID_SFTP_MODE):
        Setting().set(PluginSettings.WSI_DEID_SFTP_MODE, 'local')

if __name__ == '__main__':
    # This loads plugins, allowing setting validation
    configureServer()
    provision()
