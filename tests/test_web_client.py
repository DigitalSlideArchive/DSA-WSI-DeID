import os

import pytest
from pytest_girder.web_client import runWebClientTest

from .utilities import provisionBoundServer, provisionDefaultSchemaBoundServer, resetConfig  # noqa


@pytest.mark.plugin('wsi_deid')
@pytest.mark.parametrize('spec', [
    'wsi_deidSpec.js',
])
def testWebClient(boundServer, db, spec, provisionBoundServer, resetConfig):  # noqa
    import wsi_deid.import_export

    wsi_deid.import_export.SCHEMA_FILE_PATH = os.path.join(
        os.path.dirname(wsi_deid.import_export.SCHEMA_FILE_PATH), 'importManifestSchema.test.json')
    spec = os.path.join(os.path.dirname(__file__), '..', 'wsi_deid', 'web_client', 'tests', spec)
    runWebClientTest(boundServer, spec, 15000)


@pytest.mark.plugin('wsi_deid')
@pytest.mark.parametrize('spec', [
    'wsi_deidDefaultSchemaSpec.js',
])
def testDefaultSchemaWebClient(boundServer, db, spec, provisionDefaultSchemaBoundServer, mocker):  # noqa
    def mockStartOcrForUnfiled(*args):
        return None

    mocker.patch('wsi_deid.import_export.startOcrJobForUnfiled', mockStartOcrForUnfiled)
    specPath = os.path.join(
        os.path.dirname(__file__),
        '..', 'wsi_deid',
        'web_client',
        'tests',
        spec,
    )
    runWebClientTest(boundServer, specPath, 15000)
