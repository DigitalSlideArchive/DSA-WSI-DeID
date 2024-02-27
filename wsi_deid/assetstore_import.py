import os

from girder import logger
from girder.api.rest import getCurrentUser
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.utility.progress import ProgressContext

from . import import_export
from .constants import PluginSettings


def assetstoreImportEvent(event):
    """
    After an assetstore import, check if the import was done within the Unfiled
    folder.  If so, import the data.
    """
    logger.info('Processing assetstore import event')
    check = False
    try:
        params = event.info['returnVal']['params']
        if params['destinationType'] == 'folder':
            folder = Folder().load(params['destinationId'], force=True)
            if import_export.isProjectFolder(folder) == 'unfiled':
                check = True
    except Exception:
        logger.exception('Processing assetstore import event: Failed to check')
        return
    if not check:
        logger.info('Processing assetstore import event: not the unfiled folder')
        return
    logger.info('Processing assetstore import event: will process')
    progress = True
    user = getCurrentUser()
    with ProgressContext(progress, user=user, title='Importing data') as ctx:
        importFromUnfiled(user, ctx)


def assetstoreIngestFindFilesFolder(folder, excelFiles, imageFiles):
    """
    Walk a folder and add likely files to excel and image file lists.

    :param folder: folder to walk
    :param excelFiles: list of items that are probably excel files.
    :param imageFiles: list of items that are probably image files.
    """
    for subfolder in Folder().childFolders(folder, parentType='folder'):
        assetstoreIngestFindFilesFolder(subfolder, excelFiles, imageFiles)
    for item in Folder().childItems(folder):
        _, ext = os.path.splitext(item['name'])
        # skip this item if it has metadata
        if len(item.get('meta', {})):
            continue
        if ext.lower() in {'.xls', '.xlsx', '.csv'} and not item['name'].startswith('~$'):
            if len(list(Item().childFiles(item, limit=1))):
                excelFiles.append(item)
        elif 'largeImage' in item:
            imageFiles.append(item)


def assetstoreIngestFindFiles(importPath):
    """
    Get a list of excel and image files for import.

    :param importPath: the import folder path (ignored).
    :returns: a two tuple of lists of excel items and image items.
    """
    unfiledFolderId = Setting().get(PluginSettings.WSI_DEID_UNFILED_FOLDER)
    unfiledFolder = Folder().load(unfiledFolderId, force=True, exc=True)

    excelFiles = []
    imageFiles = []
    assetstoreIngestFindFilesFolder(unfiledFolder, excelFiles, imageFiles)
    return excelFiles, imageFiles


def importFromUnfiled(user, ctx):
    """
    Walk the unfiled folder.  Collect all excel and image files that haven't
    been processed before, then process them as if they came through the import
    mechanism.

    :param user: the user that started the process.
    :param ctx: A progress context.
    """
    import_export.ingestData(user=user, walkData=assetstoreIngestFindFiles, ctx=ctx)
