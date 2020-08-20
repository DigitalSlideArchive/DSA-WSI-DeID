from io import BytesIO
from libtiff import libtiff_ctypes
import math
import os
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import subprocess

from girder import logger
from girder_large_image.models.image_item import ImageItem
import large_image_source_tiff.girder_source


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
    for key in ('aperio.Title', ):
        if redactList['metadata'].get(key):
            return redactList['metadata'].get(key)
    # TODO: Pull from appropriate 'meta' if not otherwise present
    return title


def determine_format(tileSource):
    metadata = tileSource.getInternalMetadata() or {}
    if tileSource.name == 'openslide':
        if 'aperio' in metadata.get('openslide', {}).get('openslide.comment', '').lower():
            return 'aperio'
    return None


def execute_command_list(commandList, tempdir=None):
    """
    Run a series of commands.  Each should be in the list format.

    :param commandList: a list of command arrays.
    :param tempdir: an optional temporary directory set in the command's
        environment.
    """
    env = dict(os.environ).copy()
    if tempdir:
        env['TMPDIR'] = tempdir
    for idx, cmd in enumerate(commandList):
        logger.info('Processing %d/%d: %s' % (
            idx + 1, len(commandList), subprocess.list2cmdline(cmd)))
        try:
            subprocess.check_call(cmd, env=env)
        except Exception:
            logger.exception('Failed to process command')
            raise Exception('Failed to generate redacted file')


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
    Redact aperio files.  If the file is compressed with a propriety
    compression, this recompresses it with JPEG compression via vips.

    :param item: the item to redact.
    :param tempdir: a directory for work files and the final result.
    :param redactList: the list of redactions (see get_redact_list).
    :param title: the new title for the item.
    :param labelImage: a PIL image with a new label image.
    :returns: (filepath, mimetype) The redacted filepath in the tempdir and
        its mimetype.
    """
    quality = 90
    tileSource = ImageItem().tileSource(item)
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
    sourcePath = tileSource._getLargeImagePath()
    outputPath = os.path.join(tempdir, 'aperio.svs')
    splitPath = os.path.join(tempdir, 'split')  # names are splitaaa.tif
    header = open(sourcePath, 'rb').read(4)
    # This actually needs to be the status generated by tiffsplit.  tiffsplit
    # has some unfortunate properties -- converting some files to small tiff,
    # dropping unknown tags.  We probably want to replace it.  For now, set
    # bigtiff if the source file is >= 4Gb; this probably will still fail
    # bigtiff = b'\x2b' in header
    bigtiff = os.path.getsize(sourcePath) >= 2**32
    bigendian = header[:2] == b'MM'
    labelPath = os.path.join(tempdir, 'labelsrc.tiff')
    labelPathDest = os.path.join(tempdir, 'labeldest.tiff')
    labelImage.save(labelPath, format='tiff', compression='lzw')
    concat = ['tiffconcat.py', '--output', outputPath, split_name(splitPath, 0)]
    commandList = [
        ['tiffsplit', sourcePath, splitPath],
        ['tiffcp', '-s', '-r', '256'] + (['-8'] if bigtiff else []) + [
            'B' if bigendian else '-L', '-c', 'jpeg:%d' % quality, labelPath, labelPathDest],
        concat,
        ['tiffset', '-d', '0', '-s', '270', imageDescription, outputPath],
    ]
    tiffFile = libtiff_ctypes.TIFF.open(sourcePath.encode('utf8'))
    nextDir = 1
    if 'thumbnail' in associatedImages and 'thumbnail' not in redactList['images']:
        concat.append(split_name(splitPath, 1))
        tiffFile.SetDirectory(1)
        thumbnailComment = tiffFile.GetField('imagedescription').decode('utf8')
        thumbnailDescription = '|'.join(thumbnailComment.split('|', 1)[0:1] + aperioValues[1:])
        commandList.append([
            'tiffset', '-d', '1', '-s', '270', thumbnailDescription, outputPath])
        nextDir += 1
    for dirPos in range(len(tiffSource._tiffDirectories) - 2, -1, -1):
        if tiffSource._tiffDirectories[dirPos]:
            dir = tiffSource._tiffDirectories[dirPos]._directoryNum
            concat.append(split_name(splitPath, dir))
            nextDir += 1
    labelDescription = aperioValues[0].split('\n', 1)[1] + '\nlabel %dx%d' % (
        labelImage.width, labelImage.height)
    concat.append(labelPathDest)
    commandList.append([
        'tiffset', '-d', str(nextDir), '-s', '270', labelDescription, outputPath])
    nextDir += 1
    readDir = mainImageDir[-1] + 1
    if 'thumbnail' in associatedImages and readDir == 1:
        readDir += 1
    while tiffFile.SetDirectory(readDir):
        tag = None
        comment = tiffFile.GetField('imagedescription')
        if comment is not None:
            comment = comment.decode('utf8')
            tag = comment.split('\n', 1)[-1].split()[0].strip()
        if tag in associatedImages and tag not in redactList['images'] and tag != 'label':
            concat.append(split_name(splitPath, readDir))
        readDir += 1
    execute_command_list(commandList, tempdir)
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
