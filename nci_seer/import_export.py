import os
import pandas as pd

from girder.models.assetstore import Assetstore
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting

from .constants import PluginSettings


def readExcelData(filepath):
    """
    Read in the data from excel, while attempting to be forgiving about
    the exact location of the header row.

    :param filepath: path to the excel file.
    :returns: a pandas dataframe of the excel data rows.
    """
    potential_header = 0
    df = pd.read_excel(filepath, header=potential_header)
    rows = df.shape[0]
    while potential_header < rows:
        # When the columns include TokenID, ImageID, this is the Header row.
        if all(key in df.columns for key in {'TokenID', 'ImageID', 'ScannedFileName'}):
            return df
        potential_header += 1
        df = pd.read_excel(filepath, header=potential_header)
    raise ValueError(f'Samples excel file {filepath} lacks a header row')


def readExcelFiles(filelist, ctx):
    """
    Read each excel file, use pandas to parse it.  Collect the results, where,
    if a file is stored twice, the value from the newest excel file wins.

    :param filelist: a list of excel or csv file paths.
    :param ctx: a process context.
    :returns: a dictionary with scanned file names as the keys.  Each entry
        contains an ImageID, TokenID, name (the scanned file name), excel (the
        path from the excel file), and timestamp (the mtime of the excel file).
    """
    manifest = {}
    for filepath in filelist:
        ctx.update(message='Reading %s' % os.path.basename(filepath))
        df = readExcelData(filepath)
        timestamp = os.path.getmtime(filepath)
        for row in df.itertuples():
            name = row.ScannedFileName
            if name not in manifest or timestamp > manifest[name]['timestamp']:
                manifest[name] = {
                    'timestamp': timestamp,
                    'ImageID': row.ImageID,
                    'TokenID': row.TokenID,
                    'name': name,
                    'excel': filepath,
                }
    return manifest


def ingestOneItem(importFolder, imagePath, record, ctx, user):
    stat = os.stat(imagePath)
    existing = File().findOne({'path': imagePath, 'imported': True})
    if existing:
        if existing['size'] == stat.st_size:
            return
        item = Item().load(existing['itemId'], force=True)
        # TODO: move item somewhere; for now, delete it
        ctx.update(message='Removing existing %s since the size has changed' % imagePath)
        Item().remove(item)
    parentFolder = Folder().findOne({'name': record['TokenID'], 'parentId': importFolder['_id']})
    if not parentFolder:
        parentFolder = Folder().createFolder(importFolder, record['TokenID'], creator=user)
    # TODO: (a) use the getTargetAssetstore method from Upload(), (b) ensure
    # that the assetstore is a filesystem assestore.
    assetstore = Assetstore().getCurrent()
    name = record['ImageID'] + os.path.splitext(record['name'])[1]
    mimeType = 'image/tiff'
    item = Item().createItem(name=name, creator=user, folder=parentFolder)
    file = File().createFile(
        name=record['name'], creator=user, item=item, reuseExisting=False,
        assetstore=assetstore, mimeType=mimeType, size=stat.st_size,
        saveFile=False)
    file['path'] = os.path.abspath(os.path.expanduser(imagePath))
    file['mtime'] = stat.st_mtime
    file['imported'] = True
    file = File().save(file)
    # TODO: set item metadata / default redact data
    ctx.update(message='Imported %s' % name)


def ingestData(ctx, user=None):
    """
    Scan the import folder for image and excel files.  For each excel file,
    extract the appropriate data.  For each file listed in an excel file,
    if the import path is already in the system and has the same length as the
    file, do nothing.  If the length has changed, remove the existing item.
    For each listed file that is now not in the system, add it to the import
    directory with an appropriate name.  Add each listed file that is not in
    the system to a report; add each file present that is not listed to a
    report.  Emit the report.

    :param ctx: a progress context.
    :param user: the user triggering this.
    """
    importPath = Setting().get(PluginSettings.NCISEER_IMPORT_PATH)
    importFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    if not importPath or not importFolderId:
        raise Exception('Import path and/or folder not specified.')
    importFolder = Folder().load(importFolderId, force=True, exc=True)
    ctx.update(message='Scanning import folder')
    excelFiles = []
    imageFiles = []
    for base, _dirs, files in os.walk(importPath):
        for file in files:
            filePath = os.path.join(importPath, base, file)
            _, ext = os.path.splitext(file)
            if ext.lower() in {'.xls', '.xlsx'}:
                excelFiles.append(filePath)
            # ignore some extensions
            elif ext.lower() not in {'.zip', '.txt', '.xml'}:
                imageFiles.append(filePath)
    if not len(excelFiles):
        raise Exception('Failed to find any excel files in import directory.')
    if not len(imageFiles):
        raise Exception('Failed to find any image files in import directory.')
    manifest = readExcelFiles(excelFiles, ctx)
    missingImages = []
    for record in manifest.values():
        imagePath = os.path.join(os.path.dirname(record['excel']), record['name'])
        if imagePath not in imageFiles:
            imagePath = None
            for testPath in imageFiles:
                if os.path.basename(testPath) == record['name']:
                    imagePath = testPath
                    break
        if imagePath is None:
            missingImages.append(record)
            continue
        imageFiles.remove(imagePath)
        ingestOneItem(importFolder, imagePath, record, ctx, user)
    # imageFiles are images that have no manifest record
    # missingFiles are images listed in the manifest that are not present
    # TODO: emit a report
