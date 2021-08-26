import os
import pytest

from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
import girder.utility.config


from .utilities import provisionServer  # noqa


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_workflow(server, provisionServer, user):  # noqa
    from wsi_deid import rest
    from wsi_deid.constants import PluginSettings

    importPath, exportPath = provisionServer
    importFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    importFolder = Folder().load(importFolderId, force=True, exc=True)
    finishedFolderId = Setting().get(PluginSettings.HUI_FINISHED_FOLDER)
    finishedFolder = Folder().load(finishedFolderId, force=True, exc=True)
    assert len(list(Folder().fileList(importFolder))) == 0
    rest.ingestData(user, False)
    assert len(list(Folder().fileList(importFolder))) == 3
    for _, file in Folder().fileList(importFolder, user, data=False):
        itemId = file['itemId']
        item = Item().load(itemId, user=user)
        rest.process_item(item, user)
        item = Item().load(itemId, user=user)
        rest.move_item(item, user, PluginSettings.HUI_FINISHED_FOLDER)
    assert len(list(Folder().fileList(importFolder))) == 0
    assert len(list(Folder().fileList(finishedFolder))) == 3
    rest.exportData(user, False)
    assert len(os.listdir(exportPath)) == 3


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_workflow_with_options(server, provisionServer, user):  # noqa
    from wsi_deid import rest
    from wsi_deid.constants import PluginSettings
    import wsi_deid.config

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
    assert len(list(Folder().fileList(importFolder))) == 0
    rest.ingestData(user, False)
    assert len(list(Folder().fileList(importFolder))) == 3
    for _, file in Folder().fileList(importFolder, user, data=False):
        itemId = file['itemId']
        item = Item().load(itemId, user=user)
        rest.process_item(item, user)
        item = Item().load(itemId, user=user)
        rest.move_item(item, user, PluginSettings.HUI_FINISHED_FOLDER)
    assert len(list(Folder().fileList(importFolder))) == 0
    assert len(list(Folder().fileList(finishedFolder))) == 3
    rest.exportData(user, False)
    assert len(os.listdir(exportPath)) == 3
