import os

import girder.utility.config
import pytest
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting

from .utilities import provisionDefaultSchemaServer, provisionServer  # noqa


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_workflow(server, provisionServer, user):  # noqa
    import wsi_deid.import_export
    from wsi_deid import rest
    from wsi_deid.constants import PluginSettings

    wsi_deid.import_export.SCHEMA_FILE_PATH = os.path.join(
        os.path.dirname(wsi_deid.import_export.SCHEMA_FILE_PATH), 'importManifestSchema.test.json')
    importPath, exportPath = provisionServer
    importFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    importFolder = Folder().load(importFolderId, force=True, exc=True)
    finishedFolderId = Setting().get(PluginSettings.HUI_FINISHED_FOLDER)
    finishedFolder = Folder().load(finishedFolderId, force=True, exc=True)
    unfiledFolderId = Setting().get(PluginSettings.WSI_DEID_UNFILED_FOLDER)
    unfiledFolder = Folder().load(unfiledFolderId, force=True, exc=True)
    assert len(list(Folder().fileList(importFolder))) == 0
    rest.ingestData(user, False)
    assert len(list(Folder().fileList(importFolder))) == 4
    item = list(Folder().childItems(unfiledFolder))[0]
    rest.process.refile_image(
        item, user, '1234AB567003_01', '1234AB567003_01_06', item.get('wsi_uploadInfo'))
    assert len(list(Folder().fileList(importFolder))) == 14
    for _, file in Folder().fileList(importFolder, user, data=False):
        itemId = file['itemId']
        item = Item().load(itemId, user=user)
        rest.process_item(item, user)
        item = Item().load(itemId, user=user)
        rest.move_item(item, user, PluginSettings.HUI_FINISHED_FOLDER)
    assert len(list(Folder().fileList(importFolder))) == 0
    assert len(list(Folder().fileList(finishedFolder))) == 14
    rest.exportData(user, False)
    assert len(os.listdir(exportPath)) == 5


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_workflow_with_options(server, provisionServer, user):  # noqa
    import wsi_deid.config
    import wsi_deid.import_export
    from wsi_deid import rest
    from wsi_deid.constants import PluginSettings

    wsi_deid.import_export.SCHEMA_FILE_PATH = os.path.join(
        os.path.dirname(wsi_deid.import_export.SCHEMA_FILE_PATH), 'importManifestSchema.test.json')
    config = girder.utility.config.getConfig()
    config[wsi_deid.config.CONFIG_SECTION] = {
        'redact_macro_square': True,
        'always_redact_label': True,
    }

    importPath, exportPath = provisionServer
    importFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    importFolder = Folder().load(importFolderId, force=True, exc=True)
    finishedFolderId = Setting().get(PluginSettings.HUI_FINISHED_FOLDER)
    finishedFolder = Folder().load(finishedFolderId, force=True, exc=True)
    unfiledFolderId = Setting().get(PluginSettings.WSI_DEID_UNFILED_FOLDER)
    unfiledFolder = Folder().load(unfiledFolderId, force=True, exc=True)
    assert len(list(Folder().fileList(importFolder))) == 0
    rest.ingestData(user, False)
    assert len(list(Folder().fileList(importFolder))) == 4
    item = list(Folder().childItems(unfiledFolder))[0]
    rest.process.refile_image(
        item, user, '1234AB567003_01', '1234AB567003_01_06', item.get('wsi_uploadInfo'))
    assert len(list(Folder().fileList(importFolder))) == 14
    for _, file in Folder().fileList(importFolder, user, data=False):
        itemId = file['itemId']
        item = Item().load(itemId, user=user)
        rest.process_item(item, user)
        item = Item().load(itemId, user=user)
        rest.move_item(item, user, PluginSettings.HUI_FINISHED_FOLDER)
    assert len(list(Folder().fileList(importFolder))) == 0
    assert len(list(Folder().fileList(finishedFolder))) == 14
    rest.exportData(user, False)
    assert len(os.listdir(exportPath)) == 5


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_workflow_with_default_schema(server, provisionDefaultSchemaServer, user, mocker):  # noqa
    import wsi_deid.import_export
    from wsi_deid import rest
    from wsi_deid.constants import PluginSettings

    def mockStartOcrForUnfiled(*args):
        return None

    mocker.patch('wsi_deid.import_export.startOcrJobForUnfiled', mockStartOcrForUnfiled)

    config = girder.utility.config.getConfig()
    config[wsi_deid.config.CONFIG_SECTION] = {
        'import_text_association_columns': [
            'SurgPathNum',
            'First_Name',
            'Last_Name',
            'Date_of_Birth_mmddyyyy',
        ],
    }

    unfiledFolderId = Setting().get(PluginSettings.WSI_DEID_UNFILED_FOLDER)
    unfiledFolder = Folder().load(unfiledFolderId, force=True, exc=True)
    assert len(list(Folder().fileList(unfiledFolder))) == 0
    rest.ingestData(user, False)
    assert len(list(Folder().fileList(unfiledFolder, user, data=False))) == 5
