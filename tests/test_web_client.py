import os
import pytest
from pytest_girder.web_client import runWebClientTest
import sys


@pytest.mark.plugin('nci_seer')
@pytest.mark.parametrize('spec', (
    'nciseerSpec.js',
))
def testWebClient(boundServer, fsAssetstore, db, spec):

    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'devops', 'nciseer'))
    import provision  # noqa

    spec = os.path.join(os.path.dirname(__file__), '..', 'nci_seer', 'web_client', 'tests', spec)
    runWebClientTest(boundServer, spec, 15000)
