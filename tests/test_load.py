import pytest

from girder.plugin import loadedPlugins


@pytest.mark.plugin('dsa_seer')
def test_import(server):
    assert 'dsa_seer' in loadedPlugins()
