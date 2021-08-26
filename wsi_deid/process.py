import base64
import copy
import io
import math
import os
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import pyvips
import re
import xml.etree.ElementTree

from girder_large_image.models.image_item import ImageItem
from large_image.tilesource import dictToEtree
import tifftools

from . import config


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
            redactList['metadata']['internal;openslide;tiff.%s' % key] = {'value': value}
    # Make, Model, Software?
    for key in {'Copyright', 'HostComputer'}:
        tag = tifftools.Tag[key].value
        if tag in ifds[0]['tags']:
            redactList['metadata']['internal;openslide;tiff.%s' % key] = {
                'value': None, 'automatic': True}
    return redactList


def get_standard_redactions_format_aperio(item, tileSource, tiffinfo, title):
    metadata = tileSource.getInternalMetadata() or {}
    redactList = {
        'images': {},
        'metadata': {
            'internal;openslide;aperio.Filename': {'value': title},
            'internal;openslide;aperio.Title': {'value': title},
            'internal;openslide;tiff.Software': {
                'value': get_deid_field(item, metadata.get('openslide', {}).get('tiff.Software'))},
        },
    }
    if metadata['openslide'].get('aperio.Date'):
        redactList['metadata']['internal;openslide;aperio.Date'] = {
            'value': '01/01/' + metadata['openslide']['aperio.Date'][6:]}
    return redactList


def get_standard_redactions_format_hamamatsu(item, tileSource, tiffinfo, title):
    metadata = tileSource.getInternalMetadata() or {}
    redactList = {
        'images': {},
        'metadata': {
            'internal;openslide;hamamatsu.Reference': {'value': title},
            'internal;openslide;tiff.Software': {
                'value': get_deid_field(item, metadata.get('openslide', {}).get('tiff.Software'))},
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
            'internal;xml;PIIM_DP_SCANNER_OPERATOR_ID': {'value': title},
            'internal;xml;PIM_DP_UFS_BARCODE': {'value': title},
            'internal;tiff;software': {
                'value': get_deid_field(item, metadata.get('tiff', {}).get('software'))},
        },
    }
    for key in {'DICOM_DATE_OF_LAST_CALIBRATION'}:
        if metadata['xml'].get(key):
            value = metadata['xml'][key].strip('"')
            if len(value) < 8:
                value = None
            else:
                value = value[:4] + '0101'
            redactList['metadata']['internal;xml;%s' % key] = {'value': value}
    for key in {'DICOM_ACQUISITION_DATETIME'}:
        if metadata['xml'].get(key):
            value = metadata['xml'][key].strip('"')
            if len(value) < 8:
                value = None
            else:
                value = value[:4] + '0101' + value[8:]
            redactList['metadata']['internal;xml;%s' % key] = {'value': value}
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
    if 'label' not in redactList['images'] and not config.getConfig('always_redact_label'):
        try:
            labelImage = PIL.Image.open(io.BytesIO(tileSource.getAssociatedImage('label')[0]))
        except Exception:
            pass
    labelImage = add_title_to_image(labelImage, newTitle, previouslyRedacted)
    macroImage = None
    if ('macro' not in redactList['images'] and config.getConfig('redact_macro_square')):
        try:
            macroImage = PIL.Image.open(io.BytesIO(tileSource.getAssociatedImage('macro')[0]))
            macroImage = redact_topleft_square(macroImage)
        except Exception:
            pass
    format = determine_format(tileSource)
    func = None
    if format is not None:
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
            for key in redactList},
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
    tiffinfo = tifftools.read_tiff(sourcePath)
    ifds = tiffinfo['ifds']
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
    redact_format_aperio_add_image(
        'label', labelImage, ifds, firstAssociatedIdx, tempdir, aperioValues)
    # redact general tiff tags
    redact_tiff_tags(ifds, redactList, title)
    add_deid_metadata(item, ifds)
    outputPath = os.path.join(tempdir, 'aperio.svs')
    tifftools.write_tiff(ifds, outputPath)
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
    sourceLensTag = tifftools.Tag.NDPI_SOURCELENS.value
    for key in redactList['images']:
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
    # redact images from xmldict
    images = philips_tag(xmldict, 'PIM_DP_SCANNED_IMAGES')
    for key, pkey in [('macro', 'MACROIMAGE'), ('label', 'LABELIMAGE')]:
        if key in redactList['images'] and images:
            tag = philips_tag(
                xmldict, 'PIM_DP_SCANNED_IMAGES', None, 'PIM_DP_IMAGE_TYPE', pkey)
            if tag:
                tag[-1][0].pop(tag[-1][1])
    # redact images from ifds
    ifds = [ifd for ifd in ifds
            if ifd['tags'].get(tifftools.Tag.ImageDescription.value, {}).get(
                'data', '').split()[0].lower() not in redactList['images']]

    redactList = copy.copy(redactList)
    redactList['metadata']['internal;xml;PIIM_DP_SCANNER_OPERATOR_ID'] = {'value': title}
    redactList['metadata']['internal;xml;PIM_DP_UFS_BARCODE'] = {'value': title}
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
    # Insert label image
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
    tag = philips_tag(xmldict, 'PIM_DP_SCANNED_IMAGES')
    redact_format_philips_replace_macro(
        macroImage, ifds, tempdir, tag[2][tag[3]]['Array']['DataObject'])
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

    :param macrosImage: a PIL image or None to not change.
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
