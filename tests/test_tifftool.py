from .datastore import datastore

import tifftools


def test_read_tiff():
    path = datastore.fetch('aperio_jp2k.svs')
    info = tifftools.read_tiff(path)
    assert len(info['ifds']) == 6


# tiff_write
