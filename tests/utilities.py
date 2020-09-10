import os
import pytest
import shutil
import sys

from girder.models.setting import Setting

from nci_seer.constants import PluginSettings

from .datastore import datastore


@pytest.fixture
def provisionServer(server, admin, fsAssetstore, tmp_path):
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'devops', 'nciseer'))
    import provision  # noqa
    provision.provision()
    del sys.path[-1]

    importPath = tmp_path / 'import'
    os.makedirs(importPath, exist_ok=True)
    exportPath = tmp_path / 'export'
    os.makedirs(exportPath, exist_ok=True)
    Setting().set(PluginSettings.NCISEER_IMPORT_PATH, str(importPath))
    Setting().set(PluginSettings.NCISEER_EXPORT_PATH, str(exportPath))
    for filename in {'aperio_jp2k.svs', 'hamamatsu.ndpi', 'philips.ptif'}:
        path = datastore.fetch(filename)
        shutil.copy(path, str(importPath / filename))
    dataPath = os.path.join(os.path.dirname(__file__), 'data')
    for filename in {'deidUpload.csv'}:
        path = os.path.join(dataPath, filename)
        shutil.copy(path, importPath / filename)
    yield importPath, exportPath
