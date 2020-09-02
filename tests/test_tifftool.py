from .datastore import datastore

from nci_seer import tifftools


def test_read_tiff():
    path = datastore.fetch('aperio_jp2k.svs')
    info = tifftools.read_tiff(path)
    assert len(info['ifds']) == 6


# tiff_write
# name_to_datatype
# name_to_tag
