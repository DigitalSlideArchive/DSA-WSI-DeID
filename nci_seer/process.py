import base64
import copy
from io import BytesIO
import math
import os
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import xml.etree.ElementTree

from girder_large_image.models.image_item import ImageItem
from large_image.tilesource import dictToEtree
import large_image_source_tiff.girder_source

from . import tifftools


def get_redact_list(item):
    """
    Get the redaction list, ensuring that the images and metadata
    dictionaries exist.

    :param item: a Girder item.
    :returns: the redactList object.
    """
    redactList = item.get('meta', {}).get('redactList', {})
    redactList.setdefault('images', {})
    redactList.setdefault('metadata', {})
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
            'aperio.Title', 'hamamatsu.Reference',
            'PIIM_DP_SCANNER_OPERATOR_ID', 'PIM_DP_UFS_BARCODE'}:
        if redactList['metadata'].get(key):
            return redactList['metadata'].get(key)
    # TODO: Pull from appropriate 'meta' if not otherwise present
    return title


def determine_format(tileSource):
    metadata = tileSource.getInternalMetadata() or {}
    if tileSource.name == 'openslide':
        if metadata.get('openslide', {}).get('openslide.vendor') in ('aperio', 'hamamatsu'):
            return metadata['openslide']['openslide.vendor']
    if 'xml' in metadata and any(k.startswith('PIM_DP_') for k in metadata['xml']):
        return 'philips'
    return None


def redact_item(item, tempdir):
    """
    Redact a Girder iitem.  Based on the redact metadata, determine what
    redactions are necessary and perform them.

    :param item: a Girder large_image item.  The file in this item will be
        replaced with the redacted version.  The caller should copy the item
        before running this script, as otherwise the original file may be
        removed from the system.
    :param tempdir: a temporary directory to put all work files and the final
        result.
    :returns: (filepath, mimetype): a generated filepath and its mimetype.
        The filepath should end in the appropriate extension, but its name is
        not important.
    """
    previouslyRedacted = bool(item.get('meta', {}).get('redacted'))
    redactList = get_redact_list(item)
    newTitle = get_generated_title(item)
    tileSource = ImageItem().tileSource(item)
    labelImage = None
    if 'label' not in redactList['images']:
        try:
            labelImage = PIL.Image.open(BytesIO(tileSource.getAssociatedImage('label')[0]))
        except Exception:
            pass
    labelImage = add_title_to_image(labelImage, newTitle, previouslyRedacted)
    format = determine_format(tileSource)
    func = None
    if format is not None:
        func = globals().get('redact_format_' + format)
    if func is None:
        raise Exception('Cannot redact this format.')
    file, mimetype = func(item, tempdir, redactList, newTitle, labelImage)
    return file, mimetype


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
            value = redactList['metadata'].get(redactKey, value)
            if value is not None and '|' not in value:
                key = fullkey.split('.', 1)[1]
                aperioDict[key] = value
    # Required values
    aperioDict.update({
        'Filename': title,
        'Title': title,
    })
    aperioValues = [aperioHeader] + ['%s = %s' % (k, v) for k, v in sorted(aperioDict.items())]
    return aperioValues


def split_name(base, number):
    """
    Given a base name and a 0-based number, return the name that tiffsplit uses
    for a specific directory number.

    :param base: base path name passed to tiffsplit for the prefix.
    :param number: 0-based directory number.
    :returns: the split file path name.
    """
    let = 'abcdefghijklmnopqrstuvwxyz'
    return base + let[number // 26 // 26] + let[(number // 26) % 26] + let[number % 26] + '.tif'


def redact_format_aperio(item, tempdir, redactList, title, labelImage):
    """
    Redact aperio files.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
    :returns: (filepath, mimetype) The redacted filepath in the tempdir and
        its mimetype.
    """
    tileSource = ImageItem().tileSource(item)
    sourcePath = tileSource._getLargeImagePath()
    tiffinfo = tifftools.read_tiff(sourcePath)
    ifds = tiffinfo['ifds']
    aperioValues = aperio_value_list(item, redactList, title)
    imageDescription = '|'.join(aperioValues)
    # We expect aperio to have the full resolution image in directory 0, the
    # thumbnail in directory 1, lower resolutions starting in 2, and macro and
    # label images in other directories.  Confirm this -- our tiff reader will
    # report the directories used for the full resolution.
    tiffSource = large_image_source_tiff.girder_source.TiffGirderTileSource(item)
    mainImageDir = [dir._directoryNum for dir in tiffSource._tiffDirectories[::-1] if dir]
    associatedImages = tileSource.getAssociatedImagesList()
    if mainImageDir != [d + (1 if d and 'thumbnail' in associatedImages else 0)
                        for d in range(len(mainImageDir))]:
        raise Exception('Aperio TIFF directories are not in the expected order.')
    # Set new image description
    ifds[0]['tags'][tifftools.name_to_tag('IMAGEDESCRIPTION')] = {
        'type': tifftools.name_to_datatype('ASCII'),
        'data': imageDescription
    }
    # redact or adjust thumbnail
    if 'thumbnail' in associatedImages:
        if 'thumbnail' in redactList['images']:
            ifds.pop(1)
        else:
            thumbnailComment = ifds[1]['tags'][tifftools.name_to_tag('IMAGEDESCRIPTION')]['data']
            thumbnailDescription = '|'.join(thumbnailComment.split('|', 1)[0:1] + aperioValues[1:])
            ifds[1]['tags'][tifftools.name_to_tag('IMAGEDESCRIPTION')][
                'data'] = thumbnailDescription
    # redact other images
    for idx in range(len(ifds) - 1, 0, -1):
        key = ifds[idx]['tags'].get(tifftools.name_to_tag('IMAGEDESCRIPTION'), {}).get(
            'data', '').split('\n', 1)[-1].strip().split()
        if len(key) and key[0].lower():
            desc = key[0].lower()
            if desc in redactList['images'] or desc == 'label':
                ifds.pop(idx)
    # Add back label image
    labelPath = os.path.join(tempdir, 'label.tiff')
    labelImage.save(labelPath, format='tiff', compression='jpeg', quality=90)
    labelinfo = tifftools.read_tiff(labelPath)
    labelDescription = aperioValues[0].split('\n', 1)[1] + '\nlabel %dx%d' % (
        labelImage.width, labelImage.height)
    labelinfo['ifds'][0]['tags'][tifftools.name_to_tag('IMAGEDESCRIPTION')] = {
        'type': tifftools.name_to_datatype('ASCII'),
        'data': labelDescription
    }
    ifds.extend(labelinfo['ifds'])
    # redact general tiff tags
    redact_tiff_tags(ifds, redactList, title)
    outputPath = os.path.join(tempdir, 'aperio.svs')
    tifftools.tiff_write(ifds, outputPath)
    return outputPath, 'image/tiff'


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
        tag = tifftools.name_to_tag(key.rsplit(';tiff.', 1)[-1])
        if tag:
            redactedTags[tag] = value
    for titleKey in {'NDPI_REFERENCE', }:
        redactedTags[tifftools.name_to_tag(titleKey)] = title
    for ifd in ifds:
        # convert to a list since we may mutage the tag dictionary
        for tag, taginfo in list(ifd['tags'].items()):
            if tag in redactedTags:
                if redactedTags[tag] is None:
                    del ifd['tags'][tag]
                else:
                    taginfo['type'] = tifftools.name_to_datatype('ASCII')
                    taginfo['data'] = redactedTags[tag]


def redact_format_hamamatsu(item, tempdir, redactList, title, labelImage):
    """
    Redact hamamatsu files.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
    :returns: (filepath, mimetype) The redacted filepath in the tempdir and
        its mimetype.
    """
    tileSource = ImageItem().tileSource(item)
    sourcePath = tileSource._getLargeImagePath()
    tiffinfo = tifftools.read_tiff(sourcePath)
    ifds = tiffinfo['ifds']
    sourceLensTag = tifftools.name_to_tag('NDPI_SOURCELENS')
    if 'macro' in redactList['images']:
        ifds = [ifd for ifd in ifds
                if sourceLensTag not in ifd['tags'] or
                ifd['tags'][sourceLensTag]['data'][0] > 0]
    redact_tiff_tags(ifds, redactList, title)
    propertyTag = tifftools.name_to_tag('NDPI_PROPERTY_MAP')
    propertyList = ifds[0]['tags'][propertyTag]['data'].replace('\r', '\n').split('\n')
    ndpiProperties = {p.split('=')[0]: p.split('=', 1)[1] for p in propertyList if '=' in p}
    for fullkey, value in redactList['metadata'].items():
        if fullkey.startswith('internal;openslide;hamamatsu.'):
            key = fullkey.split('internal;openslide;hamamatsu.', 1)[1]
            if key in ndpiProperties:
                if value is None:
                    del ndpiProperties[key]
                else:
                    ndpiProperties[key] = value
    propertyList = ['%s=%s\r\n' % (k, v) for k, v in ndpiProperties.items()]
    propertyMap = ''.join(propertyList)
    for ifd in ifds:
        ifd['tags'][tifftools.name_to_tag('NDPI_REFERENCE')] = {
            'type': tifftools.name_to_datatype('ASCII'),
            'data': title,
        }
        ifd['tags'][propertyTag] = {
            'type': tifftools.name_to_datatype('ASCII'),
            'data': propertyMap,
        }
    outputPath = os.path.join(tempdir, 'hamamatsu.ndpi')
    tifftools.tiff_write(ifds, outputPath)
    return outputPath, 'image/tiff'


PhilipsTagElements = {  # Group, Element
    'DICOM_ACQUISITION_DATETIME': ('0x0008', '0x002A'),
    'DICOM_DATE_OF_LAST_CALIBRATION': ('0x0018', '0x1200'),
    'DICOM_DEVICE_SERIAL_NUMBER': ('0x0018', '0x1000'),
    'DICOM_MANUFACTURER': ('0x0008', '0x0070'),
    'DICOM_MANUFACTURERS_MODEL_NAME': ('0x0008', '0x1090'),
    'DICOM_SOFTWARE_VERSIONS': ('0x0018', '0x1020'),
    'DICOM_TIME_OF_LAST_CALIBRATION': ('0x0018', '0x1201'),
    'PIIM_DP_SCANNER_CALIBRATION_STATUS': ('0x101D', '0x100A'),
    'PIIM_DP_SCANNER_OPERATOR_ID': ('0x101D', '0x1009'),
    'PIIM_DP_SCANNER_RACK_NUMBER': ('0x101D', '0x1007'),
    'PIIM_DP_SCANNER_SLOT_NUMBER': ('0x101D', '0x1008'),
    'PIM_DP_SCANNER_RACK_PRIORITY': ('0x301D', '0x1010'),
    'PIM_DP_UFS_BARCODE': ('0x301D', '0x1002'),
    'PIM_DP_UFS_INTERFACE_VERSION': ('0x301D', '0x1001'),
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


def redact_format_philips(item, tempdir, redactList, title, labelImage):
    """
    Redact philips files.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
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
            if ifd['tags'].get(tifftools.name_to_tag('IMAGEDESCRIPTION'), {}).get(
                'data', '').split()[0].lower() not in redactList['images']]

    redactList = copy.copy(redactList)
    redactList['metadata']['internal;xml;PIIM_DP_SCANNER_OPERATOR_ID'] = title
    redactList['metadata']['internal;xml;PIM_DP_UFS_BARCODE'] = title
    # redact general tiff tags
    redact_tiff_tags(ifds, redactList, title)
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
                'PMSVR': 'IString',
                'text': value,
            }
            plist.insert(0, entry)
    # Insert label image
    labelPath = os.path.join(tempdir, 'label.tiff')
    labelImage.save(labelPath, format='tiff', compression='jpeg', quality=90)
    labelinfo = tifftools.read_tiff(labelPath)
    labelinfo['ifds'][0]['tags'][tifftools.name_to_tag('IMAGEDESCRIPTION')] = {
        'type': tifftools.name_to_datatype('ASCII'),
        'data': 'Label'
    }
    ifds.extend(labelinfo['ifds'])
    jpeg = BytesIO()
    labelImage.save(jpeg, format='jpeg', quality=90)
    tag = philips_tag(xmldict, 'PIM_DP_SCANNED_IMAGES')
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
    ifds[0]['tags'][tifftools.name_to_tag('IMAGEDESCRIPTION')] = {
        'type': tifftools.name_to_datatype('ASCII'),
        'data': xml.etree.ElementTree.tostring(
            dictToEtree(xmldict), encoding='utf8', method='xml').decode(),
    }
    outputPath = os.path.join(tempdir, 'philips.tiff')
    tifftools.tiff_write(ifds, outputPath)
    return outputPath, 'image/tiff'


def add_title_to_image(image, title, previouslyAdded=False, minWidth=384,
                       background='#000000', textColor='#ffffff'):
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
