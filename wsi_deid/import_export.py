import datetime
import json
import os
import shutil
import subprocess
import tempfile
import time

import jsonschema
import magic
import openpyxl
import pandas as pd
import paramiko
from girder import logger
from girder.models.assetstore import Assetstore
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.upload import Upload
from girder_jobs.models.job import Job, JobStatus
from girder_large_image.models.image_item import ImageItem

from . import config, process
from .constants import (ExportResult, PluginSettings, ProjectFolders, SftpMode,
                        SystemRedactedReason, TokenOnlyPrefix)

XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
EXPORT_HISTORY_KEY = 'wsi_deidExported'
SFTP_HISTORY_KEY = 'wsi_deidExportedSftp'

SCHEMA_FILE_PATH = os.path.join(os.path.dirname(__file__), 'schema', 'importManifestSchema.json')


def readExcelData(filepathOrFptr):
    """
    Read in the data from excel, while attempting to be forgiving about
    the exact location of the header row.

    :param filepath: path to the excel file.
    :returns: a pandas dataframe of the excel data rows.
    :returns: the header row number.
    """
    folderNameField = config.getConfig('folder_name_field', 'TokenID')
    imageNameField = config.getConfig('image_name_field', 'ImageID')
    validateImageIDField = config.getConfig('validate_image_id_field', True)
    potential_header = 0
    reader = pd.read_csv
    ispath = not hasattr(filepathOrFptr, 'seek')
    if ispath:
        filepath = filepathOrFptr
        mimetype = magic.from_file(filepath, mime=True)
    else:
        fptr = filepathOrFptr
        mimetype = magic.from_buffer(fptr.read(16384), mime=True)
        fptr.seek(0)
    if 'excel' in mimetype or 'openxmlformats' in mimetype:
        reader = pd.read_excel
    df = reader(filepathOrFptr, header=potential_header, dtype=str)
    df.rename(columns=lambda x: x.strip() if isinstance(x, str) else x, inplace=True)
    rows = df.shape[0]
    while potential_header < rows:
        # When the columns include TokenID, ImageID, this is the Header row.
        if folderNameField in df.columns and imageNameField in df.columns:
            return df, potential_header
        # only one of the fields is required if we aren't validating them
        # together
        if not validateImageIDField and folderNameField in df.columns:
            return df, potential_header
        potential_header += 1
        if not ispath:
            fptr.seek(0)
        df = reader(filepathOrFptr, header=potential_header, dtype=str)
        df.rename(columns=lambda x: x.strip() if isinstance(x, str) else x, inplace=True)
    err = (f'Was expecting columns named {folderNameField} and {imageNameField}.'
           if validateImageIDField else
           f'Was expecting a column named {folderNameField}.')
    raise ValueError(f'Excel file {filepath if ispath else "-"} lacks a header row.  ' + err)


def validateDataRow(validator, row, rowNumber, df):
    """
    Validate a row from a dataframe with a jsonschema validator.

    :param validator: a jsonschema validator.
    :param row: a dictionary of row information from the dataframe excluding
        the Index.
    :param rowNumber: the 1-based row number within the file for error
        reporting.
    :param df: the pandas dataframe.  Used to determine column number.
    :returns: None for no errors, otherwise a list of error messages.
    """
    folderNameField = config.getConfig('folder_name_field', 'TokenID')
    imageNameField = config.getConfig('image_name_field', 'ImageID')
    validateImageIDField = config.getConfig('validate_image_id_field', True)
    if validator.is_valid(row):
        return
    errors = []
    for error in validator.iter_errors(row):
        try:
            columnName = error.path[0]
            columnNumber = df.columns.get_loc(columnName)
            cellName = openpyxl.utils.cell.get_column_letter(columnNumber + 1) + str(rowNumber)
            errorMsg = f'Invalid {columnName} in {cellName}'
        except Exception:
            errorMsg = f'Invalid row {rowNumber} ({error.message})'
            columnNumber = None
        errors.append(errorMsg)
    if validateImageIDField and row[imageNameField] != '%s_%s_%s' % (
            row[folderNameField], row['Proc_Seq'], row['Slide_ID']):
        errors.append(
            f'Invalid ImageID in row {rowNumber}; not composed of TokenID, Proc_Seq, and Slide_ID')
    return errors


def getSchema():
    """
    Return a jsonschema.

    :returns: an object that can be passed to the jsonschema validator.
    """
    schemaFolderId = Setting().get(PluginSettings.WSI_DEID_SCHEMA_FOLDER)
    mergedSchema = {'$schema': 'http://json-schema.org/draft-07/schema', 'oneOf': []}

    if schemaFolderId:
        schemaFolder = Folder().load(schemaFolderId, force=True)
        if schemaFolder:
            max_files = 1000
            for item in Folder().childItems(schemaFolder, limit=max_files):
                if len(list(Item().childFiles(item, limit=2))) == 1:
                    if len(list(Item().childFiles(item, limit=2))) == 1:
                        file = next(Item().childFiles(item, limit=1))
                        if file['size'] < 2e+6:
                            try:
                                currentObject = json.load(File().open(file))
                                if 'properties' in currentObject:
                                    mergedSchema['oneOf'].append(currentObject)
                            except Exception:
                                pass
    if not len(mergedSchema['oneOf']):
        return json.load(open(SCHEMA_FILE_PATH))
    if len(mergedSchema['oneOf']) == 1:
        return mergedSchema['oneOf'][0]
    return mergedSchema


def getSchemaValidator():
    """
    Return a jsonschema validator.

    :returns: a validator.
    """
    return jsonschema.Draft6Validator(getSchema())


def readExcelFiles(filelist, ctx):  # noqa
    """
    Read each excel file, use pandas to parse it.  Collect the results, where,
    if a file is stored twice, the value from the newest excel file wins.

    :param filelist: a list of excel or csv file paths.
    :param ctx: a process context.
    :returns: a dictionary with scanned file names as the keys.  Each entry
        contains an ImageID, TokenID, name (the scanned file name), excel (the
        path from the excel file), and timestamp (the mtime of the excel file).
    """
    folderNameField = config.getConfig('folder_name_field', 'TokenID')
    imageNameField = config.getConfig('image_name_field', 'ImageID')
    manifest = {}
    report = []
    validator = getSchemaValidator()
    if 'oneOf' in validator.schema:
        properties = set()
        for subschema in validator.schema['oneOf']:
            properties |= set(subschema['properties'])
    else:
        properties = set(validator.schema['properties'])
    for filepath in filelist:
        filepathOrFptr = filepath
        if isinstance(filepath, dict):
            item = filepath
            filepath = item['name']
            try:
                filepathOrFptr = File().open(next(Item().childFiles(item)))
            except Exception as exc:
                logger.info(f'Exception: {exc}')
                message = 'Cannot read %s' % (os.path.basename(filepath), )
                status = 'badformat'
                continue
            # Set metadata indicating that we've parsed this file
            timestamp = time.mktime(item['created'].timetuple())
        else:
            timestamp = os.path.getmtime(filepath)
        ctx.update(message='Reading %s' % os.path.basename(filepath))
        try:
            df, header_row_number = readExcelData(filepathOrFptr)
            for key in ['ScannedFileName', 'InputFileName']:
                if key in properties and key in df:
                    df[key] = df[key].fillna('')
            df = df.dropna(how='all', axis='columns')
        except Exception as exc:
            if isinstance(exc, ValueError):
                logger.info(f'Exception: {exc}')
                message = 'Cannot read %s; it is not formatted correctly' % (
                    os.path.basename(filepath), )
                status = 'badformat'
            else:
                logger.info(f'{exc}')
                message = 'Cannot read %s; it is not an Excel file' % (
                    os.path.basename(filepath), )
                status = 'notexcel'
            report.append({
                'path': filepath,
                'status': status,
                'reason': message,
            })
            ctx.update(message=message)
            logger.info(message)
            continue
        count = 0
        totalErrors = []
        for row_num, row in enumerate(df.itertuples()):
            rowAsDict = dict(row._asdict())
            # Make sure we don't have any NaNs.  They don't serialize.  Also
            # remove None values.
            rowAsDict = {k: v for k, v in rowAsDict.items()
                         if pd.notnull(v) and v is not None}
            rowAsDict.pop('Index')
            if all(not val for val in rowAsDict.values()):
                continue
            errors = validateDataRow(validator, rowAsDict, header_row_number + 2 + row_num, df)
            name = None
            for key in {'ScannedFileName', 'InputFileName'}:
                name = rowAsDict.pop(key, name)
            if errors:
                for error in errors:
                    message = 'Error in %s: %s' % (os.path.basename(filepath), error)
                    ctx.update(message=message)
                    logger.info(message)
                totalErrors.append({'name': name, 'errors': errors})
            count += 1
            if not name:
                if not errors:
                    # If name is none and there are no errors, then we know
                    # that ScannedFileName and InputFile name are not required,
                    # and we still want this row in the manifest to run OCR and
                    # try to match the row to an image in the future
                    manifest['unfiled'] = manifest.get('unfiled', {})
                    imageName = getattr(row, imageNameField, None)
                    if not imageName and getattr(row, folderNameField, None):
                        imageName = TokenOnlyPrefix + getattr(row, folderNameField, None)
                    unlistedEntry = manifest['unfiled'].get(imageName, None)
                    if unlistedEntry is None or unlistedEntry['timestamp'] < timestamp:
                        manifest['unfiled'][imageName] = {
                            'timestamp': timestamp,
                            folderNameField: getattr(row, folderNameField, None),
                            imageNameField: getattr(row, imageNameField, None),
                            'excel': filepath,
                            'fields': rowAsDict,
                            'errors': errors,
                        }
                else:
                    pass
            elif name not in manifest or (timestamp > manifest[name]['timestamp'] and not errors):
                manifest[name] = {
                    'timestamp': timestamp,
                    imageNameField: getattr(row, imageNameField, None),
                    folderNameField: getattr(row, folderNameField, None),
                    'name': name,
                    'excel': filepath,
                    'fields': rowAsDict,
                    'errors': errors,
                }
        report.append({
            'path': filepath,
            'status': 'parsed',
            'count': count,
            'errors': totalErrors,
        })
        logger.info('Read %s; parsed %d valid rows' % (filepath, count))
    return manifest, report


def isProjectFolder(folder):
    """
    Check if the specified folder is one of the project folders that stores
    WSI.  If so, return the key of the parent folder.

    :params folder: A Girder folder document.
    :returns: A ProjectFolders key or None.
    """
    while folder:
        for key in ProjectFolders:
            projFolderId = Setting().get(ProjectFolders[key])
            if str(folder['_id']) == projFolderId:
                return key
        if folder['parentCollection'] != 'folder':
            break
        folder = Folder().load(folder['parentId'], force=True)
    return None


def getExisting(imagePath, ctx):
    """
    Get the file document of an image if it has already been imported.

    :param imagePath: the path in the assetstore to the image.
    :param ctx: a context manager to report if we had to remove an existing
        item because the file size changed.
    :returns: a status if the document exists or None if it doesn't.
    """
    if isinstance(imagePath, dict):
        return None
    reimportIfMoved = config.getConfig('reimport_if_moved', False)
    existingList = list(File().find(
        {'$or': [{'path': imagePath}, {'s3Key': imagePath}], 'imported': True}))
    existing = existingList[0] if existingList else None
    if reimportIfMoved and existing:
        moved = True
        for existing in existingList:
            item = Item().load(existing['itemId'], force=True)
            folder = Folder().load(item['folderId'], force=True)
            if isProjectFolder(folder) is not None:
                moved = False
                break
        if moved:
            existing = None
    if existing:
        stat = os.stat(imagePath)
        if existing['size'] == stat.st_size:
            return 'present'
        item = Item().load(existing['itemId'], force=True)
        # TODO: move item somewhere; for now, delete it
        ctx.update(message='Removing existing %s since the size has changed' % imagePath)
        Item().remove(item)
        return 'replaced'
    return None


def ingestOneItem(importFolder, imagePath, record, ctx, user, newItems):
    """
    Ingest a single image.

    :param importFolder: the folder to store the image.
    :param imagePath: the path of the image file.
    :param record: a dictionary of information from the excel file.
    :param ctx: a progress context.
    :param user: the user triggering this.
    :param newItems: a list which should be appended with newly added items
    """
    folderNameField = config.getConfig('folder_name_field', 'TokenID')
    imageNameField = config.getConfig('image_name_field', 'ImageID')
    status = 'added'
    status = getExisting(imagePath, ctx) or status
    if status == 'present':
        return status
    parentFolder = Folder().findOne({
        'name': record[folderNameField], 'parentId': importFolder['_id']})
    if not parentFolder:
        parentFolder = Folder().createFolder(importFolder, record[folderNameField], creator=user)
    if not isinstance(imagePath, dict):
        # TODO: (a) use the getTargetAssetstore method from Upload(), (b)
        # ensure that the assetstore is a filesystem assestore.
        assetstore = Assetstore().getCurrent()
        # TODO: When imageNameFiled is blank or undefined, use the folder name
        # plus a number
        name = (record[imageNameField] or '') + process.splitallext(record['name'])[1]
        if name.endswith('.dcm'):
            name = (record[imageNameField] or '') + '.dcm'
        mimeType = 'image/tiff'
        if Item().findOne({'name': {'$regex': '^%s\\.' % record[imageNameField]}}):
            return 'duplicate'
        item = Item().createItem(name=name, creator=user, folder=parentFolder)
        stat = os.stat(imagePath)
        file = File().createFile(
            name=name, creator=user, item=item, reuseExisting=False,
            assetstore=assetstore, mimeType=mimeType, size=stat.st_size,
            saveFile=False)
        file['path'] = os.path.abspath(os.path.expanduser(imagePath))
        file['mtime'] = stat.st_mtime
        file['imported'] = True
        file = File().save(file)
    else:
        # Move an existing item to the parent folder
        item = Item().move(item, parentFolder)
        # TODO: add metadata marking that this was added
    # Reload the item as it will have changed
    item = Item().load(item['_id'], force=True)
    if isinstance(record['fields'], dict):
        item = Item().setMetadata(item, {'deidUpload': record['fields']})
    try:
        redactList = process.get_standard_redactions(item, record[imageNameField])
    except Exception:
        logger.exception('Failed to import %s' % name)
        Item().remove(item)
        ctx.update(message='Failed to import %s' % name)
        return 'failed'
    item = Item().setMetadata(item, {'redactList': redactList})
    newItems.append(item['_id'])
    ctx.update(message='Imported %s' % name)
    return status


def ingestImageToUnfiled(imagePath, unfiledFolder, ctx, user, unfiledItems, uploadInfo):
    if getExisting(imagePath, ctx) == 'present':
        return
    if not isinstance(imagePath, dict):
        ctx.update(message='Importing %s to the Unfiled folder' % imagePath)
        assetstore = Assetstore().getCurrent()
        _, name = os.path.split(imagePath)
        mimeType = 'image/tiff'
        item = Item().createItem(name=name, creator=user, folder=unfiledFolder)
        item['wsi_uploadInfo'] = uploadInfo
        item = Item().save(item)
        stat = os.stat(imagePath)
        file = File().createFile(
            name=name, creator=user, item=item, reuseExisting=False,
            assetstore=assetstore, mimeType=mimeType, size=stat.st_size, saveFile=False)
        file['path'] = os.path.abspath(os.path.expanduser(imagePath))
        file['mtime'] = stat.st_mtime
        file['imported'] = True
        file = File().save(file)
    else:
        item = imagePath
        ctx.update(message='Importing %s to the Unfiled folder' % item['name'])
        item = Item().move(item, unfiledFolder)
        # TODO: add metadata marking that this was added
    unfiledItems.append(item['_id'])


def startOcrJobForUnfiled(itemIds, imageInfoDict, user, reportInfo):
    jobStart = datetime.datetime.now().strftime('%Y%m%d %H%M%S')
    unfiledJob = Job().createLocalJob(
        module='wsi_deid.jobs',
        function='associate_unfiled_images',
        title=f'Attempting to associate unfiled images: {user["login"]}, {jobStart}',
        type='wsi_deid.associate_unfiled',
        user=user,
        asynchronous=True,
        args=(itemIds, imageInfoDict, reportInfo),
    )
    Job().scheduleJob(unfiledJob)
    return unfiledJob['_id']


def directIngestFindFiles(importPath):
    """
    Find all the image and excel files in the import path.

    :param importPath: the import path.
    :returns: a two tuple of lists of excel files and image files.
    """
    excelFiles = []
    imageFiles = []
    for base, _dirs, files in os.walk(importPath):
        for file in files:
            filePath = os.path.join(importPath, base, file)
            _, ext = os.path.splitext(file)
            if ext.lower() in {'.xls', '.xlsx', '.csv'} and not file.startswith('~$'):
                excelFiles.append(filePath)
            # ignore some extensions
            elif (ext.lower() not in {'.zip', '.txt', '.xml', '.swp', '.xlk'} and
                    not file.startswith('~$') and not file.startswith('.~')):
                imageFiles.append(filePath)
    return excelFiles, imageFiles


def ingestData(ctx, user=None, walkData=None):  # noqa
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
    :param walkData: None to find files in the import path, otherwise a
        function that takes an import path and yields a two tuple of a list of
        excelFiles and a list of imageFiles.
    """
    importPath = Setting().get(PluginSettings.WSI_DEID_IMPORT_PATH)
    importFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    if not importPath or not importFolderId:
        msg = 'Import path and/or folder not specified.'
        raise Exception(msg)
    importFolder = Folder().load(importFolderId, force=True, exc=True)
    ctx.update(message='Scanning import folder')
    if not walkData:
        excelFiles, imageFiles = directIngestFindFiles(importPath)
    else:
        excelFiles, imageFiles = walkData(importPath)
    if not len(excelFiles):
        ctx.update(message='Failed to find any excel files in import directory.')
    if not len(imageFiles):
        ctx.update(message='Failed to find any image files in import directory.')
    manifest, excelReport = readExcelFiles(excelFiles, ctx)
    unfiledImages = None
    if manifest.get('unfiled', None) is not None:
        unfiledImages = manifest.pop('unfiled')
    missingImages = []
    report = []
    newItems = []
    for record in manifest.values():
        try:
            imagePath = os.path.join(os.path.dirname(record['excel']), record['name'])
        except TypeError:
            imagePath = None
        if imagePath not in imageFiles:
            imagePath = None
            for testPath in imageFiles:
                if os.path.basename(testPath) == record['name']:
                    imagePath = testPath
                    break
        if imagePath is None and not record.get('errors'):
            missingImages.append(record)
            status = 'missing'
            report.append({'record': record, 'status': status, 'path': record['name']})
            continue
        if imagePath is not None:
            imageFiles.remove(imagePath)
        if record.get('errors'):
            status = 'badentry'
        else:
            status = ingestOneItem(importFolder, imagePath, record, ctx, user, newItems)
        report.append({'record': record, 'status': status, 'path': imagePath})
    # imageFiles are images that have no manifest record
    unfiledFolder = None
    unfiledFolderId = Setting().get(PluginSettings.WSI_DEID_UNFILED_FOLDER)
    if unfiledFolderId:
        unfiledFolder = Folder().load(unfiledFolderId, force=True, exc=True)
    unfiledItems = []
    unfiledJobId = None
    # If we have no valid manifests but we have an unfiled folder, be willing
    # to import to the unfiled area.
    if manifest == {} and imageFiles and unfiledImages is None:
        unfiledImages = {}
    if unfiledImages is not None:
        logger.info(f'{unfiledImages}')
        if not unfiledFolder:
            logger.info('Unfiled folder not specified.')
    for image in imageFiles:
        if unfiledFolder is None:
            status = 'unlisted'
            report.append({
                'record': None, 'status': status,
                'path': image if not isinstance(image, dict) else image['name']})
        else:
            ingestImageToUnfiled(image, unfiledFolder, ctx, user, unfiledItems, unfiledImages)
            report.append({
                'status': 'unfiled',
                'path': image if not isinstance(image, dict) else image['name']})
    if len(unfiledItems):
        unfiledJobId = startOcrJobForUnfiled(
            unfiledItems, unfiledImages, user,
            {'files': report, 'excel': excelReport, 'importPath': importPath})
    # kick off a batch job to run OCR on new items
    startOcrDuringImport = Setting().get(PluginSettings.WSI_DEID_OCR_ON_IMPORT)
    batchJob = None
    if startOcrDuringImport and len(newItems):
        jobStart = datetime.datetime.now().strftime('%Y%m%d %H%M%S')
        batchJob = Job().createLocalJob(
            module='wsi_deid.jobs',
            function='start_ocr_batch_job',
            title=f'Batch OCR triggered by import: {user["login"]}, {jobStart}',
            type='wsi_deid.batch_ocr',
            user=user,
            asynchronous=True,
            args=(newItems),
        )
        Job().scheduleJob(job=batchJob)
    file = importReport(ctx, report, excelReport, user, importPath if not walkData else None)
    summary = reportSummary(report, excelReport, file=file)
    if startOcrDuringImport and batchJob:
        summary['ocr_job'] = batchJob['_id']
    if len(unfiledItems) and unfiledJobId:
        summary['unfiled_job'] = unfiledJobId
    return summary


def importReport(ctx, report, excelReport, user, importPath, reason=None):
    """
    Create an import report.

    :param ctx: a progress context.
    :param report: a list of files that were exported.
    :param excelReport: a list of excel files that were processed.
    :param user: the user triggering this.
    :param importPath: the path of the import folder.  Used to show relative
        paths in the report.  None to not use relative reporting.
    :return: the Girder file with the report
    """
    ctx.update(message='Generating report')
    excelStatusDict = {
        'parsed': 'Parsed',
        'notexcel': 'Not Excel',
        'badformat': 'Bad Format',
    }
    statusDict = {
        'added': 'Imported',
        'present': 'Already imported',
        'replaced': 'Updated',
        'missing': 'File missing',
        'unlisted': 'Not in DeID Upload file',
        'badentry': 'Error in DeID Upload file',
        'failed': 'Failed to import',
        'duplicate': 'Duplicate ImageID',
        'unfiled': 'Unfiled Image',
        'ocrmatch': 'Filed based on OCR',
    }
    statusExplanation = {
        'failed': 'Image file is not an accepted WSI format',
        'duplicate': 'A different image with the same ImageID was previously imported',
        'replaced': 'File size was different than that already present; '
                    'existing image was replaced',
        'unfiled': 'The file could not be associated with a row in the import spreadsheet '
                    'at the time of import',
    }
    keyToColumns = {
        'excel': 'ExcelFilePath',
    }
    dataList = []
    reportFields = config.getConfig('upload_metadata_for_export_report') or []
    statusKey = 'SoftwareStatus'
    reasonKey = 'Status/FailureReason'
    anyErrors = False
    for row in excelReport:
        data = {
            'ExcelFilePath': os.path.relpath(row['path'], importPath)
            if importPath else row['path'],
            statusKey: excelStatusDict.get(row['status'], row['status']),
            reasonKey: row.get('reason'),
        }
        if row['status'] == 'badformat' and not row.get('reason'):
            data[reasonKey] = 'No header row with ImageID, TokenID, and ImportFileName'
        dataList.append(data)
        anyErrors = anyErrors or row['status'] in {'notexcel', 'badformat'}
    for row in report:
        data = {
            'WSIFilePath': os.path.relpath(row['path'], importPath) if row.get(
                'path') and row['status'] != 'missing' and importPath else row.get('path'),
            statusKey: statusDict.get(row['status'], row['status']),
        }
        if row.get('record'):
            fields = row['record'].get('fields')
            fields = {key: value for key, value in fields.items() if key in reportFields}
            data.update(fields)
            for k, v in row['record'].items():
                if k == 'excel' and v and importPath:
                    v = os.path.relpath(v, importPath)
                if k != 'fields':
                    data[keyToColumns.get(k, k)] = v
            if row['record'].get('errors'):
                data[reasonKey] = '. '.join(row['record']['errors'])
        if not data.get(reasonKey) and row['status'] in statusExplanation:
            data[reasonKey] = statusExplanation[row['status']]
        dataList.append(data)
        anyErrors = anyErrors or row['status'] in {
            'duplicate', 'missing', 'unlisted', 'failed', 'badentry'}
    if not len(excelReport) and not len(report):
        dataList.insert(0, {
            reasonKey: 'Nothing to import.  Import folder is empty.'})
    else:
        reasonBase = {'OCR': 'OCR after import completed'}.get(reason, 'Import process completed')
        dataList.insert(0, {reasonKey: reasonBase + ('' if not anyErrors else ' with errors')})
    for row in dataList:
        if not row.get(reasonKey) and row.get(statusKey):
            row[reasonKey] = row[statusKey]
    df = pd.DataFrame(dataList, columns=[
        'ExcelFilePath', 'WSIFilePath', statusKey, *reportFields, reasonKey])
    reasonStr = '' if not reason else ' %s' % reason
    reportName = 'DeID Import Job %s%s.xlsx' % (
        datetime.datetime.now().strftime('%Y%m%d %H%M%S'), reasonStr)
    reportFolder = 'Import Job Reports'
    with tempfile.TemporaryDirectory(prefix='wsi_deid') as tempdir:
        path = os.path.join(tempdir, reportName)
        ctx.update(message='Saving report')
        df.to_excel(path, index=False)
        return saveToReports(path, XLSX_MIMETYPE, user, reportFolder)


def reportSummary(*args, **kwargs):
    """
    Generate a summary of multiple reports.

    :param *args: all other arguments are lists of results, each entry of which
        is a dictionary with a 'status' field.  The overall summary is a
        tally of the occurrences of each status.
    :param **kwargs: if 'file' is specified, this is a Girder file model.  The
        file id is returned as part of the results.
    :returns: a dictionary of status values, each with a numerical tally, and
        optionally a reportItemId field.
    """
    result = {}
    for report in args:
        for entry in report:
            result.setdefault(entry['status'], 0)
            result[entry['status']] += 1
    if kwargs.get('file'):
        result['reportItemId'] = str(kwargs['file']['itemId'])
    return result


def exportItems(ctx, user=None, all=False, onlyReport=False):
    """
    Export all or all recent items in the Finished directory.  Mark each
    exported item as having been exported.

    :param ctx: a progress context.
    :param user: the user triggering this.
    :param all: True to export all items.  False to only export items that have
        not been previously exported.
    :param onlyReport: True to only generate the report, not to actually do the
        export.
    """
    sftp_mode = SftpMode(Setting().get(PluginSettings.WSI_DEID_SFTP_MODE))
    export_enabled = sftp_mode in [SftpMode.LOCAL_EXPORT_ONLY, SftpMode.SFTP_AND_EXPORT]
    sftp_enabled = sftp_mode in [SftpMode.SFTP_AND_EXPORT, SftpMode.SFTP_ONLY]
    logger.info('Export begin (all=%s)' % all)
    exportPath = Setting().get(PluginSettings.WSI_DEID_EXPORT_PATH)
    exportFolderId = Setting().get(PluginSettings.HUI_FINISHED_FOLDER)
    if (not exportPath or not exportFolderId) and not onlyReport:
        msg = 'Export path and/or finished folder not specified.'
        raise Exception(msg)
    exportFolder = Folder().load(exportFolderId, force=True, exc=True)
    report = []
    summary = {}
    totalByteCount = 0
    if sftp_enabled and not onlyReport:
        job_title = f'Remote export: {user["login"]}, {datetime.datetime.now()}'
        sftp_job = Job().createLocalJob(
            module='wsi_deid.import_export',
            function='sftp_items',
            title=job_title,
            type='wsi_deid.sftp_job',
            user=user,
            asynchronous=True,
            args=(exportFolder, user, all),
        )
        Job().scheduleJob(job=sftp_job)
    if export_enabled or onlyReport:
        for mode in (('measure', 'copy') if not onlyReport else ('measure',)):
            byteCount = 0
            for filepath, file in Folder().fileList(exportFolder, user, data=False):
                byteCount += exportItemsNext(
                    mode, ctx, byteCount, totalByteCount, filepath, file,
                    exportPath, user, report, onlyReport=onlyReport)
            totalByteCount = byteCount
        logger.info('Exported files')
        exportNoteRejected(report, user, all, EXPORT_HISTORY_KEY)
        logger.info('Exported note others')
        file = exportReport(ctx, exportPath, report, user, onlyReport=onlyReport)
        logger.info('Exported generated report')
        summary = reportSummary(report, file=file)
        logger.info('Exported done')
    summary['sftp_enabled'] = sftp_enabled
    summary['local_export_enabled'] = export_enabled
    if sftp_enabled and not onlyReport:
        summary['sftp_job_id'] = sftp_job['_id']
    return summary


def sftp_items(job):
    """
    Export items to a remote server via SFTP.

    :param job: A girder job object containing information about how to run the SFTP export
    """
    args = job.get('args', None)
    export_folder = args[0]
    user = args[1]
    export_all = args[2]
    sftp_report = []

    sftp_mode = Setting().get(PluginSettings.WSI_DEID_SFTP_MODE)
    sftp_enabled = SftpMode(sftp_mode) in [SftpMode.SFTP_AND_EXPORT, SftpMode.SFTP_ONLY]
    sftp_destination = Setting().get(PluginSettings.WSI_DEID_REMOTE_PATH)
    if not sftp_enabled:  # Sanity check
        return

    Job().updateJob(job, status=JobStatus.RUNNING)  # mark job as running
    if not sftp_destination:
        message = 'SFTP destination not specified. No items transferred.\n'
        Job().updateJob(
            job, log=message, status=JobStatus.ERROR, notify=True)
        raise Exception(message)

    Job().updateJob(
        job,
        log=f'Starting transfer of files to remote directory: {sftp_destination}.\n\n',
    )

    try:
        sftp_client = get_sftp_client()
    except Exception as exc:
        logger.exception(f'Job {job["_id"]} failed.')
        connection_failed_message = (
            f'Attempting to establish a remote connection resulted in: {str(exc)}'
        )
        Job().updateJob(job, log=connection_failed_message, status=JobStatus.ERROR, notify=True)
        return
    Job().updateJob(job, log='Successfully established a connection with the remote host.\n\n')
    previous_exported_count = 0
    try:
        for filepath, file in Folder().fileList(export_folder, user, data=False):
            try:
                export_result = sftp_one_item(
                    filepath,
                    file,
                    sftp_destination,
                    sftp_client,
                    job,
                    export_all,
                    user,
                    sftp_report,
                )
                if export_result == ExportResult.PREVIOUSLY_EXPORTED:
                    previous_exported_count += 1
            except Exception:
                Job().updateJob(
                    job,
                    log=f'There was an error transferring {filepath} to the remote destination.\n',
                    status=JobStatus.ERROR,
                )
                # reraise exception to stop looping through files
                raise
        # create and export the report
        exportNoteRejected(sftp_report, user, export_all, SFTP_HISTORY_KEY)
        sftpReport(
            job,
            Setting().get(PluginSettings.WSI_DEID_EXPORT_PATH),
            sftp_report,
            sftp_client,
            sftp_destination,
            user,
        )
        if previous_exported_count > 0:
            Job().updateJob(job, log=f'{previous_exported_count} file(s) previously exported.\n')
        Job().updateJob(job, log='Transfer of files complete.\n', status=JobStatus.SUCCESS)
    except Exception as exc:
        # log the exception
        logger.exception(f'Job {job["_id"]} failed.')
        # mark the job failed with details about the exception
        Job.updateJob(
            job,
            log=f'Job failed with the following exception: {str(exc)}.',
            status=JobStatus.ERROR,
        )
    finally:
        sftp_client.close()


def get_sftp_client():
    """Create an instance of paramiko.SFTPClient based on girder config."""
    host = Setting().get(PluginSettings.WSI_DEID_REMOTE_HOST)
    port = Setting().get(PluginSettings.WSI_DEID_REMOTE_PORT)
    user = Setting().get(PluginSettings.WSI_DEID_REMOTE_USER)
    password = Setting().get(PluginSettings.WSI_DEID_REMOTE_PASSWORD)

    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    sftp_client = paramiko.SFTPClient.from_transport(transport)
    if sftp_client is None:
        msg = 'There was an error connecting to the remote server.'
        raise Exception(msg)
    return sftp_client


def getSourcePath(item):
    """
    Get the large image path for a Girder File.
    Return None if no tile source could be found.

    :param item: The girder item to find the tile source path of
    """
    try:
        tileSource = ImageItem().tileSource(item)
    except Exception:
        return None
    return tileSource._getLargeImagePath()


def skipExport(item, all, metadataProperty):
    """
    Determine whether a particular item should be exported as part of this export run.

    :param item: the item we're checking
    :param all: whether or not we're exporting all or recent items
    :param metadataProperty: the metadata property that acts as a flag to check previous exports
    """
    return not all and item.get('meta', {}).get(metadataProperty)


def appendExportRecord(item, user, metadataProperty, status=None):
    """
    Append information about the current export to an item's exported record. Return the most
    recent export record.

    :param item: the Girder item to add export history to
    :param user: the user performing this export
    :metadataProperty: the Girder item property that holds export history
    """
    from . import __version__
    exportedRecord = item.get('meta', {}).get(metadataProperty, [])
    newExportRecord = {
        'time': datetime.datetime.utcnow().isoformat(),
        'user': str(user['_id']) if user else None,
        'version': __version__,
    }
    if status:
        newExportRecord['status'] = status
    exportedRecord.append(newExportRecord)
    item = Item().setMetadata(item, {metadataProperty: exportedRecord})
    return newExportRecord


def sftp_one_item(filepath, file, destination, sftp_client, job, export_all, user, reports):
    """
    Send a file to a remote server via SFTP.

    :param filepath: the file path of this item
    :param file: the file document of this item
    :param destination: the remote folder for the file to be sent to
    :param sftp_client: an instance of paramiko.SFTPClient
    :param job: a Girder job. Used to log messages.
    :param export_all: whether or not to export all items or newly approved items
    :param user: the user who triggered the transfer
    :param reports: array of export info to compile into a report spreadsheet
    :return: a member of enum ExportResult
    """
    file_path_segments = filepath.split(os.path.sep)
    image_dir = file_path_segments[-2]
    file_name = file_path_segments[-1]
    full_remote_path = os.path.join(destination, image_dir, file_name)
    item = Item().load(file['itemId'], force=True, exc=False)
    tile_source_path = getSourcePath(item)
    if not tile_source_path:
        Job().updateJob(job, log=f'Unable to locate tile source for {file_name}.\n')
        return ExportResult.EXPORT_FAILED
    if skipExport(item, export_all, SFTP_HISTORY_KEY):
        return ExportResult.PREVIOUSLY_EXPORTED

    remote_dirs = sftp_client.listdir(destination)
    if image_dir not in remote_dirs:
        sftp_client.mkdir(os.path.join(destination, image_dir))

    existing_files = sftp_client.listdir(os.path.join(destination, image_dir))
    if file_name in existing_files:
        existing_file_stat = sftp_client.stat(full_remote_path)
        if existing_file_stat.st_size == file['size']:
            reports.append({'item': item, 'status': 'present'})
        else:
            reports.append({'item': item, 'status': 'different'})
        Job().updateJob(
            job,
            log=f'A file with the name {file_name} already exists at the remote destination.\n',
        )
        return ExportResult.ALREADY_EXISTS_AT_DESTINATION
    else:
        transferred_file_stat = sftp_client.put(tile_source_path, full_remote_path)
        if transferred_file_stat.st_size == file['size']:
            Job().updateJob(
                job,
                log=f'File {file_name} successfully transferred to the remote destination.\n',
            )
            new_export_record = appendExportRecord(item, user, SFTP_HISTORY_KEY)
            reports.append({
                'item': item,
                'status': 'finished',
                'time': new_export_record['time'],
            })
            return ExportResult.EXPORTED_SUCCESSFULLY
        else:
            msg = f'There was an error transferring file {file_name} to remote destination.'
            raise Exception(msg)


def exportItemsNext(mode, ctx, byteCount, totalByteCount, filepath, file,
                    exportPath, user, report, onlyReport=False):
    """
    Export an item or report on its size.

    :param mode: either 'measure' or 'copy'.
    :param ctx: a progress context.
    :param byteCount: the number of bytes copies so far.
    :param totalByteCount: the total number of bytes needed to be copies.
    :param filepath: the file path of this item.
    :param file: the file document of this item.
    :param exportPath: the destination for the export.
    :param user: the user triggering this.
    :param report: a collected report list.
    :param onlyReport: True to only generate the report, not to actually do the
        export.
    :returns: the number of bytes that are copied.  If mode is measure, no
        copying is actually done.
    """
    item = Item().load(file['itemId'], force=True, exc=False)
    sourcePath = getSourcePath(item)
    if not sourcePath or skipExport(item, all, EXPORT_HISTORY_KEY):
        return 0
    filepath = filepath.split(os.path.sep, 1)[1]
    if mode == 'copy':
        ctx.update(message='Exporting %s' % filepath, total=totalByteCount, current=byteCount)
    destPath = os.path.join(exportPath, filepath)
    destFolder = os.path.dirname(destPath)
    if os.path.exists(destPath):
        if mode == 'copy' or onlyReport:
            if os.path.getsize(destPath) == file['size']:
                report.append({'item': item, 'status': 'present'})
            else:
                report.append({'item': item, 'status': 'different'})
        return 0
    else:
        if mode == 'copy':
            os.makedirs(destFolder, exist_ok=True)
            # When run in a docker in Windows, cp is around twice as fast as
            # shutil.copy2 for Python < 3.8.  For Python >=3.8, shutil.copy2 is
            # even slower (by about a factor of 3 from shutil in Python < 3.8),
            # seemingly because the internal call to posix.sendfile is terrible
            # in a linux docker under Windows.
            try:
                subprocess.check_call(['cp', '--preserve=timestamps', sourcePath, destPath])
            except Exception:
                shutil.copy2(sourcePath, destPath)
            newExportRecord = appendExportRecord(item, user, EXPORT_HISTORY_KEY)
            report.append({
                'item': item,
                'status': 'finished',
                'time': newExportRecord['time'],
            })
        elif onlyReport:
            report.append({
                'item': item,
                'status': 'ready',
            })
        return file['size']


def exportNoteRejected(report, user, all, metadataProperty, allFiles=True):
    """
    Note items that are rejected or quarantined, collecting them for a report.

    :param report: a list of items to report.
    :param user: the user triggering this.
    :param all: True to export all items.  False to only export items that have
        not been previously exported.
    :param allFiles: True to report on all files in all folders.  False to only
        report rejected and quarantined items.
    """
    shortList = [
        ('rejected', PluginSettings.HUI_REJECTED_FOLDER),
        ('quarantined', PluginSettings.HUI_QUARANTINE_FOLDER),
    ]
    longList = shortList + [
        ('imported', PluginSettings.HUI_INGEST_FOLDER),
        ('processed', PluginSettings.HUI_PROCESSED_FOLDER),
    ]
    for status, settingkey in (shortList if not allFiles else longList):
        folderId = Setting().get(settingkey)
        folder = Folder().load(folderId, force=True, exc=True)
        for _, file in Folder().fileList(folder, user, data=False):
            item = Item().load(file['itemId'], force=True, exc=True)
            try:
                ImageItem().tileSource(item)
            except Exception:
                continue
            if skipExport(item, all, metadataProperty):
                continue
            newExportRecord = appendExportRecord(item, user, metadataProperty, status=status)
            report.append({
                'item': item,
                'status': status,
                'time': newExportRecord['time'],
            })


def buildExportDataSet(report):
    """
    Build a dataframe with export data. The results of this method
    can be used to generate an export report spreadsheet.

    :param report: a list of information used to build the dataframe
    """
    statusDict = {
        'finished': 'Approved',
        'present': 'Approved',
        'redacted': 'Approved',
        'quarantined': 'Quarantined',
        'rejected': 'Rejected',
        'imported': 'AvailableToProcess',
        'processed': 'ReadyForApproval',
        'different': 'FailedToExport',
    }
    curtime = datetime.datetime.utcnow()
    exportFields = config.getConfig('upload_metadata_for_export_report') or []
    statusReasonFields = []
    rejectReasonRequired = config.getConfig('require_reject_reason')
    if rejectReasonRequired:
        statusReasonFields += ['Rejection_Reason']
    dataList = []
    timeformat = '%m%d%Y: %H%M%S'
    for row in report:
        row['item']['meta'].setdefault('deidUpload', {})
        uploadData = row['item']['meta']['deidUpload']
        uploadData = {key: value for key, value in uploadData.items() if key in exportFields}
        row['item']['meta']['deidUpload'] = uploadData
        data = {}
        data.update(row['item']['meta']['deidUpload'])
        data['DSAImageStatus'] = statusDict.get(row['status'], row['status'])
        if data['DSAImageStatus'] == 'Approved':
            data['Date_DEID_Export'] = curtime.strftime(timeformat)
        if data['DSAImageStatus'] == 'Rejected' and rejectReasonRequired:
            rejectReasonData = row['item']['meta'].get('reject', {}).get('rejectReason', {})
            rejectEntry = ''
            rejectReason = rejectReasonData.get('reason', None)
            if rejectReason is not None:
                rejectEntry += rejectReason
            rejectCategory = rejectReasonData.get('category', None)
            if rejectCategory is not None:
                rejectEntry += ' (' + rejectCategory + ')'
            data['Rejection_Reason'] = rejectEntry
        if data['DSAImageStatus'] != 'AvailableToProcess':
            data['Last_DEID_RunDate'] = row['item'].get(
                'modified', row['item']['created']).strftime(timeformat)
        if 'redacted' in row['item']['meta']:
            try:
                info = row['item']['meta']['redacted'][-1]
                data['ScannerMake'] = info['details']['format'].capitalize()
                data['ScannerModel'] = info['details']['model']
                data['ByteSize_InboundWSI'] = row['item']['meta']['redacted'][0]['originalSize']
                data['ByteSize_ExportedWSI'] = info['redactedSize']
                data['Total_VendorMetadataFields'] = info[
                    'details']['fieldCount']['metadata']['redactable'] + info[
                    'details']['fieldCount']['metadata']['automatic']
                data['Total_VendorMetadataFields_ModifiedOrCreated'] = len(
                    info['redactList']['metadata'])
                data['Automatic_DEID_PHIPII_MetadataFieldsModifiedRedacted'] = ', '.join(sorted(
                    k.rsplit(';', 1)[-1] for k, v in info['redactList']['metadata'].items()
                    if not v.get('reason') or v.get('reason') == SystemRedactedReason)) or 'N/A'
                userMeta = sorted(
                    k.rsplit(';', 1)[-1] for k, v in info['redactList']['metadata'].items()
                    if v.get('reason') and v.get('reason') != SystemRedactedReason)
                userImages = sorted(
                    k for k, v in info['redactList']['images'].items()
                    if v.get('reason') and v.get('reason') != SystemRedactedReason)
                data['Addtl_UserIdentifiedPHIPII_BINARY'] = 'Yes' if (
                    len(userMeta) or len(userImages)) else 'No'
                data['Total_Addtl_UserIdentifiedPHIPII_MetadataFields'] = len(userMeta)
                data['Addtl_UserIdentifiedPHIPII_MetadataFields'] = ', '.join(userMeta) or 'N/A'

                data['Addtl_UserIdentifiedPHIPII_Category_MetadataFields'] = ', '.join(sorted({
                    v['category'] for k, v in info['redactList']['metadata'].items()
                    if v.get('reason') and v.get('reason') != SystemRedactedReason and
                    v.get('category')})) or 'N/A'
                data['Addtl_UserIdentifiedPHIPII_DetailedType_MetadataFields'] = ', '.join(sorted(
                    {
                        v['reason'] for k, v in info['redactList']['metadata'].items()
                        if v.get('reason') and v.get('category') == 'Personal_Info'})) or 'N/A'
                data['Total_VendorImageComponents'] = info[
                    'details']['fieldCount']['images']
                data['Total_UserIdentifiedPHIPII_ImageComponents'] = len(userImages)
                data['UserIdentifiedPHIPII_ImageComponents'] = ', '.join(userImages) or 'N/A'
                data['UserIdentifiedPHIPII_Category_ImageComponents'] = ', '.join(sorted({
                    v['category'] for k, v in info['redactList']['images'].items()
                    if v.get('reason') and v.get('reason') != SystemRedactedReason and
                    v.get('category')})) or 'N/A'
                data['UserIdentifiedPHIPII_DetailedType_ImageComponents'] = ', '.join(sorted({
                    v['reason'] for k, v in info['redactList']['images'].items()
                    if v.get('reason') and v.get('reason') != SystemRedactedReason and
                    v.get('category') == 'Personal_Info'})) or 'N/A'
            except KeyError:
                pass
        dataList.append(data)
    df = pd.DataFrame(dataList, columns=[
        'Last_DEID_RunDate', 'Date_DEID_Export',
        *exportFields,
        'ScannerMake', 'ScannerModel',
        'DSAImageStatus', *statusReasonFields,
        'ByteSize_InboundWSI',
        'ByteSize_ExportedWSI',
        'Total_VendorMetadataFields',
        'Total_VendorMetadataFields_ModifiedOrCreated',
        # Space separated list of redacted fields names (chunk after last ;)
        'Automatic_DEID_PHIPII_MetadataFieldsModifiedRedacted',
        'Addtl_UserIdentifiedPHIPII_BINARY',          # no/yes
        'Total_Addtl_UserIdentifiedPHIPII_MetadataFields',
        # N/A is none, otherwise space separated field names (chunk after ;)
        'Addtl_UserIdentifiedPHIPII_MetadataFields',
        # category list or N/A
        'Addtl_UserIdentifiedPHIPII_Category_MetadataFields',
        # reason list or N/A
        'Addtl_UserIdentifiedPHIPII_DetailedType_MetadataFields',
        'Total_VendorImageComponents',
        'Total_UserIdentifiedPHIPII_ImageComponents',
        'UserIdentifiedPHIPII_ImageComponents',
        'UserIdentifiedPHIPII_Category_ImageComponents',
        'UserIdentifiedPHIPII_DetailedType_ImageComponents',
    ])
    return df


def exportReport(ctx, exportPath, report, user, onlyReport=False):
    """
    Create an export report.

    :param ctx: a progress context.
    :param exportPath: directory for exports
    :param report: a list of files that were exported.
    :param user: the user triggering this.
    :param onlyReport: True to only generate the report, not to actually do the
        export.
    :return: the Girder file with the report
    """
    ctx.update(message='Generating report')
    basename = 'DeID Export Job' if not onlyReport else 'DeID Report'
    exportName = f'{basename} {datetime.datetime.now().strftime("%Y%m%d %H%M%S")}.xlsx'
    df = buildExportDataSet(report)
    reportFolder = 'Export Job Reports'
    path = os.path.join(exportPath, exportName)
    ctx.update(message='Saving report')
    df.to_excel(path, index=False)
    return saveToReports(path, XLSX_MIMETYPE, user, reportFolder)


def sftpReport(job, exportPath, report, sftpClient, sftpDestination, user):
    """
    Create an export report for SFTP transfers.

    :param job: the girder job running the transfer.
    :param exportPath: path for exports.
    :param report: a list of files that were exported.
    :param sftpClient: an instance of paramiko.SFTPClient
    :param sftpDestination: the directory path for remote transfers.
    :param user: the user triggering generation of the report.
    :return: result of transferring the file to the remote SFTP destination.
    """
    dateTime = datetime.datetime.now()
    exportName = 'DeID Remote Export Job %s.xlsx' % dateTime.strftime('%Y%m%d %H%M%S')
    path = os.path.join(exportPath, exportName)
    Job().updateJob(job, log=f'\nGenerating remote export report "{exportName}".\n')
    df = buildExportDataSet(report)
    Job().updateJob(job, log='Transferring report to remote destination.\n')
    df.to_excel(path, index=False)
    remotePath = os.path.join(sftpDestination, exportName)
    stat = sftpClient.put(path, remotePath)
    Job().updateJob(job, log='Report transferred to the remote destination.\n\n')
    reportFolder = 'Remote Export Job Reports'
    saveToReports(path, XLSX_MIMETYPE, user, reportFolder)
    return stat


def saveToReports(path, mimetype=None, user=None, folderName=None):
    """
    Save a file to the reports folder.

    :param path: path of the file to save.
    :param mimetype: the mimetype of the file.
    :param user: the user triggering this.
    :param folderName: if not None, create a folder in the reportsFolder with
        this name and store the new report in that folder.
    :return: the Girder file with the report
    """
    reportsFolderId = Setting().get(PluginSettings.HUI_REPORTS_FOLDER)
    reportsFolder = Folder().load(reportsFolderId, force=True, exc=False)
    if not reportsFolder:
        msg = 'Reports folder not specified.'
        raise Exception(msg)
    if folderName:
        reportsFolder = Folder().createFolder(
            reportsFolder, folderName, creator=user, reuseExisting=True)
    with open(path, 'rb') as f:
        file = Upload().uploadFromFile(
            f, size=os.path.getsize(path), name=os.path.basename(path),
            parentType='folder', parent=reportsFolder, user=user,
            mimeType=mimetype)
        return file
