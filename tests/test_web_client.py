import os
import pytest
from pytest_girder.web_client import runWebClientTest
import sys


@pytest.mark.plugin('wsi_deid')
@pytest.mark.parametrize('spec', (
    'wsi_deidSpec.js',
))
def testWebClient(boundServer, fsAssetstore, db, spec):
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'devops', 'wsi_deid'))
    import provision  # noqa
    provision.provision()
    del sys.path[-1]

    spec = os.path.join(os.path.dirname(__file__), '..', 'wsi_deid', 'web_client', 'tests', spec)
    runWebClientTest(boundServer, spec, 15000)
