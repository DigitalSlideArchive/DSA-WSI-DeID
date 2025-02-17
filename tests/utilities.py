import os
import shutil
import sys

import pytest
from girder.models.setting import Setting

from wsi_deid.constants import PluginSettings

from .datastore import datastore


@pytest.fixture
def provisionServer(server, admin, fsAssetstore, tmp_path):
    return _provisionServer(tmp_path)


@pytest.fixture
def provisionBoundServer(boundServer, admin, fsAssetstore, tmp_path):
    return _provisionServer(tmp_path)


@pytest.fixture
def provisionDefaultSchemaServer(server, admin, fsAssetstore, tmp_path):
    return _provisionDefaultSchemaServer(tmp_path)


@pytest.fixture
def provisionDefaultSchemaBoundServer(boundServer, admin, fsAssetstore, tmp_path):
    return _provisionDefaultSchemaServer(tmp_path)


def _provisionServer(tmp_path):
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'devops', 'wsi_deid'))
    import provision  # noqa
    provision.provision()
    del sys.path[-1]

    importPath = tmp_path / 'import'
    os.makedirs(importPath, exist_ok=True)
    exportPath = tmp_path / 'export'
    os.makedirs(exportPath, exist_ok=True)
    Setting().set(PluginSettings.WSI_DEID_IMPORT_PATH, str(importPath))
    Setting().set(PluginSettings.WSI_DEID_EXPORT_PATH, str(exportPath))
    for filename in {'aperio_jp2k.svs', 'hamamatsu.ndpi', 'philips.ptif'}:
        path = datastore.fetch(filename)
        shutil.copy(path, str(importPath / filename))
    dataPath = os.path.join(os.path.dirname(__file__), 'data')
    for filename in {'deidUpload.csv'}:
        path = os.path.join(dataPath, filename)
        shutil.copy(path, importPath / filename)
    return importPath, exportPath


@pytest.fixture
def resetConfig():
    import girder.utility.config

    import wsi_deid.config

    # Use default wsi_deid config for tests
    config = girder.utility.config.getConfig()
    config[wsi_deid.config.CONFIG_SECTION] = {}


def _provisionDefaultSchemaServer(tmp_path):
    import girder.utility.config  # noqa

    import wsi_deid.config  # noqa
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'devops', 'wsi_deid'))
    config = girder.utility.config.getConfig()
    config[wsi_deid.config.CONFIG_SECTION] = {
        'import_text_association_columns': [
            'SurgPathNum',
            'First_Name',
            'Last_Name',
            'Date_of_Birth_mmddyyyy',
        ],
    }
    import provision  # noqa
    provision.provision()
    del sys.path[-1]

    importPath = tmp_path / 'import'
    os.makedirs(importPath, exist_ok=True)
    exportPath = tmp_path / 'export'
    os.makedirs(exportPath, exist_ok=True)
    # unfiledPath = tmp_path / 'unfiled'
    # os.makedirs(unfiledPath, exist_ok=True)
    Setting().set(PluginSettings.WSI_DEID_IMPORT_PATH, str(importPath))
    Setting().set(PluginSettings.WSI_DEID_EXPORT_PATH, str(exportPath))
    Setting().set(PluginSettings.WSI_DEID_DB_API_KEY, 'api-key')
    Setting().set(PluginSettings.WSI_DEID_DB_API_URL, 'http://localhost:8080/matching/wsi')
    # Setting().set(PluginSettings.WSI_DEID_UNFILED_FOLDER, str(unfiledPath))
    for filename in {
        'SEER_Mouse_1_17158539.svs',
        'SEER_Mouse_1_17158540.svs',
        'SEER_Mouse_1_17158541.svs',
        'SEER_Mouse_1_17158542.svs',
        'SEER_Mouse_1_17158543.svs',
    }:
        path = datastore.fetch(filename)
        shutil.copy(path, str(importPath / filename))
    dataPath = os.path.join(os.path.dirname(__file__), 'data')
    for filename in {'default_schema_deidUpload.csv'}:
        path = os.path.join(dataPath, filename)
        shutil.copy(path, importPath / filename)
    return importPath, exportPath
