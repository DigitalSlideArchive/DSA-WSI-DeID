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
from nci_seer.constants import PluginSettings

# This loads plugins, allowing setting validation
configureServer()

# If there is are no users, create an admin user
if User().findOne() is None:
    User().createUser('admin', 'password', 'Admin', 'Admin', 'admin@nowhere.nil')
adminUser = User().findOne({'admin': True})

# Set branding
Setting().set('core.brand_name', 'Digital Slide Archive')
Setting().set('homepage.markdown', """
# Digital Slide Archive
---
## NCI SEER Pediatic WSI Pilot

Welcome to the **Digital Slide Archive**.

Developers who want to use the Girder REST API should check out the
[interactive web API docs](api/v1).
""")

# Make sure we have an assetstore
if Assetstore().findOne() is None:
    Assetstore().createFilesystemAssetstore('Assetstore', '/assetstore')

# Make sure we have the SEER collection
if Collection().findOne({'name': 'SEER'}) is None:
    Collection().createCollection('SEER', adminUser)
seerCollection = Collection().findOne({'name': 'SEER'})
# Create default folders.  Set the settings to those folders
folders = {
    PluginSettings.HUI_INGEST_FOLDER: ('Ingest', False),
    PluginSettings.HUI_QUARANTINE_FOLDER: ('Quarantine', False),
    PluginSettings.HUI_PROCESSED_FOLDER: ('Audited', False),
    PluginSettings.HUI_REJECTED_FOLDER: ('Rejected', False),
    PluginSettings.HUI_ORIGINAL_FOLDER: ('Original', False),
    PluginSettings.HUI_FINISHED_FOLDER: ('Finished', True),
}
for settingKey, (folderName, public) in folders.items():
    if not Setting().get(settingKey):
        folder = Folder().createFolder(
            seerCollection, folderName, parentType='collection',
            public=public, creator=adminUser)
        Setting().set(settingKey, str(folder['_id']))
Setting().set(liSettings.LARGE_IMAGE_SHOW_EXTRA_ADMIN, '{"images": ["label", "macro"]}')
Setting().set(liSettings.LARGE_IMAGE_SHOW_EXTRA, '{"images": ["label", "macro"]}')
Setting().set(liSettings.LARGE_IMAGE_SHOW_ITEM_EXTRA_ADMIN,
              '{"metadata": ["tile", "internal"], "images": ["label", "macro", "*"]}')
Setting().set(liSettings.LARGE_IMAGE_SHOW_ITEM_EXTRA,
              '{"metadata": ["tile", "internal"], "images": ["label", "macro", "*"]}')
