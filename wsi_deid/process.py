import base64
import copy
import io
import math
import os
import re
import subprocess
import threading
import time
import xml.etree.ElementTree

import numpy
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageOps
import pyvips
import tifftools
from girder import logger
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder_large_image.models.image_item import ImageItem
from large_image.tilesource import dictToEtree

from . import config
from .constants import PluginSettings, TokenOnlyPrefix

OCRLock = threading.Lock()
OCRReader = None


def get_reader():
    global OCRReader
    with OCRLock:
        if OCRReader is None:
            import easyocr

            OCRReader = easyocr.Reader(['en'], verbose=False)
        return OCRReader


def generate_system_redaction_list_entry(newValue):
    """Create an entry for the redaction list for a redaction performed by the system."""
    return {
        'value': newValue,
        'reason': 'System Redacted',
    }


def get_redact_list(item):
    """
    Get the redaction list, ensuring that the images and metadata
    dictionaries exist.

    :param item: a Girder item.
    :returns: the redactList object.
    """
    redactList = item.get('meta', {}).get('redactList', {})
    for cat in {'images', 'metadata'}:
        redactList.setdefault(cat, {})
        for key in list(redactList[cat]):
            if not isinstance(redactList[cat][key], dict):
                redactList[cat][key] = {'value': redactList[cat][key]}
    return redactList


def get_generated_title(item):
    """
    Given an item with possible metadata and redactions, return the desired
    title.

    :param item: a Girder item.
    :returns: a title.
    """
    redactList = get_redact_list(item)
    title = os.path.splitext(item['name'])[0]
    for key in {
            'internal;openslide;aperio.Title',
            'internal;openslide;hamamatsu.Reference',
            'internal;xml;PIIM_DP_SCANNER_OPERATOR_ID',
            'internal;xml;PIM_DP_UFS_BARCODE'}:
        if redactList['metadata'].get(key):
            return redactList['metadata'].get(key)['value']
    # TODO: Pull from appropriate 'meta' if not otherwise present
    return title


def determine_format(tileSource):
    """
    Given a tile source, return the vendor format.

    :param tileSource: a large_image tile source.
    :returns: the vendor or None if unknown.
    """
    metadata = tileSource.getInternalMetadata() or {}
    if tileSource.name == 'openslide':
        if metadata.get('openslide', {}).get('openslide.vendor') in ('aperio', 'hamamatsu'):
            return metadata['openslide']['openslide.vendor']
    if 'xml' in metadata and any(k.startswith('PIM_DP_') for k in metadata['xml']):
        return 'philips'
    return None


def get_standard_redactions(item, title):
    """
    Produce a standardize redaction list based on format.

    :param item: a Girder item.
    :param title: the new title of the image.
    :returns: a redactList.
    """
    tileSource = ImageItem().tileSource(item)
    sourcePath = tileSource._getLargeImagePath()
    tiffinfo = tifftools.read_tiff(sourcePath)
    ifds = tiffinfo['ifds']
    func = None
    format = determine_format(tileSource)
    if format is not None:
        func = globals().get('get_standard_redactions_format_' + format)
    if func:
        redactList = func(item, tileSource, tiffinfo, title)
    else:
        redactList = {
            'images': {},
            'metadata': {},
        }
    for key in {'DateTime'}:
        tag = tifftools.Tag[key].value
        if tag in ifds[0]['tags']:
            value = ifds[0]['tags'][tag]['data']
            if len(value) >= 10:
                value = value[:5] + '01:01' + value[10:]
            else:
                value = None
            redactList['metadata']['internal;openslide;tiff.%s' % key] = (
                generate_system_redaction_list_entry(value)
            )
    # Make, Model, Software?
    for key in {'Copyright', 'HostComputer'}:
        tag = tifftools.Tag[key].value
        if tag in ifds[0]['tags']:
            redactList['metadata']['internal;openslide;tiff.%s' % key] = {
                'value': None, 'automatic': True}
    return redactList


def get_standard_redactions_format_aperio(item, tileSource, tiffinfo, title):
    metadata = tileSource.getInternalMetadata() or {}
    title_redaction_list_entry = generate_system_redaction_list_entry(title)
    redactList = {
        'images': {},
        'metadata': {
            'internal;openslide;aperio.Filename': title_redaction_list_entry,
            'internal;openslide;aperio.Title': title_redaction_list_entry,
            'internal;openslide;tiff.Software': generate_system_redaction_list_entry(
                get_deid_field(item, metadata.get('openslide', {}).get('tiff.Software'))
            ),
        },
    }
    if metadata['openslide'].get('aperio.Date'):
        redactList['metadata']['internal;openslide;aperio.Date'] = (
            generate_system_redaction_list_entry(
                '01/01/' + metadata['openslide']['aperio.Date'][6:]
            )
        )
    return redactList


def get_standard_redactions_format_hamamatsu(item, tileSource, tiffinfo, title):
    metadata = tileSource.getInternalMetadata() or {}
    redactList = {
        'images': {},
        'metadata': {
            'internal;openslide;hamamatsu.Reference': generate_system_redaction_list_entry(title),
            'internal;openslide;tiff.Software': generate_system_redaction_list_entry(
                get_deid_field(item, metadata.get('openslide', {}).get('tiff.Software'))
            )
        },
    }
    for key in {'Created', 'Updated'}:
        if metadata['openslide'].get('hamamatsu.%s' % key):
            redactList['metadata']['internal;openslide;hamamatsu.%s' % key] = \
                metadata['openslide']['hamamatsu.%s' % key][:4] + '/01/01'
    return redactList


def get_standard_redactions_format_philips(item, tileSource, tiffinfo, title):
    metadata = tileSource.getInternalMetadata() or {}
    redactList = {
        'images': {},
        'metadata': {
            'internal;xml;PIIM_DP_SCANNER_OPERATOR_ID': generate_system_redaction_list_entry(title),
            'internal;xml;PIM_DP_UFS_BARCODE': generate_system_redaction_list_entry(title),
            'internal;tiff;software': generate_system_redaction_list_entry(
                get_deid_field(item, metadata.get('tiff', {}).get('software'))
            ),
        },
    }
    for key in {'DICOM_DATE_OF_LAST_CALIBRATION'}:
        if metadata['xml'].get(key):
            value = metadata['xml'][key].strip('"')
            if len(value) < 8:
                value = None
            else:
                value = value[:4] + '0101'
            redactList['metadata']['internal;xml;%s' % key] = (
                generate_system_redaction_list_entry(value)
            )
    for key in {'DICOM_ACQUISITION_DATETIME'}:
        if metadata['xml'].get(key):
            value = metadata['xml'][key].strip('"')
            if len(value) < 8:
                value = None
            else:
                value = value[:4] + '0101' + value[8:]
            redactList['metadata']['internal;xml;%s' % key] = (
                generate_system_redaction_list_entry(value)
            )
    return redactList


def metadata_field_count(tileSource, format, redactList):
    """
    Count how many metadata fields are likely to be shown to the user and how
    many could be redacted.

    :param tileSource: a large_image tile source.
    :param format: the vendor or None if unknown.
    :param redactList: the list of redactions (see get_redact_list).
    :returns: the count of shown and redactable fields.
    """
    shown = 0
    redactable = 0
    preset = 0
    metadata = tileSource.getInternalMetadata()
    for mainkey in metadata:
        if not isinstance(metadata[mainkey], dict):
            shown += 1
            if redactList['metadata'].get(mainkey):
                preset += 1
            else:
                redactable += 1
            continue
        for subkey in metadata[mainkey]:
            key = 'internal;%s;%s' % (mainkey, subkey)
            if format == 'aperio' and re.match(
                    r'^internal;openslide;(openslide.comment|tiff.ImageDescription)$', key):
                continue
            if re.match(r'^internal;openslide;openslide.level\[', key):
                continue
            if re.match(r'^internal;openslide;hamamatsu.(AHEX|MHLN)\[', key):
                continue
            shown += 1
            if redactList['metadata'].get(key):
                preset += 1
                continue
            if re.match(r'^internal;aperio_version$', key):
                continue
            if re.match(r'^internal;openslide;openslide\.(?!comment$)', key):
                continue
            if re.match(r'^internal;openslide;tiff.(ResolutionUnit|XResolution|YResolution)$', key):
                continue
            redactable += 1
    return {'visible': shown, 'redactable': redactable, 'automatic': preset}


def model_information(tileSource, format):
    """
    Return the model name or best information we have related to it.

    :param tileSource: a large_image tile source.
    :param format: the vendor or None if unknown.
    :returns: a string of model information or None.
    """
    metadata = tileSource.getInternalMetadata()
    for key in ('aperio.ScanScope ID', 'hamamatsu.Product'):
        if metadata.get('openslide', {}).get(key):
            return metadata['openslide'][key]
    for key in ('DICOM_MANUFACTURERS_MODEL_NAME', 'DICOM_DEVICE_SERIAL_NUMBER'):
        if metadata.get('xml', {}).get(key):
            return metadata['xml'][key]


def fadvise_willneed(item):
    """
    Tell the os we will need to read the entire file.

    :param item: the girder item.
    """
    try:
        tileSource = ImageItem().tileSource(item)
        path = tileSource._getLargeImagePath()
        fptr = open(path, 'rb')
        os.posix_fadvise(fptr.fileno(), 0, os.path.getsize(path), os.POSIX_FADV_WILLNEED)
    except Exception:
        pass


def redact_image_area(image, geojson):
    """
    Redact an area from a PIL image.

    :param image: a PIL image.
    :param geojson: area to be redacted in geojson format.
    """
    width, height = image.size
    polygon_svg = polygons_to_svg(geojson_to_polygons(geojson), width, height)
    svg_image = pyvips.Image.svgload_buffer(polygon_svg.encode())
    buffer = io.BytesIO()
    image.save(buffer, 'TIFF')
    vips_image = pyvips.Image.new_from_buffer(buffer.getvalue(), '')
    redacted_image = vips_image.composite([svg_image], pyvips.BlendMode.OVER)
    if redacted_image.bands > 3:
        redacted_image = redacted_image[:3]
    elif redacted_image.bands == 2:
        redacted_image = redacted_image[:1]
    redacted_data = redacted_image.write_to_buffer('.tiff')
    redacted_image = PIL.Image.open(io.BytesIO(redacted_data))
    return redacted_image


def redact_item(item, tempdir):
    """
    Redact a Girder item.  Based on the redact metadata, determine what
    redactions are necessary and perform them.

    :param item: a Girder large_image item.  The file in this item will be
        replaced with the redacted version.  The caller should copy the item
        before running this script, as otherwise the original file may be
        removed from the system.
    :param tempdir: a temporary directory to put all work files and the final
        result.
    :returns: the generated filepath.  The filepath ends in the original
        extension, its name is not important.
    :returns: a dictionary of information including 'mimetype'.
    """
    previouslyRedacted = bool(item.get('meta', {}).get('redacted'))
    redactList = get_redact_list(item)
    newTitle = get_generated_title(item)
    tileSource = ImageItem().tileSource(item)
    labelImage = None
    label_geojson = redactList.get('images', {}).get('label', {}).get('geojson')
    if (('label' not in redactList['images'] and not config.getConfig('always_redact_label')) or
            label_geojson is not None):
        try:
            labelImage = PIL.Image.open(io.BytesIO(tileSource.getAssociatedImage('label')[0]))
            ImageItem().removeThumbnailFiles(item)
        except Exception:
            pass
    if label_geojson is not None and labelImage is not None:
        labelImage = redact_image_area(labelImage, label_geojson)
    if config.getConfig('add_title_to_label'):
        labelImage = add_title_to_image(labelImage, newTitle, previouslyRedacted)
    macroImage = None
    macro_geojson = redactList.get('images', {}).get('macro', {}).get('geojson')
    redact_square_default = ('macro' not in redactList['images'] and
                             config.getConfig('redact_macro_square'))
    redact_square_manual = ('macro' in redactList['images'] and
                            redactList['images']['macro'].get('square'))
    redact_square = redact_square_default or redact_square_manual
    if redact_square or macro_geojson:
        try:
            macroImage = PIL.Image.open(io.BytesIO(tileSource.getAssociatedImage('macro')[0]))
            ImageItem().removeThumbnailFiles(item)
        except Exception:
            pass
    if macroImage is not None:
        if redact_square:
            macroImage = redact_topleft_square(macroImage)
        elif macro_geojson:
            macroImage = redact_image_area(macroImage, macro_geojson)
    format = determine_format(tileSource)
    func = None
    if format is not None:
        fadvise_willneed(item)
        func = globals().get('redact_format_' + format)
    if func is None:
        raise Exception('Cannot redact this format.')
    file, mimetype = func(item, tempdir, redactList, newTitle, labelImage, macroImage)
    info = {
        'format': format,
        'model': model_information(tileSource, format),
        'mimetype': mimetype,
        'redactionCount': {
            key: len([k for k, v in redactList[key].items() if v['value'] is None])
            for key in redactList if key != 'area'},
        'fieldCount': {
            'metadata': metadata_field_count(tileSource, format, redactList),
            'images': len(tileSource.getAssociatedImagesList()),
        },
    }
    return file, info


def aperio_value_list(item, redactList, title):
    """
    Get a list of aperio values that can be joined with | to form the aperio
    comment.

    :param item: the item to redact.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    """
    tileSource = ImageItem().tileSource(item)
    metadata = tileSource.getInternalMetadata() or {}
    comment = metadata['openslide']['openslide.comment']
    aperioHeader = comment.split('|', 1)[0]
    # Add defaults for required aperio fields to this dictionary
    aperioDict = {
    }
    for fullkey, value in metadata['openslide'].items():
        if fullkey.startswith('aperio.'):
            redactKey = 'internal;openslide;' + fullkey.replace('\\', '\\\\').replace(';', '\\;')
            value = redactList['metadata'].get(redactKey, {}).get('value', value)
            if value is not None and '|' not in value:
                key = fullkey.split('.', 1)[1]
                aperioDict[key] = value
    # From DeID Upload information
    aperioDict.update(get_deid_field_dict(item))
    # Required values
    aperioDict.update({
        'Filename': title,
        'Title': title,
    })
    aperioValues = [aperioHeader] + ['%s = %s' % (k, v) for k, v in sorted(aperioDict.items())]
    return aperioValues


def redact_tiff_tags(ifds, redactList, title):
    """
    Redact any tags of the form *;tiff.<tiff name name> from all IFDs.

    :param ifds: a list of ifd info records.  Tags may be removed or modified.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.  If any of a list of title tags
        exist, they are replaced with this value.
    """
    redactedTags = {}
    for key, value in redactList['metadata'].items():
        tiffkey = key.rsplit(';tiff.', 1)[-1]
        tiffdir = 0
        if ';tiff;' in key:
            tiffkey = key.rsplit(';tiff;', 1)[-1]
        if ':' in tiffkey:
            tiffkey, tiffdir = tiffkey.rsplit(':', 1)
            tiffdir = int(tiffdir)
        if tiffkey in tifftools.Tag:
            tag = tifftools.Tag[tiffkey].value
            redactedTags.setdefault(tiffdir, {})
            redactedTags[tiffdir][tag] = value['value']
    for titleKey in {'DocumentName', 'NDPI_REFERENCE', }:
        redactedTags[tifftools.Tag[titleKey].value] = title
    for idx, ifd in enumerate(ifds):
        # convert to a list since we may mutage the tag dictionary
        for tag, taginfo in list(ifd['tags'].items()):
            if tag in redactedTags.get(idx, {}):
                if redactedTags[idx][tag] is None:
                    del ifd['tags'][tag]
                else:
                    taginfo['datatype'] = tifftools.Datatype.ASCII
                    taginfo['data'] = redactedTags[idx][tag]


def get_deid_field_dict(item):
    """
    Return a dictionary with custom fields from the DeID Upload metadata.

    :param item: the item with data.
    :returns: a dictionary of key-vlaue pairs.
    """
    deid = item.get('meta', {}).get('deidUpload', {})
    if not isinstance(deid, dict):
        deid = {}
    result = {}
    for k, v in deid.items():
        result['CustomField.%s' % k] = str(v).replace('|', ' ')
    return result


def get_deid_field(item, prefix=None):
    """
    Return a text field with the DeID Upload metadata formatted for storage.

    :param item: the item with data.
    :returns: the text field.
    """
    from . import __version__

    version = 'DSA Redaction %s' % __version__
    if prefix and prefix.strip():
        if 'DSA Redaction' in prefix:
            prefix.split('DSA Redaction')[0].strip()
        if prefix:
            prefix = prefix.strip() + '\n'
    else:
        prefix = ''
    return prefix + version + '\n' + '|'.join([
        '%s = %s' % (k, v) for k, v in sorted(get_deid_field_dict(item).items())])


def add_deid_metadata(item, ifds):
    """
    Add deid metadata to the Software tag.

    :param item: the item to adjust.
    :param ifds: a list of ifd info records.  Tags may be added or modified.
    """
    ifds[0]['tags'][tifftools.Tag.Software.value] = {
        'datatype': tifftools.Datatype.ASCII,
        'data': get_deid_field(item),
    }


def geojson_to_polygons(geojson):
    """
    Convert geojson as generated by geojs's annotation layer.

    :param geojson: geojson record.
    :returns: an array of polygons, each of which is an array of points.
    """
    polys = []
    for feature in geojson['features']:
        if feature.get('geometry', {}).get('type') == 'Polygon':
            polys.append(feature['geometry']['coordinates'])
    return polys


def polygons_to_svg(polygons, width, height, cropAllowed=True, offsetx=0, offsety=0):
    """
    Convert a list of polygons to an svg record.

    :param polygons: a list of polygons.
    :param width: width of the image.
    :param height: height of the image.
    :param cropAllowed: if True, the final width and height may be smaller than
        that specified if the polygons don't cover the right or bottom edge.
    :param offsetx: if set, deduct this value from all polygon coordinates.
    :param offsety: if set, deduct this value from all polygon coordinates.
    """
    if offsetx or offsety:
        polygons = [[[[pt[0] - offsetx, pt[1] - offsety]
                      for poly in polygons for loop in poly for pt in loop]]]
    if cropAllowed:
        width = max(1, min(width, int(math.ceil(max(
            pt[0] for poly in polygons for loop in poly for pt in loop)))))
        height = max(1, min(height, int(math.ceil(max(
            pt[1] for poly in polygons for loop in poly for pt in loop)))))
    svg = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    for poly in polygons:
        svg.append('<path fill-rule="evenodd" fill="black" d="')
        for loop in poly:
            svg.append('M ')
            svg.append(' L '.join([f'{pt[0]},{pt[1]}' for pt in loop]))
            svg.append(' z')
        svg.append('"/>')
    svg.append('</svg>')
    svg = ''.join(svg)
    return svg


def redact_format_aperio(item, tempdir, redactList, title, labelImage, macroImage):
    """
    Redact aperio files.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
    :param macroImage: a PIL image with a new macro image.  None to keep or
        redact the current macro image.
    :returns: (filepath, mimetype) The redacted filepath in the tempdir and
        its mimetype.
    """
    import large_image_source_tiff.girder_source

    tileSource = ImageItem().tileSource(item)
    sourcePath = tileSource._getLargeImagePath()
    logger.info('Redacting aperio file %s', sourcePath)
    tiffinfo = tifftools.read_tiff(sourcePath)
    ifds = tiffinfo['ifds']
    if redactList.get('area', {}).get('_wsi', {}).get('geojson'):
        ifds = redact_format_aperio_philips_redact_wsi(
            tileSource, ifds, redactList['area']['_wsi']['geojson'], tempdir)
        ImageItem().removeThumbnailFiles(item)
    aperioValues = aperio_value_list(item, redactList, title)
    imageDescription = '|'.join(aperioValues)
    # We expect aperio to have the full resolution image in directory 0, the
    # thumbnail in directory 1, lower resolutions starting in 2, and label and
    # macro images in other directories.  Confirm this -- our tiff reader will
    # report the directories used for the full resolution.
    tiffSource = large_image_source_tiff.girder_source.TiffGirderTileSource(item)
    mainImageDir = [dir._directoryNum for dir in tiffSource._tiffDirectories[::-1] if dir]
    associatedImages = tileSource.getAssociatedImagesList()
    if mainImageDir != [d + (1 if d and 'thumbnail' in associatedImages else 0)
                        for d in range(len(mainImageDir))]:
        raise Exception('Aperio TIFF directories are not in the expected order.')
    firstAssociatedIdx = max(mainImageDir) + 1
    # Set new image description
    ifds[0]['tags'][tifftools.Tag.ImageDescription.value] = {
        'datatype': tifftools.Datatype.ASCII,
        'data': imageDescription,
    }
    # redact or adjust thumbnail
    if 'thumbnail' in associatedImages:
        if 'thumbnail' in redactList['images']:
            ifds.pop(1)
            firstAssociatedIdx -= 1
        else:
            thumbnailComment = ifds[1]['tags'][tifftools.Tag.ImageDescription.value]['data']
            thumbnailDescription = '|'.join(thumbnailComment.split('|', 1)[0:1] + aperioValues[1:])
            ifds[1]['tags'][tifftools.Tag.ImageDescription.value][
                'data'] = thumbnailDescription
    # redact other images
    for idx in range(len(ifds) - 1, 0, -1):
        ifd = ifds[idx]
        key = None
        keyparts = ifd['tags'].get(tifftools.Tag.ImageDescription.value, {}).get(
            'data', '').split('\n', 1)[-1].strip().split()
        if len(keyparts) and keyparts[0].lower() and not keyparts[0][0].isdigit():
            key = keyparts[0].lower()
        if (key is None and ifd['tags'].get(tifftools.Tag.NewSubfileType.value) and
                ifd['tags'][tifftools.Tag.NewSubfileType.value]['data'][0] &
                tifftools.Tag.NewSubfileType.bitfield.ReducedImage.value):
            key = 'label' if ifd['tags'][
                tifftools.Tag.NewSubfileType.value]['data'][0] == 1 else 'macro'
        if key in redactList['images'] or key == 'label' or (key == 'macro' and macroImage):
            ifds.pop(idx)
    # Add back label and macro image
    if macroImage:
        redact_format_aperio_add_image(
            'macro', macroImage, ifds, firstAssociatedIdx, tempdir, aperioValues)
    if labelImage:
        redact_format_aperio_add_image(
            'label', labelImage, ifds, firstAssociatedIdx, tempdir, aperioValues)
    # redact general tiff tags
    redact_tiff_tags(ifds, redactList, title)
    add_deid_metadata(item, ifds)
    outputPath = os.path.join(tempdir, 'aperio.svs')
    tifftools.write_tiff(ifds, outputPath)
    logger.info('Redacted aperio file %s as %s', sourcePath, outputPath)
    return outputPath, 'image/tiff'


def redact_format_aperio_add_image(key, image, ifds, firstAssociatedIdx, tempdir, aperioValues):
    """
    Add a label or macro image to an aperio file.

    :param key: either 'label' or 'macro'
    :param image: a PIL image.
    :param ifds: ifds of output file.
    :param firstAssociatedIdx: ifd index of first associated image.
    :param tempdir: a directory for work files and the final result.
    :param aperioValues: a list of aperio metadata values.
    """
    imagePath = os.path.join(tempdir, '%s.tiff' % key)
    image.save(imagePath, format='tiff', compression='jpeg', quality=90)
    imageinfo = tifftools.read_tiff(imagePath)
    imageDescription = aperioValues[0].split('\n', 1)[1] + '\n%s %dx%d' % (
        key, image.width, image.height)
    imageinfo['ifds'][0]['tags'][tifftools.Tag.ImageDescription.value] = {
        'datatype': tifftools.Datatype.ASCII,
        'data': imageDescription
    }
    imageinfo['ifds'][0]['tags'][tifftools.Tag.NewSubfileType] = {
        'data': [9 if key == 'macro' else 1], 'datatype': tifftools.Datatype.LONG}
    imageinfo['ifds'][0]['tags'][tifftools.Tag.ImageDepth] = {
        'data': [1], 'datatype': tifftools.Datatype.SHORT}
    ifds[firstAssociatedIdx:firstAssociatedIdx] = imageinfo['ifds']


def read_ts_as_vips(ts):
    """
    Read a tile source into a vips image.

    :param ts: a large image tile source.
    :returns: a vips image.
    """
    from large_image_converter import (_convert_large_image_tile, _drain_pool, _get_thread_pool,
                                       _import_pyvips, _pool_add)

    _import_pyvips()
    _iterTileSize = 4096
    strips = []
    pool = _get_thread_pool()
    tasks = []
    tilelock = threading.Lock()
    for tile in ts.tileIterator(tile_size=dict(width=_iterTileSize)):
        _pool_add(tasks, (pool.submit(_convert_large_image_tile, tilelock, strips, tile), ))
    _drain_pool(pool, tasks)
    img = strips[0]
    for stripidx in range(1, len(strips)):
        img = img.insert(strips[stripidx], 0, stripidx * _iterTileSize, expand=True)
    if img.bands > 3:
        img = img[:3]
    elif img.bands == 2:
        img = img[:1]
    return img


def redact_wsi_geojson(geojson, width, height, origImage):
    """
    Given an original image and a geojson record, produce a redacted image.

    :param geojson: geojson to redact.
    :param width: the width of the original image.
    :param height: the height of the original image.
    :param origImage: a vips image.
    :returns: redactedImage: a vips image.
    """
    polys = geojson_to_polygons(geojson)
    logger.info('Redacting wsi - polygons: %r', polys)
    svgImage = None
    chunk = 16384
    for yoffset in range(0, height, chunk):
        for xoffset in range(0, width, chunk):
            polygonSvg = polygons_to_svg(
                polys, min(width - xoffset, chunk), min(height - yoffset, chunk),
                cropAllowed=True, offsetx=xoffset, offsety=yoffset)
            logger.info('Redacting wsi - svg: %r', polygonSvg)
            chunkImage = pyvips.Image.svgload_buffer(polygonSvg.encode())
            if not svgImage:
                svgImage = chunkImage
            else:
                svgImage = svgImage.insert(chunkImage, xoffset, yoffset, expand=True)
    logger.info('Redacting wsi - compositing')
    redactedImage = origImage.composite([svgImage], pyvips.BlendMode.OVER)
    if redactedImage.bands > 3:
        redactedImage = redactedImage[:3]
    elif redactedImage.bands == 2:
        redactedImage = redactedImage[:1]
    return redactedImage


def redact_format_aperio_philips_redact_wsi(tileSource, ifds, geojson, tempdir):
    """
    Given a geojson list of polygons, remove them from the wsi.

    :param tileSource: the large_image tile source.
    :param ifds: ifds of output file.
    :param geojson: geojson to redact.
    :returns ifds: a modified list of ifds.
    """
    logger.info('Redacting wsi %s', tileSource._getLargeImagePath())
    width = ifds[0]['tags'][tifftools.Tag.ImageWidth.value]['data'][0]
    height = ifds[0]['tags'][tifftools.Tag.ImageHeight.value]['data'][0]
    logger.info('Redacting wsi - loading source')
    origImage = read_ts_as_vips(tileSource)
    redactedImage = redact_wsi_geojson(geojson, width, height, origImage)
    logger.info('Redacting wsi - saving')
    tileWidth = ifds[0]['tags'][tifftools.Tag.TileWidth.value]['data'][0]
    tileHeight = ifds[0]['tags'][tifftools.Tag.TileHeight.value]['data'][0]
    compression = ifds[0]['tags'][tifftools.Tag.Compression.value]['data'][0]
    quality = 95
    if compression == tifftools.constants.Compression.JPEG.value:
        try:
            quality = tifftools.constants.EstimateJpegQuality(
                ifds[0]['tags'][tifftools.Tag.JPEGTables.value]['data'])
        except KeyError:
            pass
    wsiPath = os.path.join(tempdir, '_wsi.tiff')
    redactedImage.tiffsave(
        wsiPath, tile=True, tile_width=tileWidth, tile_height=tileHeight,
        pyramid=True, bigtiff=True, compression='jpeg', Q=quality)
    logger.info('Redacting wsi - saved')
    redactedInfo = tifftools.read_tiff(wsiPath)
    redifds = redactedInfo['ifds']
    newifds = []
    for idx, ifd in enumerate(ifds):
        newifd = None
        ifdw = ifd['tags'][tifftools.Tag.ImageWidth.value]['data'][0]
        ifdh = ifd['tags'][tifftools.Tag.ImageHeight.value]['data'][0]
        if tifftools.Tag.TileWidth.value in ifd['tags']:
            for redifd in redifds:
                redw = redifd['tags'][tifftools.Tag.ImageWidth.value]['data'][0]
                redh = redifd['tags'][tifftools.Tag.ImageHeight.value]['data'][0]
                if (ifdw == redw and ifdh == redh) or (
                        ifdw == math.ceil(redw / tileWidth) * tileWidth and
                        ifdh == math.ceil(redh / tileHeight) * tileHeight):
                    newifd = redifd
                    break
        if newifd:
            for tag in {tifftools.Tag.ImageDescription, tifftools.Tag.NewSubfileType}:
                if tag.value in ifd['tags']:
                    newifd['tags'][tag.value] = ifd['tags'][tag.value]
            logger.info('Redacting wsi - replacing directory %d' % idx)
        else:
            logger.info('Redacting wsi - keeping directory %d' % idx)
        newifds.append(newifd or ifd)
    return newifds


def set_mcu_starts(path, mcutag, offset, length):
    """
    Find the MCU restart locations and populate tag data with the information.

    :param path: path to the file with JPEG compression.
    :param mcutag: A dictionary whose 'data' value will be set to the list of
        mcu starts.
    :param offset: start of the JPEG in the file.
    :param length: length of the JPEG in the file.
    """
    fptr = open(path, 'rb')
    fptr.seek(offset)
    chunksize = 2 * 1024 ** 2
    mcu = []
    previous = b''
    pos = 0
    while length > 0:
        data = fptr.read(min(length, chunksize))
        if len(data) != min(length, chunksize):
            length = 0
        else:
            length -= len(data)
        data = previous + data
        parts = data.split(b'\xff')
        previous = b'\xff' + parts[-1]
        pos += len(parts[0])
        for part in parts[1:-1]:
            if not len(mcu):
                if part[0] == 0xda:
                    mcu.append(pos + 2 + part[1] * 256 + part[2])
            elif part[0] >= 0xd0 and part[0] <= 0xd7:
                mcu.append(pos + 2)
            pos += 1 + len(part)
    mcutag['data'] = mcu


def redact_format_hamamatsu_redact_wsi(tileSource, ifds, geojson, tempdir):
    """
    Given a geojson list of polygons, remove them from the wsi.

    :param tileSource: the large_image tile source.
    :param ifds: ifds of output file.
    :param geojson: geojson to redact.
    :returns ifds: a modified list of ifds.
    """
    logger.info('Redacting wsi %s', tileSource._getLargeImagePath())
    width = ifds[0]['tags'][tifftools.Tag.ImageWidth.value]['data'][0]
    height = ifds[0]['tags'][tifftools.Tag.ImageHeight.value]['data'][0]
    logger.info('Redacting wsi - loading source')
    origImage = pyvips.Image.tiffload(tileSource._getLargeImagePath(), page=0)
    redactedImage = redact_wsi_geojson(geojson, width, height, origImage)
    if tifftools.Tag.NDPI_JpegQuality.value in ifds[0]['tags']:
        quality = int(ifds[0]['tags'][tifftools.Tag.NDPI_JpegQuality.value]['data'][0])
    else:
        quality = 95
    newifds = []
    reduced = redactedImage
    for idx, ifd in enumerate(ifds):
        newifd = None
        ifdw = ifd['tags'][tifftools.Tag.ImageWidth.value]['data'][0]
        ifdh = ifd['tags'][tifftools.Tag.ImageLength.value]['data'][0]
        if (tifftools.Tag.NDPI_SOURCELENS.value in ifd['tags'] and
                ifd['tags'][tifftools.Tag.NDPI_SOURCELENS.value]['data'][0] > 0):
            logger.info('Redacting wsi - saving directory %d' % idx)
            wsiPath = os.path.join(tempdir, '_wsi_%d.tiff' % idx)
            jpegPath = os.path.join(tempdir, '_wsi_%d.jpeg' % idx)
            reduced = reduced.shrink(reduced.width / ifdw, reduced.width / ifdw)
            if idx:
                logger.info('Redacting wsi - storing')
                reducedTemp = pyvips.Image.new_temp_file('%s.v')
                reduced.write(reducedTemp)
                reduced = reducedTemp
            # Save a tiny image just to have a placeholder
            reduced.crop(0, 0, min(32, reduced.width), min(32, reduced.height)).tiffsave(wsiPath)
            logger.info('Redacting wsi - saving jpeg')
            jpegPos = os.path.getsize(wsiPath)
            reduced.jpegsave(jpegPath, Q=quality, subsample_mode=pyvips.ForeignJpegSubsample.OFF)
            # Add restart markers to the jpeg
            if tifftools.Tag.NDPI_MCU_STARTS.value not in ifd['tags']:
                restartInterval = int(math.ceil(ifdw / 8))
                while restartInterval > 32 and not restartInterval % 2:
                    restartInterval /= 2
            else:
                restartInterval = (
                    int(math.ceil(ifdw / 8) * math.ceil(ifdh / 8)) //
                    len(ifd['tags'][tifftools.Tag.NDPI_MCU_STARTS.value]['data']))
            logger.info('Redacting wsi - converting jpeg (restart interval %d)', restartInterval)
            subprocess.check_call(
                ['jpegtran', '-restart', '%dB' % restartInterval, jpegPath]
                if tifftools.Tag.NDPI_MCU_STARTS.value in ifd['tags']
                else ['cat', jpegPath],
                stdout=open(wsiPath, 'ab'))
            jpegLen = os.path.getsize(wsiPath) - jpegPos
            redactedInfo = tifftools.read_tiff(wsiPath)
            newifd = redactedInfo['ifds'][0]
            newifd['tags'][tifftools.Tag.ImageWidth.value]['data'][0] = reduced.width
            newifd['tags'][tifftools.Tag.ImageLength.value]['data'][0] = reduced.height
            newifd['tags'][tifftools.Tag.RowsPerStrip.value]['data'][0] = reduced.height
            newifd['tags'][tifftools.Tag.Compression.value]['data'][0] = \
                tifftools.constants.Compression.JPEG.value
            newifd['tags'][tifftools.Tag.Photometric.value]['data'][0] = \
                tifftools.constants.Photometric.YCbCr.value
            newifd['tags'][tifftools.Tag.StripOffsets.value]['data'] = [jpegPos]
            newifd['tags'][tifftools.Tag.StripByteCounts.value]['data'] = [jpegLen]
            for tag in {
                    tifftools.Tag.Make, tifftools.Tag.Model, tifftools.Tag.ImageDescription,
                    tifftools.Tag.NewSubfileType, tifftools.Tag.Software, tifftools.Tag.DateTime,
                    tifftools.Tag.SampleFormat,
                    tifftools.Tag.XResolution, tifftools.Tag.YResolution,
                    } | {
                    tag for tag in tifftools.Tag if tag.name.startswith('NDPI')}:
                if tag.value in ifd['tags']:
                    newifd['tags'][tag.value] = ifd['tags'][tag.value]
            for numtag in {65433, 65443}:
                if numtag in ifd['tags']:
                    newifd['tags'][numtag] = ifd['tags'][numtag]
            if tifftools.Tag.NDPI_MCU_STARTS.value in ifd['tags']:
                set_mcu_starts(
                    wsiPath, newifd['tags'][tifftools.Tag.NDPI_MCU_STARTS.value],
                    newifd['tags'][tifftools.Tag.StripOffsets.value]['data'][0],
                    sum(newifd['tags'][tifftools.Tag.StripByteCounts.value]['data']))
            logger.info('Redacting wsi - replacing directory %d' % idx)
        else:
            logger.info('Redacting wsi - keeping directory %d' % idx)
        newifds.append(newifd or ifd)
    return newifds


def redact_format_hamamatsu(item, tempdir, redactList, title, labelImage, macroImage):
    """
    Redact hamamatsu files.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
    :param macroImage: a PIL image with a new macro image.  None to keep or
        redact the current macro image.
    :returns: (filepath, mimetype) The redacted filepath in the tempdir and
        its mimetype.
    """
    tileSource = ImageItem().tileSource(item)
    sourcePath = tileSource._getLargeImagePath()
    tiffinfo = tifftools.read_tiff(sourcePath)
    ifds = tiffinfo['ifds']
    if redactList.get('area', {}).get('_wsi', {}).get('geojson'):
        ifds = redact_format_hamamatsu_redact_wsi(
            tileSource, ifds, redactList['area']['_wsi']['geojson'], tempdir)
        ImageItem().removeThumbnailFiles(item)
    sourceLensTag = tifftools.Tag.NDPI_SOURCELENS.value
    for key in redactList['images']:
        if key == 'macro' and macroImage:
            continue
        lensval = {'macro': -1, 'nonempty': -2}
        ifds = [ifd for ifd in ifds
                if sourceLensTag not in ifd['tags'] or
                ifd['tags'][sourceLensTag]['data'][0] != lensval.get(key)]
    redact_tiff_tags(ifds, redactList, title)
    add_deid_metadata(item, ifds)
    propertyTag = tifftools.Tag.NDPI_PROPERTY_MAP.value
    propertyList = ifds[0]['tags'][propertyTag]['data'].replace('\r', '\n').split('\n')
    ndpiProperties = {p.split('=')[0]: p.split('=', 1)[1] for p in propertyList if '=' in p}
    for fullkey, value in redactList['metadata'].items():
        if fullkey.startswith('internal;openslide;hamamatsu.'):
            key = fullkey.split('internal;openslide;hamamatsu.', 1)[1]
            if key in ndpiProperties:
                if value is None:
                    del ndpiProperties[key]
                else:
                    ndpiProperties[key] = value['value'] if isinstance(
                        value, dict) and 'value' in value else value
    propertyList = ['%s=%s\r\n' % (k, v) for k, v in ndpiProperties.items()]
    propertyMap = ''.join(propertyList)
    for ifd in ifds:
        ifd['tags'][tifftools.Tag.NDPI_REFERENCE.value] = {
            'datatype': tifftools.Datatype.ASCII,
            'data': title,
        }
        ifd['tags'][propertyTag] = {
            'datatype': tifftools.Datatype.ASCII,
            'data': propertyMap,
        }
    redact_format_hamamatsu_replace_macro(macroImage, ifds, tempdir)
    outputPath = os.path.join(tempdir, 'hamamatsu.ndpi')
    tifftools.write_tiff(ifds, outputPath)
    return outputPath, 'image/tiff'


def redact_format_hamamatsu_replace_macro(macroImage, ifds, tempdir):
    """
    Modify a macro image in a hamamatsu file.

    :param macrosImage: a PIL image or None to not change.
    :param ifds: ifds of output file.
    :param tempdir: a directory for work files and the final result.
    """
    macroifd = None
    for idx, ifd in enumerate(ifds):
        if (tifftools.Tag.NDPI_SOURCELENS.value in ifd['tags'] and
                ifd['tags'][tifftools.Tag.NDPI_SOURCELENS.value]['data'][0] == -1):
            macroifd = idx
            break
    if not macroImage or macroifd is None:
        return
    imagePath = os.path.join(tempdir, 'macro.tiff')
    tifftools.write_tiff(ifds[macroifd], imagePath)
    image = io.BytesIO()
    macroImage.save(image, 'jpeg', qaulity=90)
    jpos = os.path.getsize(imagePath)
    jlen = len(image.getvalue())
    imageifd = tifftools.read_tiff(imagePath)['ifds'][0]
    open(imagePath, 'ab').write(image.getvalue())
    imageifd['tags'][tifftools.Tag.StripOffsets.value]['data'][0] = jpos
    imageifd['tags'][tifftools.Tag.StripByteCounts.value]['data'][0] = jlen
    imageifd['size'] += jlen
    ifds[macroifd] = imageifd


PhilipsTagElements = {  # Group, Element, Format
    'DICOM_ACQUISITION_DATETIME': ('0x0008', '0x002A', 'IString'),
    'DICOM_BITS_ALLOCATED': ('0x0028', '0x0100', 'IUInt16'),
    'DICOM_BITS_STORED': ('0x0028', '0x0101', 'IUInt16'),
    'DICOM_DATE_OF_LAST_CALIBRATION': ('0x0018', '0x1200', 'IStringArray'),
    'DICOM_DERIVATION_DESCRIPTION': ('0x0008', '0x2111', 'IString'),
    'DICOM_DEVICE_SERIAL_NUMBER': ('0x0018', '0x1000', 'IString'),
    'DICOM_HIGH_BIT': ('0x0028', '0x0102', 'IUInt16'),
    'DICOM_ICCPROFILE': ('0x0028', '0x2000', 'IString'),
    'DICOM_LOSSY_IMAGE_COMPRESSION': ('0x0028', '0x2110', 'IString'),
    'DICOM_LOSSY_IMAGE_COMPRESSION_METHOD': ('0x0028', '0x2114', 'IString'),
    'DICOM_LOSSY_IMAGE_COMPRESSION_RATIO': ('0x0028', '0x2112', 'IDouble'),
    'DICOM_MANUFACTURER': ('0x0008', '0x0070', 'IString'),
    'DICOM_MANUFACTURERS_MODEL_NAME': ('0x0008', '0x1090', 'IString'),
    'DICOM_SAMPLES_PER_PIXEL': ('0x0028', '0x0002', 'IUInt16'),
    'DICOM_SOFTWARE_VERSIONS': ('0x0018', '0x1020', 'IStringArray'),
    'DICOM_TIME_OF_LAST_CALIBRATION': ('0x0018', '0x1201', 'IStringArray'),
    'DP_COLOR_MANAGEMENT': ('0x301D', '0x1013', 'IDataObjectArray'),
    'DP_WAVELET_DEADZONE': ('0x301D', '0x101C', 'IUInt16'),
    'DP_WAVELET_QUANTIZER': ('0x301D', '0x101B', 'IUInt16'),
    'DP_WAVELET_QUANTIZER_SETTINGS_PER_COLOR': ('0x301D', '0x1019', 'IDataObjectArray'),
    'DP_WAVELET_QUANTIZER_SETTINGS_PER_LEVEL': ('0x301D', '0x101A', 'IDataObjectArray'),
    'PIIM_DP_SCANNER_CALIBRATION_STATUS': ('0x101D', '0x100A', 'IString'),
    'PIIM_DP_SCANNER_OPERATOR_ID': ('0x101D', '0x1009', 'IString'),
    'PIIM_DP_SCANNER_RACK_NUMBER': ('0x101D', '0x1007', 'IUInt16'),
    'PIIM_DP_SCANNER_SLOT_NUMBER': ('0x101D', '0x1008', 'IUInt16'),
    'PIM_DP_IMAGE_DATA': ('0x301D', '0x1005', 'IString'),
    'PIM_DP_IMAGE_TYPE': ('0x301D', '0x1004', 'IString'),
    'PIM_DP_SCANNED_IMAGES': ('0x301D', '0x1003', 'IDataObjectArray'),
    'PIM_DP_SCANNER_RACK_PRIORITY': ('0x301D', '0x1010', 'IUInt16'),
    'PIM_DP_UFS_BARCODE': ('0x301D', '0x1002', 'IString'),
    'PIM_DP_UFS_INTERFACE_VERSION': ('0x301D', '0x1001', 'IString'),
    'UFS_IMAGE_BLOCK_COMPRESSION_METHOD': ('0x301D', '0x200F', 'IString'),
    'UFS_IMAGE_BLOCK_COORDINATE': ('0x301D', '0x200E', 'IUInt32Array'),
    'UFS_IMAGE_BLOCK_DATA_OFFSET': ('0x301D', '0x2010', 'IUint64'),
    'UFS_IMAGE_BLOCK_HEADERS': ('0x301D', '0x200D', 'IDataObjectArray'),
    'UFS_IMAGE_BLOCK_HEADER_TABLE': ('0x301D', '0x2014', 'IString'),
    'UFS_IMAGE_BLOCK_HEADER_TEMPLATES': ('0x301D', '0x2009', 'IDataObjectArray'),
    'UFS_IMAGE_BLOCK_HEADER_TEMPLATE_ID': ('0x301D', '0x2012', 'IUInt32'),
    'UFS_IMAGE_BLOCK_SIZE': ('0x301D', '0x2011', 'IUint64'),
    'UFS_IMAGE_DIMENSIONS': ('0x301D', '0x2003', 'IDataObjectArray'),
    'UFS_IMAGE_DIMENSIONS_IN_BLOCK': ('0x301D', '0x200C', 'IUInt16Array'),
    'UFS_IMAGE_DIMENSIONS_OVER_BLOCK': ('0x301D', '0x2002', 'IUInt16Array'),
    'UFS_IMAGE_DIMENSION_DISCRETE_VALUES_STRING': ('0x301D', '0x2008', 'IStringArray'),
    'UFS_IMAGE_DIMENSION_NAME': ('0x301D', '0x2004', 'IString'),
    'UFS_IMAGE_DIMENSION_RANGE': ('0x301D', '0x200B', 'IUInt32Array'),
    'UFS_IMAGE_DIMENSION_RANGES': ('0x301D', '0x200A', 'IDataObjectArray'),
    'UFS_IMAGE_DIMENSION_SCALE_FACTOR': ('0x301D', '0x2007', 'IDouble'),
    'UFS_IMAGE_DIMENSION_TYPE': ('0x301D', '0x2005', 'IString'),
    'UFS_IMAGE_DIMENSION_UNIT': ('0x301D', '0x2006', 'IString'),
    'UFS_IMAGE_GENERAL_HEADERS': ('0x301D', '0x2000', 'IDataObjectArray'),
    'UFS_IMAGE_NUMBER_OF_BLOCKS': ('0x301D', '0x2001', 'IUInt32')
}


def philips_tag(dict, key, value=None, subkey=None, subvalue=None):
    """
    Given an xml dictionary and a key, return information about the philips
    tag in the dictionary.

    :param dict: an xml dictionary.
    :param key: the key to match.
    :param value: the value to match.  None to match any value.  Ignored if
        subkey is specified.
    :param subkey: the subkey to match.  None to not match a subkey.
    :param subvalue: the value of the subkey to match.
    :returns: None if no match, otherwise a dictionary object, the index of the
        dictionary object, the tag list, the index in the tag list, and the tag
        entry or subkey entry.
    """
    dobjs = dict['DataObject']
    if not isinstance(dobjs, list):
        dobjs = [dobjs]
    for didx, dobj in enumerate(dobjs):
        taglist = dobj['Attribute']
        if not isinstance(taglist, list):
            taglist = [taglist]
        for tidx, entry in enumerate(taglist):
            if entry['Name'] == key:
                if subkey is None and (value is None or entry['text'] == value):
                    return dobjs, didx, taglist, tidx, entry
                elif 'Array' in entry:
                    subtag = philips_tag(entry['Array'], subkey, subvalue)
                    if subtag is not None:
                        return dobjs, didx, taglist, tidx, subtag
    return None


def redact_format_philips(item, tempdir, redactList, title, labelImage, macroImage):
    """
    Redact philips files.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
    :param macroImage: a PIL image with a new macro image.  None to keep or
        redact the current macro image.
    :returns: (filepath, mimetype) The redacted filepath in the tempdir and
        its mimetype.
    """
    tileSource = ImageItem().tileSource(item)
    sourcePath = tileSource._getLargeImagePath()
    tiffinfo = tifftools.read_tiff(sourcePath)
    xmldict = tileSource._tiffDirectories[-1]._description_record
    ifds = tiffinfo['ifds']
    if redactList.get('area', {}).get('_wsi', {}).get('geojson'):
        ifds = redact_format_aperio_philips_redact_wsi(
            tileSource, ifds, redactList['area']['_wsi']['geojson'], tempdir)
        ImageItem().removeThumbnailFiles(item)
    # redact images from xmldict
    images = philips_tag(xmldict, 'PIM_DP_SCANNED_IMAGES')
    for key, pkey in [('macro', 'MACROIMAGE'), ('label', 'LABELIMAGE')]:
        if key in redactList['images'] and images:
            if key == 'macro' and macroImage:
                continue
            tag = philips_tag(
                xmldict, 'PIM_DP_SCANNED_IMAGES', None, 'PIM_DP_IMAGE_TYPE', pkey)
            if tag:
                tag[-1][0].pop(tag[-1][1])
    # redact images from ifds
    ifds = [ifd for ifd in ifds
            if ifd['tags'].get(tifftools.Tag.ImageDescription.value, {}).get(
                'data', '').split()[0].lower() not in redactList['images'] or (
                ifd['tags'].get(tifftools.Tag.ImageDescription.value, {}).get(
                    'data', '').split()[0].lower() == 'macro' and macroImage)]

    redactList = copy.copy(redactList)
    title_redaction_list_entry = generate_system_redaction_list_entry(title)
    redactList['metadata']['internal;xml;PIIM_DP_SCANNER_OPERATOR_ID'] = title_redaction_list_entry
    redactList['metadata']['internal;xml;PIM_DP_UFS_BARCODE'] = title_redaction_list_entry
    # redact general tiff tags
    redact_tiff_tags(ifds, redactList, title)
    add_deid_metadata(item, ifds)
    # remove redacted philips tags
    for key in redactList['metadata']:
        if not key.startswith('internal;xml;'):
            continue
        key = key.split(';', 2)[-1]
        parts = key.split('|') + [None]
        tag = philips_tag(xmldict, parts[0], None, parts[1])
        if tag:
            if parts[1] is not None:
                tag[-1][2].pop(tag[-1][3])
            else:
                tag[2].pop(tag[3])
    # Add back philips tags with values
    for key, value in redactList['metadata'].items():
        if not key.startswith('internal;xml;'):
            continue
        key = key.split(';', 2)[-1]
        if value is not None and '|' not in key and key in PhilipsTagElements:
            plist = xmldict['DataObject']['Attribute']
            pelem = PhilipsTagElements[key]
            entry = {
                'Name': key,
                'Group': pelem[0],
                'Element': pelem[1],
                'PMSVR': pelem[2],
                'text': value,
            }
            plist.insert(0, entry)
    tag = philips_tag(xmldict, 'PIM_DP_SCANNED_IMAGES')
    redact_format_philips_replace_macro(
        macroImage, ifds, tempdir, tag[2][tag[3]]['Array']['DataObject'])
    # Insert label image
    if labelImage:
        labelPath = os.path.join(tempdir, 'label.tiff')
        labelImage.save(labelPath, format='tiff', compression='jpeg', quality=90)
        labelinfo = tifftools.read_tiff(labelPath)
        labelinfo['ifds'][0]['tags'][tifftools.Tag.ImageDescription.value] = {
            'datatype': tifftools.Datatype.ASCII,
            'data': 'Label'
        }
        labelinfo['ifds'][0]['tags'][tifftools.Tag.NewSubfileType] = {
            'data': [1], 'datatype': tifftools.Datatype.LONG}
        ifds.extend(labelinfo['ifds'])
        jpeg = io.BytesIO()
        labelImage.save(jpeg, format='jpeg', quality=90)
        tag[2][tag[3]]['Array']['DataObject'].append({
            'Attribute': [{
                'Name': 'PIM_DP_IMAGE_TYPE',
                'Group': '0x301D',
                'Element': '0x1004',
                'PMSVR': 'IString',
                'text': 'LABELIMAGE',
            }, {
                'Name': 'PIM_DP_IMAGE_DATA',
                'Group': '0x301D',
                'Element': '0x1005',
                'PMSVR': 'IString',
                'text': base64.b64encode(jpeg.getvalue()).decode(),
            }],
            'ObjectType': 'DPScannedImage',
        })
    ifds[0]['tags'][tifftools.Tag.ImageDescription.value] = {
        'datatype': tifftools.Datatype.ASCII,
        'data': xml.etree.ElementTree.tostring(
            dictToEtree(xmldict), encoding='utf8', method='xml').decode(),
    }
    outputPath = os.path.join(tempdir, 'philips.tiff')
    tifftools.write_tiff(ifds, outputPath)
    return outputPath, 'image/tiff'


def redact_format_philips_replace_macro(macroImage, ifds, tempdir, pdo):
    """
    Modify a macro image in a philips file.

    :param macroImage: a PIL image or None to not change.
    :param ifds: ifds of output file.
    :param tempdir: a directory for work files and the final result.
    :param pdo: Philips DataObject array.
    """
    macroifd = None
    for idx, ifd in enumerate(ifds):
        if ifd['tags'].get(tifftools.Tag.ImageDescription.value, {}).get(
                'data', '').split()[0].lower() == 'macro':
            macroifd = idx
            break
    if not macroImage or macroifd is None:
        return
    logger.info('Replacing Philips macro')
    imagePath = os.path.join(tempdir, 'macro.tiff')
    image = io.BytesIO()
    macroImage.save(image, 'TIFF')
    image = pyvips.Image.new_from_buffer(image.getvalue(), '')
    image.write_to_file(imagePath, Q=85, compression='jpeg')
    imageifd = tifftools.read_tiff(imagePath)['ifds'][0]
    imageifd['tags'][tifftools.Tag.ImageDescription.value] = ifds[
        macroifd]['tags'][tifftools.Tag.ImageDescription.value]
    ifds[macroifd] = imageifd

    for dobj in pdo:
        if 'Attribute' in dobj:
            used = False
            for attr in dobj['Attribute']:
                if attr['Name'] == 'PIM_DP_IMAGE_TYPE' and attr['text'] == 'MACROIMAGE':
                    used = True
            if used:
                for attr in dobj['Attribute']:
                    if attr['Name'] == 'PIM_DP_IMAGE_DATA':
                        jpeg = io.BytesIO()
                        macroImage.save(jpeg, 'jpeg', quality=85)
                        attr['text'] = base64.b64encode(jpeg.getvalue()).decode()


def add_title_to_image(image, title, previouslyAdded=False, minWidth=384,
                       background='#000000', textColor='#ffffff', square=True):
    """
    Add a title to an image.  If the image doesn't exist, a new image is made
    the minimum width and appropriate height.  If the image does exist, a bar
    is added at its top to hold the title.  If an existing image is smaller
    than minWidth, it is pillarboxed to the minWidth.

    :param image: a PIL image or None.
    :param title: a text string.
    :param previouslyAdded: if true and modifying an image, don't allocate more
        space for the title; overwrite the top of the image instead.
    :param minWidth: the minimum width for the new image.
    :param background: the background color of the title and any necessary
        pillarbox.
    :param textColor: the color of the title text.
    :param square: if True, output a square image.
    :returns: a PIL image.
    """
    mode = 'RGB'
    if image is None:
        image = PIL.Image.new(mode, (0, 0))
    image = image.convert(mode)
    w, h = image.size
    background = PIL.ImageColor.getcolor(background, mode)
    textColor = PIL.ImageColor.getcolor(textColor, mode)
    targetW = max(minWidth, w)
    fontSize = 0.15
    imageDraw = PIL.ImageDraw.Draw(image)
    for iter in range(3, 0, -1):
        try:
            imageDrawFont = PIL.ImageFont.truetype(
                font='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
                size=int(fontSize * targetW)
            )
        except IOError:
            try:
                imageDrawFont = PIL.ImageFont.truetype(
                    size=int(fontSize * targetW)
                )
            except IOError:
                imageDrawFont = PIL.ImageFont.load_default()
        textW, textH = imageDraw.textsize(title, imageDrawFont)
        if iter != 1 and (textW > targetW * 0.95 or textW < targetW * 0.85):
            fontSize = fontSize * targetW * 0.9 / textW
    titleH = int(math.ceil(textH * 1.25))
    if square and (w != h or (not previouslyAdded or w != targetW or h < titleH)):
        if targetW < h + titleH:
            targetW = h + titleH
        else:
            titleH = targetW - h
    if previouslyAdded and w == targetW and h >= titleH:
        newImage = image.copy()
    else:
        newImage = PIL.Image.new(mode=mode, size=(targetW, h + titleH), color=background)
        newImage.paste(image, (int((targetW - w) / 2), titleH))
    imageDraw = PIL.ImageDraw.Draw(newImage)
    imageDraw.rectangle((0, 0, targetW, titleH), fill=background, outline=None, width=0)
    imageDraw.text(
        xy=(int((targetW - textW) / 2), int((titleH - textH) / 2)),
        text=title,
        fill=textColor,
        font=imageDrawFont)
    return newImage


def redact_topleft_square(image):
    """
    Replace the top left square of an image with black.

    :param image: a PIL image to adjust.
    :returns: an adjusted PIL image.
    """
    mode = 'RGB'
    newImage = image.convert(mode)
    w, h = image.size
    background = PIL.ImageColor.getcolor('#000000', mode)
    imageDraw = PIL.ImageDraw.Draw(newImage)
    imageDraw.rectangle((0, 0, min(w, h), min(w, h)), fill=background, outline=None, width=0)
    return newImage


def get_allow_list():
    """
    Get a string of allowed characters for EasyOCR to find.
    """
    return 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-:&.'


def get_text_from_associated_image(tile_source, label, reader):
    starttime = time.time()
    associated_image, _ = tile_source.getAssociatedImage(label)
    associated_image = PIL.Image.open(io.BytesIO(associated_image))
    logger.info('%s %s size %r', tile_source.item['name'], label, associated_image.size)
    maxSize = 2048 if label == 'macro' else 1024
    if max(associated_image.size) > maxSize:
        associated_image.thumbnail((maxSize, maxSize), PIL.Image.LANCZOS)
    words = {}
    for rotate in [None, PIL.Image.ROTATE_90, PIL.Image.ROTATE_180, PIL.Image.ROTATE_270]:
        if rotate is not None:
            rotated_image = associated_image.transpose(rotate)
        text_results = reader.readtext(
            numpy.asarray(associated_image if rotate is None else rotated_image),
            allowlist=get_allow_list(),
            contrast_ths=0.75,
            adjust_contrast=1.0,
            # This probably isn't useful if we are already trying all rotations
            # rotation_info=[90, 180, 270],
            # Note: batch_size didn't help anything
        )
        for result in text_results:
            # easyocr returns the text box coordinates, text, and confidence
            _, found_text, confidence = result
            result_info = words.get(found_text, {})
            result_count = result_info.get('count', 0) + 1
            result_info['count'] = result_count
            result_avg_conf = result_info.get('average_confidence', 0)
            result_avg_conf = (result_avg_conf * (result_count - 1) + confidence) / result_count
            result_info['average_confidence'] = result_avg_conf
            words[found_text] = result_info
    # Sort so the most confident is first
    words = {k: v for _, k, v in sorted((-v['average_confidence'], k, v) for k, v in words.items())}
    logger.info('Ran OCR on %s %s in %5.3fs', tile_source.item['name'],
                label, time.time() - starttime)
    return words


def get_image_text(item):
    """
    Use OCR to identify and return text on any associated image.

    :param item: a girder item.
    :returns: a list of found text .
    """
    reader = get_reader()
    results = []
    tile_source = ImageItem().tileSource(item)
    image_format = determine_format(tile_source)
    if image_format in ['aperio', 'philips']:
        key = 'label'
    elif image_format == 'hamamatsu':
        key = 'macro'
    results = get_text_from_associated_image(tile_source, key, reader)
    item = ImageItem().setMetadata(item, {f'{key}_ocr': results})
    return results


def refile_image(item, user, tokenId, imageId, uploadInfo=None):
    """
    Refile an item to a new name and folder.

    :param item: the girder item to move.
    :param user: the user authorizing the move.
    :param tokenId: the new folder name.
    :param imageId: the new item name without extension.
    :param uploadInfo: a dictionary of imageIds that contain additional fields.
        If it doesn't exist or the imageId is not present in it, it is not
        used.
    :returns: the modified girder item.
    """
    # if imageId starts with folder key, auto assign a number
    originalImageId = imageId
    if imageId.startswith(TokenOnlyPrefix):
        baseImageId = imageId[len(TokenOnlyPrefix):]
        used = {
            int(entry['name'][len(baseImageId) + 1:].split('.')[0]) for entry in
            Item().find({'name': {'$regex': '^' + re.escape(baseImageId) + r'_[0-9]+\..*'}})}
        nextValue = 1
        while nextValue in used:
            nextValue += 1
        imageId = baseImageId + '_' + str(nextValue)
    ingestFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    ingestFolder = Folder().load(ingestFolderId, force=True, exc=True)
    parentFolder = Folder().findOne({'name': tokenId, 'parentId': ingestFolder['_id']})
    if not parentFolder:
        parentFolder = Folder().createFolder(ingestFolder, tokenId, creator=user)
    newImageName = f'{imageId}.{item["name"].split(".")[-1]}'
    originalName = item['name']
    item['name'] = newImageName
    item = Item().move(item, parentFolder)
    redactList = get_standard_redactions(item, imageId)
    itemMetadata = {
        'redactList': redactList,
    }
    if uploadInfo and originalImageId in uploadInfo:
        itemMetadata['deidUpload'] = uploadInfo[originalImageId]['fields']
    else:
        itemMetadata['deidUpload'] = {}
    itemMetadata['deidUpload']['InputFileName'] = originalName
    item = Item().setMetadata(item, itemMetadata)
    if 'wsi_uploadInfo' in item:
        del item['wsi_uploadInfo']
        item = Item().save(item)
    return item
