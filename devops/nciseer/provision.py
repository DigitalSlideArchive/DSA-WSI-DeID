# This ensures that:
#  - Worker settings are correct
#  - there is at least one admin user
#  - there is a default task folder
#  - there is at least one assetstore

from girder.models.assetstore import Assetstore
from girder.models.collection import Collection
from girder.models.folder import Folder
from girder.models.setting import Setting
from girder.models.user import User
from girder.utility.server import configureServer

from girder_large_image.constants import PluginSettings as liSettings
import nci_seer
from nci_seer.constants import PluginSettings

# This loads plugins, allowing setting validation
configureServer()

# If there is are no users, create an admin user
if User().findOne() is None:
    User().createUser('admin', 'password', 'Admin', 'Admin', 'admin@nowhere.nil')
adminUser = User().findOne({'admin': True})

# Set branding
Setting().set('core.brand_name', 'SEER DSA')
Setting().set('homepage.markdown', """
# SEER Digital Slide Archive
---
## NCI SEER Pediatic WSI Pilot

Welcome to the **SEER Digital Slide Archive**.

Developers who want to use the Girder REST API should check out the
[interactive web API docs](api/v1).

NCI SEER Version: %s
""" % (nci_seer.__version__))

# Make sure we have an assetstore
if Assetstore().findOne() is None:
    Assetstore().createFilesystemAssetstore('Assetstore', '/assetstore')

# Make sure we have the SEER collection
if Collection().findOne({'name': 'SEER'}) is None:
    Collection().createCollection('SEER', adminUser)
seerCollection = Collection().findOne({'name': 'SEER'})
# Create default folders.  Set the settings to those folders
folders = {
    PluginSettings.HUI_INGEST_FOLDER: ('AvailableToProcess', True),
    PluginSettings.HUI_QUARANTINE_FOLDER: ('Quarantined', True),
    PluginSettings.HUI_PROCESSED_FOLDER: ('Redacted', True),
    PluginSettings.HUI_REJECTED_FOLDER: ('Rejected', True),
    PluginSettings.HUI_ORIGINAL_FOLDER: ('Original', True),
    PluginSettings.HUI_FINISHED_FOLDER: ('Approved', True),
}
for settingKey, (folderName, public) in folders.items():
    folder = None
    folderId = Setting().get(settingKey)
    if folderId:
        folder = Folder().load(folderId, force=True)
    if not folder:
        folder = Folder().createFolder(
            seerCollection, folderName, parentType='collection',
            public=public, creator=adminUser, reuseExisting=True)
        Setting().set(settingKey, str(folder['_id']))
    elif folder['name'] != folderName or folder['public'] != public:
        folder['name'] = folderName
        folder['public'] = public
        Folder().save(folder)
# Set default import/export paths
if not Setting().get(PluginSettings.NCISEER_IMPORT_PATH):
    Setting().set(PluginSettings.NCISEER_IMPORT_PATH, '/import')
if not Setting().get(PluginSettings.NCISEER_EXPORT_PATH):
    Setting().set(PluginSettings.NCISEER_EXPORT_PATH, '/export')
# Show label and macro images, plus tile and internal metadata for all users
Setting().set(liSettings.LARGE_IMAGE_SHOW_EXTRA_ADMIN, '{"images": ["label", "macro"]}')
Setting().set(liSettings.LARGE_IMAGE_SHOW_EXTRA, '{"images": ["label", "macro"]}')
Setting().set(liSettings.LARGE_IMAGE_SHOW_ITEM_EXTRA_ADMIN,
              '{"metadata": ["tile", "internal"], "images": ["label", "macro", "*"]}')
Setting().set(liSettings.LARGE_IMAGE_SHOW_ITEM_EXTRA,
              '{"metadata": ["tile", "internal"], "images": ["label", "macro", "*"]}')
