import pytest
from girder.plugin import loadedPlugins


@pytest.mark.plugin('wsi_deid')
def test_import(server):
    assert 'wsi_deid' in loadedPlugins()
