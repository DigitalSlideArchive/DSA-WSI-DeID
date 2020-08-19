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
            raise Exception('Failed to generated redacted file')


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
    isCommonCompression = tiffSource._tiffDirectories[-1]._tiffInfo['compression'] in {
        libtiff_ctypes.COMPRESSION_LZW,
        libtiff_ctypes.COMPRESSION_JPEG,
        libtiff_ctypes.COMPRESSION_PACKBITS,
        libtiff_ctypes.COMPRESSION_DEFLATE,
    }
    associatedImages = tileSource.getAssociatedImagesList()
    if mainImageDir != [d + (1 if d and 'thumbnail' in associatedImages else 0)
                        for d in range(len(mainImageDir))]:
        raise Exception('Aperio TIFF directories are not in the expected order.')
    sourcePath = pyramidPath = tileSource._getLargeImagePath()
    outputPath = os.path.join(tempdir, 'aperio.svs')
    commandList = []
    tiffcpCompression = ['-c', 'jpeg:r:%d' % quality]
    if not isCommonCompression:
        pyramidPath = os.path.join(tempdir, 'vips_pyramid.tiff')
        commandList.append([
            'vips', 'tiffsave', '--bigtiff', '--pyramid', '--tile',
            '--tile-width', str(tileSource.tileWidth),
            '--tile-height', str(tileSource.tileHeight),
            # Unfortunately, we have to ask tiffcp to compress, so don't do it
            # here.  This uses more disk space, but is faster and avoids some
            # potential artifacts.
            # '--compression', 'jpeg', '--Q', str(quality),
            sourcePath, pyramidPath])
    commandList.extend([
        ['tiffcp', '-8', '-L'] + tiffcpCompression + [pyramidPath + ',0', outputPath],
        ['tiffset', '-d', '0', '-s', '270', imageDescription, outputPath],
    ])
    tiffFile = libtiff_ctypes.TIFF.open(sourcePath.encode('utf8'))
    nextDir = 1
    if 'thumbnail' in associatedImages and 'thumbnail' not in redactList['images']:
        tiffFile.SetDirectory(1)
        thumbnailComment = tiffFile.GetField('imagedescription').decode('utf8')
        thumbnailDescription = '|'.join(thumbnailComment.split('|', 1)[0:1] + aperioValues[1:])
        commandList.extend([
            ['tiffcp', '-8', '-L', '-a', '-c', 'jpeg:%d' % quality, sourcePath + ',1', outputPath],
            ['tiffset', '-d', '1', '-s', '270', thumbnailDescription, outputPath],
        ])
        nextDir += 1
    for dirPos in range(len(tiffSource._tiffDirectories) - 2, -1, -1):
        if tiffSource._tiffDirectories[dirPos]:
            dir = pyramiddir = tiffSource._tiffDirectories[dirPos]._directoryNum
            if not isCommonCompression:
                pyramiddir = len(tiffSource._tiffDirectories) - 1 - dirPos
            tiffFile.SetDirectory(dir)
            subDescription = tiffFile.GetField('imagedescription').decode('utf8')
            commandList.append([
                'tiffcp', '-8', '-L', '-a'] + tiffcpCompression + [
                    '%s,%d' % (pyramidPath, pyramiddir), outputPath])
            if not isCommonCompression:
                commandList.append([
                    'tiffset', '-d', str(nextDir), '-s', '270', subDescription, outputPath])
            nextDir += 1
    labelPath = os.path.join(tempdir, 'label.tiff')
    labelImage.save(labelPath, format='tiff', compression='jpeg', quality=quality)
    labelDescription = aperioValues[0].split('\n', 1)[1] + '\nlabel %dx%d' % (
        labelImage.width, labelImage.height)
    commandList.extend([
        ['tiffcp', '-8', '-L', '-a', labelPath, outputPath],
        ['tiffset', '-d', str(nextDir), '-s', '270', labelDescription, outputPath],
    ])
    nextDir += 1
    readDir = mainImageDir[-1] + 1
    if 'thumbnail' in associatedImages and readDir == 1:
        readDir += 1
    while tiffFile.SetDirectory(readDir):
        comment = tiffFile.GetField('imagedescription').decode('utf8')
        tag = comment.split('\n', 1)[-1].split()[0].strip()
        if tag in associatedImages and tag not in redactList['images'] and tag != 'label':
            commandList.append(
                ['tiffcp', '-8', '-L', '-a', sourcePath + ',%d' % readDir, outputPath])
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
