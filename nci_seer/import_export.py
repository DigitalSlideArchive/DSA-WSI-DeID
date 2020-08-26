import datetime
import os
import pandas as pd
import shutil

from girder.models.assetstore import Assetstore
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting

from girder_large_image.models.image_item import ImageItem

from . import process
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
            if not name or not row.ImageID or not row.TokenID:
                continue
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
    status = 'added'
    stat = os.stat(imagePath)
    existing = File().findOne({'path': imagePath, 'imported': True})
    if existing:
        if existing['size'] == stat.st_size:
            return 'present'
        item = Item().load(existing['itemId'], force=True)
        # TODO: move item somewhere; for now, delete it
        ctx.update(message='Removing existing %s since the size has changed' % imagePath)
        Item().remove(item)
        status = 'replaced'
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
    # Reload the item as it will have changed
    item = Item().load(item['_id'], force=True)
    redactList = process.get_standard_redactions(item, record['ImageID'])
    item = Item().setMetadata(item, {'redactList': redactList})
    ctx.update(message='Imported %s' % name)
    return status


def ingestData(ctx, user=None):  # noqa
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
    report = []
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
            status = 'missing'
            report.append({'record': record, 'status': status})
            continue
        imageFiles.remove(imagePath)
        status = ingestOneItem(importFolder, imagePath, record, ctx, user)
        report.append({'record': record, 'status': status, 'path': imagePath})
    # imageFiles are images that have no manifest record
    for image in imageFiles:
        status = 'unlisted'
        report.append({'record': None, 'status': status, 'path': image})
    # TODO: emit a report
    return reportSummary(report)


def reportSummary(report):
    result = {}
    for entry in report:
        result.setdefault(entry['status'], 0)
        result[entry['status']] += 1
    return result


def exportItems(ctx, user=None, all=False):
    """
    Export all or all recent items in the Finished directory.  Mark each
    exported item as having been exported.

    :param ctx: a progress context.
    :param user: the user triggering this.
    :param all: True to export all items.  False to only export items that have
        not been previously exported.
    """
    from . import __version__

    exportPath = Setting().get(PluginSettings.NCISEER_EXPORT_PATH)
    exportFolderId = Setting().get(PluginSettings.HUI_FINISHED_FOLDER)
    if not exportPath or not exportFolderId:
        raise Exception('Export path and/or finished folder not specified.')
    exportFolder = Folder().load(exportFolderId, force=True, exc=True)
    report = []
    for filepath, file in Folder().fileList(exportFolder, user, data=False):
        item = Item().load(file['itemId'], force=True, exc=True)
        try:
            tileSource = ImageItem().tileSource(item)
        except Exception:
            continue
        sourcePath = tileSource._getLargeImagePath()
        if not all and item.get('meta', {}).get('nciseerExported'):
            continue
        filepath = filepath.split(os.path.sep, 1)[1]
        ctx.update(message='Exporting %s' % filepath)
        destPath = os.path.join(exportPath, filepath)
        destFolder = os.path.dirname(destPath)
        if os.path.exists(destPath):
            if os.path.getsize(destPath) == file['size']:
                report.append({'item': item, 'status': 'present'})
            else:
                report.append({'item': item, 'status': 'different'})
        else:
            os.makedirs(destFolder, exist_ok=True)
            shutil.copy2(sourcePath, destPath)
            exportedRecord = item.get('meta', {}).get('nciseerExported', [])
            exportedRecord.append({
                'time': datetime.datetime.utcnow().isoformat(),
                'user': str(user['_id']) if user else None,
                'version': __version__,
            })
            item = Item().setMetadata(item, {'nciseerExported': exportedRecord})
            report.append({'item': item, 'status': 'export'})
    # TODO: emit a report
    return reportSummary(report)
