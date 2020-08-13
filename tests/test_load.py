import pytest

from girder.plugin import loadedPlugins


@pytest.mark.plugin('nci_seer')
def test_import(server):
    assert 'nci_seer' in loadedPlugins()
