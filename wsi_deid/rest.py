import copy
import datetime
import json
import os
import re
import tempfile
import threading
import time

import girder_large_image
import histomicsui.handlers
from bson import ObjectId
from girder import logger
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource, boundHandler
from girder.constants import AccessType, SortDir, TokenScope
from girder.exceptions import AccessException, RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.upload import Upload
from girder.models.user import User
from girder.utility.model_importer import ModelImporter
from girder.utility.progress import ProgressContext, setResponseTimeLimit
from girder_jobs.models.job import Job
from girder_large_image.models.image_item import ImageItem

from . import config, import_export, process
from .constants import PluginSettings, ProjectFolders, TokenOnlyPrefix

IngestLock = threading.Lock()
ExportLock = threading.Lock()
ItemActionLock = threading.Lock()
ItemActionList = []


def create_folder_hierarchy(item, user, folder):
    """
    Create a folder hierarchy that matches the original if the original is
    under a project folder.

    :param item: the item that will be moved or copied.
    :param user: the user that will own the created folders.
    :param folder: the destination project folder.
    :returns: a destination folder that is either the folder passed to this
        routine or a folder beneath it.
    """
    # Mirror the folder structure in the destination.  Remove empty folders in
    # the original location.
    projFolderIds = [Setting().get(val) for key, val in ProjectFolders.items()]
    origPath = []
    origFolders = []
    itemFolder = Folder().load(item['folderId'], force=True)
    while itemFolder and str(itemFolder['_id']) not in projFolderIds:
        origPath.insert(0, itemFolder['name'])
        origFolders.insert(0, itemFolder)
        if itemFolder['parentCollection'] != 'folder':
            origPath = origFolders = []
            itemFolder = None
        else:
            itemFolder = Folder().load(itemFolder['parentId'], force=True)
    # create new folder structure
    for name in origPath:
        folder = Folder().createFolder(folder, name=name, creator=user, reuseExisting=True)
    return folder, origFolders


def move_item(item, user, settingkey, options=None):
    """
    Move an item to one of the folders specified by a setting.

    :param item: the item model to move.
    :param user: a user for folder creation.
    :param settingkey: one of the PluginSettings values.
    :returns: the item after move.
    """
    folderId = Setting().get(settingkey)
    if not folderId:
        msg = 'The appropriate folder is not configured.'
        raise RestException(msg)
    folder = Folder().load(folderId, force=True)
    if not folder:
        msg = 'The appropriate folder does not exist.'
        raise RestException(msg)
    if str(folder['_id']) == str(item['folderId']):
        msg = 'The item is already in the appropriate folder.'
        raise RestException(msg)
    folder, origFolders = create_folder_hierarchy(item, user, folder)
    if settingkey == PluginSettings.HUI_QUARANTINE_FOLDER:
        quarantineInfo = {
            'originalFolderId': item['folderId'],
            'originalBaseParentType': item['baseParentType'],
            'originalBaseParentId': item['baseParentId'],
            'originalUpdated': item['updated'],
            'quarantineUserId': user['_id'],
            'quarantineTime': datetime.datetime.utcnow(),
        }
    rejectInfo = None
    if settingkey == PluginSettings.HUI_REJECTED_FOLDER and options is not None:
        rejectReason = options.get('rejectReason', None)
        if rejectReason:
            rejectInfo = {
                'rejectReason': rejectReason,
            }
        requireRejectReason = config.getConfig('require_reject_reason')
        if requireRejectReason and rejectInfo is None:
            msg = 'A rejection reason is required.'
            raise RestException(msg)
    # move the item
    item = Item().move(item, folder)
    if settingkey == PluginSettings.HUI_QUARANTINE_FOLDER:
        # When quarantining, add metadata and don't prune folders
        item = Item().setMetadata(item, {'quarantine': quarantineInfo})
    if settingkey == PluginSettings.HUI_REJECTED_FOLDER and rejectInfo is not None:
        item = Item().setMetadata(item, {'reject': rejectInfo})
    else:
        # Prune empty folders
        for origFolder in origFolders[::-1]:
            if Folder().findOne({'parentId': origFolder['_id'], 'parentCollection': 'folder'}):
                break
            if Item().findOne({'folderId': origFolder['_id']}):
                break
            Folder().remove(origFolder)
    return item


def quarantine_item(item, user, *args, **kwargs):
    return move_item(item, user, PluginSettings.HUI_QUARANTINE_FOLDER)


histomicsui.handlers.quarantine_item = quarantine_item


def process_item(item, user=None):  # noqa
    """
    Copy an item to the original folder.  Modify the item by processing it and
    generating a new, redacted file.  Move the item to the processed folder.

    :param item: the item model to move.
    :param user: the user performing the processing.
    :returns: the item after move.
    """
    from . import __version__

    origFolderId = Setting().get(PluginSettings.HUI_ORIGINAL_FOLDER)
    procFolderId = Setting().get(PluginSettings.HUI_PROCESSED_FOLDER)
    if not origFolderId or not procFolderId:
        msg = 'The appropriate folder is not configured.'
        raise RestException(msg)
    origFolder = Folder().load(origFolderId, force=True)
    procFolder = Folder().load(procFolderId, force=True)
    if not origFolder or not procFolder:
        msg = 'The appropriate folder does not exist.'
        raise RestException(msg)
    creator = User().load(item['creatorId'], force=True)
    # Generate the redacted file first, so if it fails we don't do anything
    # else
    with tempfile.TemporaryDirectory(prefix='wsi_deid') as tempdir:
        try:
            filepaths, info = process.redact_item(item, tempdir)
        except Exception as e:
            logger.exception('Failed to redact item')
            raise RestException(e.args[0])
        if not isinstance(filepaths, list):
            filepaths = [filepaths]
        origFolder, _ = create_folder_hierarchy(item, user, origFolder)
        origItem = Item().copyItem(item, creator, folder=origFolder)
        origItem = Item().setMetadata(origItem, {
            'wsi_deidProcessed': {
                'itemId': str(item['_id']),
                'time': datetime.datetime.utcnow().isoformat(),
                'user': str(user['_id']) if user else None,
            },
        })
        ImageItem().delete(item)
        origSize = 0
        for childFile in Item().childFiles(item):
            origSize += childFile['size']
            File().remove(childFile)
        newName = item['name']
        if len(process.splitallext(newName)[1]) <= 1:
            newName = process.splitallext(item['name'])[0] + process.splitallext(filepaths[0])[1]
        if len(filepaths) > 1:
            newName = process.splitallext(item['name'])[0] + os.path.splitext(filepaths[0])[1]
        newSize = 0
        for filepath in filepaths:
            newSize += os.path.getsize(filepath)
            with open(filepath, 'rb') as f:
                Upload().uploadFromFile(
                    f, size=os.path.getsize(filepath),
                    name=os.path.basename(filepath) if len(filepaths) > 1 else newName,
                    parentType='item', parent=item, user=creator,
                    mimeType=info['mimetype'])
        item = Item().load(item['_id'], force=True)
        if len(filepaths) > 1:
            for idx in range(len(filepaths)):
                try:
                    ImageItem().delete(item)
                except Exception:
                    pass
                item = Item().load(item['_id'], force=True)
                try:
                    ImageItem().createImageItem(
                        item, list(Item().childFiles(item))[idx], user=user, createJob=False)
                    break
                except Exception:
                    if idx + 1 == len(filepaths):
                        raise
            item = Item().load(item['_id'], force=True)
        item['name'] = newName
    item.setdefault('meta', {})
    item['meta'].setdefault('redacted', [])
    item['meta']['redacted'].append({
        'user': str(user['_id']) if user else None,
        'time': datetime.datetime.utcnow().isoformat(),
        'originalSize': origSize,
        'redactedSize': newSize,
        'redactList': item['meta'].get('redactList'),
        'details': info,
        'version': __version__,
    })
    item['meta'].pop('quarantine', None)
    allPreviousExports = {}
    for history_key in [import_export.EXPORT_HISTORY_KEY, import_export.SFTP_HISTORY_KEY]:
        if history_key in item['meta']:
            allPreviousExports[history_key] = item['meta'][history_key]
        item['meta'].pop(history_key, None)
    item['meta']['redacted'][-1]['previousExports'] = allPreviousExports
    item['updated'] = datetime.datetime.utcnow()
    try:
        redactList = item['meta'].get('redactList') or {}
        if redactList.get('area', {}).get('_wsi', {}).get('geojson') or any(
                redactList['images'][key].get('geojson') for key in redactList.get('images', {})):
            ImageItem().removeThumbnailFiles(item)

    except Exception:
        ImageItem().removeThumbnailFiles(item)
    item = move_item(item, user, PluginSettings.HUI_PROCESSED_FOLDER)
    return item


def ocr_item(item, user):
    job_title = f'Finding label text for image: {item["name"]}'
    ocr_job = Job().createLocalJob(
        module='wsi_deid.jobs',
        function='start_ocr_item_job',
        title=job_title,
        type='wsi_deid.ocr_job',
        user=user,
        asynchronous=True,
        args=(item,),
    )
    Job().scheduleJob(job=ocr_job)
    return {
        'jobId': ocr_job.get('_id', None),
    }


def get_first_item(folder, user, exclude=None, excludeFolders=False):
    """
    Get the first item in a folder or any subfolder of that folder.  The items
    are sorted alphabetically.

    :param folder: the folder to search
    :param user: the user with permissions to use for searching.
    :param exclude: if not None, exclude items in this list of folders (does
        not include their subfolders).
    :param excludeFolders: if True, add the folders of items in the current
        ItemActionList to the list of excluded folders.
    :returns: an item or None.
    """
    if excludeFolders:
        exclude = (exclude or [])[:]
        with ItemActionLock:
            for item in ItemActionList:
                exclude.append({'_id': item['folderId']})
    excludeset = (str(entry['_id']) for entry in exclude) if exclude else set()
    if str(folder['_id']) not in excludeset:
        for item in Folder().childItems(folder, limit=1, sort=[('lowerName', SortDir.ASCENDING)]):
            with ItemActionLock:
                if item['_id'] not in [entry['_id'] for entry in ItemActionList]:
                    return item
    for subfolder in Folder().childFolders(
            folder, 'folder', user=user, sort=[('lowerName', SortDir.ASCENDING)]):
        item = get_first_item(subfolder, user, exclude)
        if item is not None and str(subfolder['_id']) not in excludeset:
            with ItemActionLock:
                if item['_id'] not in [entry['_id'] for entry in ItemActionList]:
                    return item


def ingestData(user=None, progress=True):
    """
    Ingest data from the import folder.

    :param user: the user that started this.
    """
    with ProgressContext(progress, user=user, title='Importing data') as ctx:
        with IngestLock:
            result = import_export.ingestData(ctx, user)
    result['action'] = 'ingest'
    return result


def exportData(user=None, progress=True):
    """
    Export data to the export folder.

    :param user: the user that started this.
    """
    with ProgressContext(progress, user=user, title='Exporting recent finished items') as ctx:
        with ExportLock:
            result = import_export.exportItems(ctx, user)
    result['action'] = 'export'
    return result


class WSIDeIDResource(Resource):
    def __init__(self, apiRoot):
        super().__init__()
        self.resourceName = 'wsi_deid'
        self.route('PUT', ('action', 'export'), self.export)
        self.route('PUT', ('action', 'exportall'), self.exportAll)
        self.route('PUT', ('action', 'exportreport'), self.exportReport)
        # self.route('PUT', ('action', 'finishlist'), self.finishItemList)
        self.route('PUT', ('action', 'ingest'), self.ingest)
        self.route('PUT', ('action', 'list', ':action'), self.itemListAction)
        self.route('PUT', ('action', 'ocrall'), self.ocrReadyToProcess)
        self.route('GET', ('folder', ':id', 'item_list'), self.folderItemList)
        self.route('GET', ('folder', ':id', 'refileList'), self.getRefileListFolder)
        self.route('PUT', ('item', ':id', 'action', ':action'), self.itemAction)
        self.route('PUT', ('item', ':id', 'action', 'refile'), self.refileItem)
        self.route('POST', ('item', ':id', 'action', 'refile', ':tokenId'), self.refileItemFull)
        self.route('PUT', ('folder', ':id', 'action', ':action'), self.folderAction)
        self.route('POST', ('folder', ':id', 'action', 'refile', ':tokenId'),
                   self.refileFolderFull)
        self.route('PUT', ('action', 'bulkRefile'), self.refileItems)
        self.route('PUT', ('item', ':id', 'redactList'), self.setRedactList)
        self.route('GET', ('item', ':id', 'refileList'), self.getRefileList)
        self.route('GET', ('item', ':id', 'status'), self.itemStatus)
        self.route('GET', ('next_unprocessed_folders', ), self.nextUnprocessedFolders)
        self.route('GET', ('next_unprocessed_item', ), self.nextUnprocessedItem)
        self.route('GET', ('project_folder', ':id'), self.isProjectFolder)
        self.route('GET', ('resource', ':id', 'subtreeCount'), self.getSubtreeCount)
        self.route('GET', ('schema',), self.getSchema)
        self.route('GET', ('settings',), self.getSettings)
        self.route('POST', ('matching', ), self.callMatchingAPI)
        self.route('POST', ('matching', 'wsi'), self.fakeMatchingAPI)
        self.route('GET', ('status', ), self.allItemStatus)
        self._item_find = apiRoot.item._find

    @autoDescribeRoute(
        Description('Check if a folder is a project folder.')
        .modelParam('id', model=Folder, level=AccessType.READ)
        .errorResponse(),
    )
    @access.public(scope=TokenScope.DATA_READ)
    def isProjectFolder(self, folder):
        return import_export.isProjectFolder(folder)

    def _actionForItem(self, item, user, action, options=None):
        """
        Given an item, user, an action, return a function and parameters to
        execute that action.

        :param item: an item document.
        :param user: the user document.
        :param action: an action string.
        :returns: the action function, a tuple of arguments to pass to it, the
            name of the action, and the present participle of the action.
        """
        actionmap = {
            'quarantine': (
                histomicsui.handlers.quarantine_item, (item, user, False),
                'quarantine', 'quarantining'),
            'unquarantine': (
                histomicsui.handlers.restore_quarantine_item, (item, user),
                'unquarantine', 'unquaranting'),
            'reject': (
                move_item, (item, user, PluginSettings.HUI_REJECTED_FOLDER, options),
                'reject', 'rejecting'),
            'finish': (
                move_item, (item, user, PluginSettings.HUI_FINISHED_FOLDER),
                'approve', 'approving'),
            'process': (
                process_item, (item, user),
                'redact', 'redacting'),
            'ocr': (
                ocr_item, (item, user),
                'scan', 'scanning'),
        }
        return actionmap[action]

    @autoDescribeRoute(
        Description('Perform an action on an item.')
        # Allow all users to do redaction actions; change to WRITE otherwise
        .modelParam('id', model=Item, level=AccessType.READ)
        .param('action', 'Action to perform on the item.  One of process, '
               'reject, quarantine, unquarantine, finish, ocr.', paramType='path',
               enum=['process', 'reject', 'quarantine', 'unquarantine', 'finish', 'ocr'])
        .jsonParam('options', 'Additional information pertaining to the action.',
                   required=False, paramType='body')
        .errorResponse()
        .errorResponse('Write access was denied on the item.', 403),
    )
    @access.user
    def itemAction(self, item, action, options):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        with ItemActionLock:
            ItemActionList.append(item)
        try:
            actionfunc, actionargs, name, pp = self._actionForItem(item, user, action, options)
        finally:
            with ItemActionLock:
                ItemActionList.remove(item)
        return actionfunc(*actionargs)

    @autoDescribeRoute(
        Description('Set the redactList meta value on an item.')
        .responseClass('Item')
        # we allow all users to do this; change to WRITE to do otherwise.
        .modelParam('id', model=Item, level=AccessType.READ)
        .jsonParam('redactList', 'A JSON object containing the redactList to set',
                   paramType='body', requireObject=True)
        .errorResponse(),
    )
    @access.user
    def setRedactList(self, item, redactList):
        return Item().setMetadata(item, {'redactList': redactList})

    @autoDescribeRoute(
        Description('Ingest data from the import folder asynchronously.')
        .errorResponse(),
    )
    @access.user
    def ingest(self):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        return ingestData(user)

    @autoDescribeRoute(
        Description('Export recently finished items to the export folder asynchronously.')
        .errorResponse(),
    )
    @access.user
    def export(self):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        return exportData(user)

    @autoDescribeRoute(
        Description('Export all finished items to the export folder asynchronously.')
        .errorResponse(),
    )
    @access.user
    def exportAll(self):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        with ProgressContext(True, user=user, title='Exporting all finished items') as ctx:
            result = import_export.exportItems(ctx, user, True)
        result['action'] = 'exportall'
        return result

    @autoDescribeRoute(
        Description('Generate a report of the items in the system.')
        .errorResponse(),
    )
    @access.user
    def exportReport(self):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        with ProgressContext(True, user=user, title='Reporting on items') as ctx:
            result = import_export.exportItems(ctx, user, True, True)
        result['action'] = 'exportreport'
        return result

    @autoDescribeRoute(
        Description('Run OCR to find label text on items in the import folder without OCR metadata')
        .errorResponse(),
    )
    @access.user
    def ocrReadyToProcess(self):
        user = self.getCurrentUser()
        itemIds = []
        ingestFolder = Folder().load(Setting().get(
            PluginSettings.HUI_INGEST_FOLDER), user=user, level=AccessType.WRITE,
        )
        resp = {'action': 'ocrall'}
        for _, file in Folder().fileList(ingestFolder, user, data=False):
            itemId = file['itemId']
            item = Item().load(itemId, force=True)
            if (item.get('meta', {}).get('label_ocr', None) is None and
                    item.get('meta', {}).get('macro_ocr', None) is None):
                itemIds.append(file['itemId'])
        if len(itemIds) > 0:
            jobStart = datetime.datetime.now().strftime('%Y%m%d %H%M%S')
            batchJob = Job().createLocalJob(
                module='wsi_deid.jobs',
                function='start_ocr_batch_job',
                title=f'Batch OCR triggered manually: {user["login"]}, {jobStart}',
                type='wsi_deid.batch_ocr',
                user=user,
                asynchronous=True,
                args=(itemIds,),
            )
            Job().scheduleJob(job=batchJob)
            resp['ocrJobId'] = batchJob['_id']
        return resp

    @autoDescribeRoute(
        Description('Get the ID of the next unprocessed item.')
        .errorResponse(),
    )
    @access.user
    def nextUnprocessedItem(self):
        user = self.getCurrentUser()
        for settingKey in (
                PluginSettings.WSI_DEID_UNFILED_FOLDER,
                PluginSettings.HUI_INGEST_FOLDER,
                PluginSettings.HUI_QUARANTINE_FOLDER,
                PluginSettings.HUI_PROCESSED_FOLDER):
            folderId = Setting().get(settingKey)
            if folderId:
                try:
                    folder = Folder().load(folderId, user=user, level=AccessType.READ)
                except AccessException:
                    # Don't return a result if we don't have read access
                    continue
                if folder:
                    item = get_first_item(folder, user)
                    if item is not None:
                        return str(item['_id'])

    @autoDescribeRoute(
        Description(
            'Get the IDs of the next two folders with unprocessed items and '
            'the id of the finished folder.')
        .errorResponse(),
    )
    @access.user
    def nextUnprocessedFolders(self):
        user = self.getCurrentUser()
        folders = []
        exclude = None
        for _ in range(2):
            # Reverse priority
            for settingKey in (
                PluginSettings.HUI_PROCESSED_FOLDER,
                PluginSettings.HUI_QUARANTINE_FOLDER,
                PluginSettings.HUI_INGEST_FOLDER,
            ):
                folder = Folder().load(Setting().get(settingKey), user=user, level=AccessType.READ)
                item = get_first_item(folder, user, exclude, exclude is not None)
                if item is not None:
                    parent = Folder().load(item['folderId'], user=user, level=AccessType.READ)
                    folders[0:0] = [str(parent['_id'])]
                    exclude = [parent]
                    break
            if not exclude:
                break
        folders.append(Setting().get(PluginSettings.HUI_FINISHED_FOLDER))
        return folders

    @autoDescribeRoute(
        Description('Get settings that affect the UI.')
        .errorResponse(),
    )
    @access.public(scope=TokenScope.DATA_READ)
    def getSettings(self):
        results = config.getConfig().copy()
        for key in {PluginSettings.WSI_DEID_DB_API_URL}:
            results[key] = Setting().get(key)
        return results

    @access.public
    @autoDescribeRoute(
        Description('Get total subtree folder and item counts of a resource by ID.')
        .param('id', 'The ID of the resource.', paramType='path')
        .param('type', 'The type of the resource (folder, user, collection).')
        .errorResponse('ID was invalid.')
        .errorResponse('Read access was denied for the resource.', 403),
    )
    def getSubtreeCount(self, id, type):
        user = self.getCurrentUser()
        model = ModelImporter.model(type)
        doc = model.load(id=id, user=self.getCurrentUser(), level=AccessType.READ)
        if not hasattr(self, '_pendingSubtreeCounts'):
            self._pendingSubtreeCounts = {}
        key = (user['_id'] if user else None, doc['_id'])
        try:
            # Don't make the request a second time if we made it recently
            # and think it is pending.  Some subtree counts can take minutes
            if time.time() - self._pendingSubtreeCounts.get(key, 0) < 3600:
                return
            self._pendingSubtreeCounts[key] = time.time()
            folderCount = model.subtreeCount(doc, False, user=user, level=AccessType.READ)
            totalCount = model.subtreeCount(doc, True, user=user, level=AccessType.READ)
        finally:
            try:
                del self._pendingSubtreeCounts[key]
            except Exception:
                pass
        return {'folders': folderCount, 'items': totalCount - folderCount, 'total': totalCount}

    def _folderItemListGetItem(self, item):
        try:
            metadata = ImageItem().getMetadata(item)
        except Exception:
            return None
        internal_metadata = ImageItem().getInternalMetadata(item)
        images = ImageItem().getAssociatedImagesList(item)
        return {
            'item': item,
            'metadata': metadata,
            'internal_metadata': internal_metadata,
            'images': images,
        }

    def _commonValues(self, common, entry):
        if common is None:
            return copy.deepcopy(entry)
        for k, v in entry.items():
            if isinstance(v, dict):
                if isinstance(common.get(k), dict):
                    self._commonValues(common[k], v)
                elif k in common:
                    del common[k]
            elif k in common and common.get(k) != v:
                del common[k]
        for k in list(common.keys()):
            if k not in entry:
                del common[k]
        return common

    def _allKeys(self, allkeys, entry, parent=None):
        for k, v in entry.items():
            subkey = tuple(list(parent or ()) + [k])
            if isinstance(v, dict):
                self._allKeys(allkeys, v, subkey)
            else:
                allkeys.add(subkey)

    @autoDescribeRoute(
        Description(
            'Return a list of all items in a folder with enough information '
            'to allow review and redaction.')
        .modelParam('id', model=Folder, level=AccessType.READ)
        .jsonParam('images', 'A list of image ids to include', required=False)
        .param('recurse', 'Return items recursively under this folder.',
               dataType='boolean', default=False, required=False)
        .pagingParams(defaultSort='lowerName')
        .errorResponse()
        .errorResponse('Read access was denied on the parent folder.', 403),
    )
    @access.public(scope=TokenScope.DATA_READ)
    def folderItemList(self, folder, images, limit, offset, sort, recurse):
        import concurrent.futures

        starttime = time.time()
        user = self.getCurrentUser()
        filters = {'largeImage.fileId': {'$exists': True}}
        if isinstance(images, list):
            filters['_id'] = {'$in': [ObjectId(id) for id in images]}
        text = '_recurse_:' if recurse else None
        cursor = self._item_find(
            folder['_id'], text=text, name=None, limit=limit, offset=offset,
            sort=sort, filters=filters)
        response = {
            'sort': sort,
            'offset': offset,
            'limit': limit,
            'count': cursor.count(),
            'folder': folder,
            'rootpath': Folder().parentsToRoot(folder, user=user, level=AccessType.READ),
            'large_image_settings': {
                k: Setting().get(k) for k in [
                    getattr(girder_large_image.constants.PluginSettings, key)
                    for key in dir(girder_large_image.constants.PluginSettings)
                    if key.startswith('LARGE_IMAGE_')]},
            'wsi_deid_settings': config.getConfig(),
        }
        with concurrent.futures.ThreadPoolExecutor() as executor:
            response['items'] = [
                item for item in
                executor.map(self._folderItemListGetItem, cursor)
                if item is not None]
        images = {}
        common = None
        allmeta = set()
        for item in response['items']:
            for image in item['images']:
                images[image] = images.get(image, 0) + 1
            common = self._commonValues(common, item['internal_metadata'])
            self._allKeys(allmeta, item['internal_metadata'])
        response['images'] = images
        response['image_names'] = [entry[-1] for entry in sorted(
            [(key != 'label', key != 'macro', key) for key in images.keys()])]
        response['common_internal_metadata'] = common
        response['all_metadata_keys'] = [list(entry) for entry in sorted(allmeta)]
        response['_time'] = time.time() - starttime
        return response

    @autoDescribeRoute(
        Description('Perform an action on a list of items.')
        .jsonParam('ids', 'A list of item ids to redact', required=True)
        # Allow all users to do redaction actions; change to WRITE otherwise
        .param('action', 'Action to perform on the item.  One of process, '
               'reject, quarantine, unquarantine, finish, ocr.', paramType='path',
               enum=['process', 'reject', 'quarantine', 'unquarantine', 'finish', 'ocr'])
        .errorResponse()
        .errorResponse('Write access was denied on the item.', 403),
    )
    @access.user
    def itemListAction(self, ids, action):
        setResponseTimeLimit(86400)
        if not len(ids):
            return
        user = self.getCurrentUser()
        items = [Item().load(id=id, user=user, level=AccessType.READ) for id in ids]
        self._itemListAction(action, items, user)
        return len(items)

    def _itemListAction(self, action, items, user):
        actionfunc, actionargs, actname, pp = self._actionForItem(items[0], user, action)
        with ItemActionLock:
            ItemActionList.extend(items)
        try:
            with ProgressContext(
                True, user=user, title='%s items' % pp.capitalize(),
                message='%s %s' % (pp.capitalize(), items[0]['name']),
                total=len(items), current=0,
            ) as ctx:
                try:
                    for idx, item in enumerate(items):
                        actionfunc, actionargs, actname, pp = self._actionForItem(
                            item, user, action)
                        ctx.update(
                            message='%s %s' % (pp.capitalize(), item['name']),
                            total=len(items), current=idx)
                        try:
                            actionfunc(*actionargs)
                        except Exception:
                            logger.exception('Failed to %s item' % actname)
                            ctx.update('Error %s %s' % (pp, item['name']))
                            raise
                    ctx.update(message='Done %s' % pp, total=len(items), current=len(items))
                except Exception:
                    pass
        finally:
            with ItemActionLock:
                for item in items:
                    ItemActionList.remove(item)

    @autoDescribeRoute(
        Description('Perform an action on a folder of items.')
        .modelParam('id', 'The folder ID', model=Folder, level=AccessType.READ)
        .param('action', 'Action to perform on the item.  One of process, '
               'reject, quarantine, unquarantine, finish, ocr.', paramType='path',
               enum=['process', 'reject', 'quarantine', 'unquarantine', 'finish', 'ocr'])
        .param('limit', 'Maximum number of items in folder to process',
               required=False, dataType='int')
        .param('recurse', 'Return items recursively under this folder.',
               dataType='boolean', default=False, required=False)
        .errorResponse(),
    )
    @access.user
    def folderAction(self, folder, action, limit=None, recurse=False):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        text = '_recurse_:' if recurse else None
        filters = {'largeImage.fileId': {'$exists': True}}
        limit = int(limit or 0)
        sort = [('lowerName', SortDir.ASCENDING)]
        items = list(self._item_find(
            folder['_id'], text=text, name=None, limit=limit, offset=0,
            sort=sort, filters=filters))
        self._itemListAction(action, items, user)
        return len(items)

    @autoDescribeRoute(
        Description('Get the list of known and allowed image names for refiling.')
        .modelParam('id', model=Item, level=AccessType.READ)
        .errorResponse(),
    )
    @access.user
    def getRefileList(self, item):
        imageIds = []
        for imageId in item.get('wsi_uploadInfo', {}):
            if not imageId.startswith(TokenOnlyPrefix) and not Item().findOne({
                    'name': {'$regex': '^' + re.escape(imageId) + r'\..*'}}):
                imageIds.append(imageId)
        for imageId in item.get('wsi_uploadInfo', {}):
            if imageId.startswith(TokenOnlyPrefix):
                baseImageId = imageId[len(TokenOnlyPrefix):]
                if baseImageId not in imageIds:
                    imageIds.append(baseImageId)
        return sorted(imageIds)

    @autoDescribeRoute(
        Description('Get the list of known and allowed image names for refiling.')
        .modelParam('id', model=Folder, level=AccessType.READ)
        .errorResponse(),
    )
    @access.user
    def getRefileListFolder(self, folder):
        imageIds = set()
        for item in Folder().childItems(folder):
            for imageId in item.get('wsi_uploadInfo', {}) or []:
                if not imageId.startswith(TokenOnlyPrefix) and not Item().findOne({
                        'name': {'$regex': '^' + re.escape(imageId) + r'\..*'}}):
                    imageIds.add(imageId)
            for imageId in item.get('wsi_uploadInfo', {}) or []:
                if imageId.startswith(TokenOnlyPrefix):
                    baseImageId = imageId[len(TokenOnlyPrefix):]
                    if baseImageId not in imageIds:
                        imageIds.add(baseImageId)
        return sorted(imageIds)

    @autoDescribeRoute(
        Description('Get the current import schema')
        .errorResponse(),
    )
    @access.admin
    def getSchema(self):
        return import_export.getSchema()

    @autoDescribeRoute(
        Description('Perform an action on an item.')
        .responseClass('Item')
        # Allow all users to do redaction actions; change to WRITE otherwise
        .modelParam('id', model=Item, level=AccessType.READ)
        .param('imageId', 'The new imageId')
        .param('tokenId', 'The new tokenId', required=False)
        .errorResponse()
        .errorResponse('Write access was denied on the item.', 403),
    )
    @access.user
    def refileItem(self, item, imageId, tokenId):
        folderNameField = config.getConfig('folder_name_field', 'TokenID')
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        if imageId and imageId != item['name'].split('.', 1)[0] and Item().findOne({
                'name': {'$regex': '^' + re.escape(imageId) + r'\..*'}}):
            msg = 'An image with that name already exists.'
            raise RestException(msg)
        if not imageId:
            imageId = TokenOnlyPrefix + tokenId
        uploadInfo = item.get('wsi_uploadInfo')
        if uploadInfo and TokenOnlyPrefix + imageId in uploadInfo:
            imageId = TokenOnlyPrefix + imageId
        if uploadInfo and imageId in uploadInfo:
            tokenId = uploadInfo[imageId].get(folderNameField, tokenId)
        if not tokenId:
            tokenId = imageId.split('_', 1)[0]
        item = process.refile_image(item, user, tokenId, imageId, uploadInfo)
        return item

    @autoDescribeRoute(
        Description('Refile an item with a specific token ID.')
        .responseClass('Item')
        # Allow all users to do redaction actions; change to WRITE otherwise
        .modelParam('id', model=Item, level=AccessType.READ)
        .param('tokenId', 'The new tokenId', required=True)
        .jsonParam('refileData', 'Data used instead of internal data', paramType='body')
        .errorResponse('Write access was denied on the item.', 403),
    )
    @access.user
    def refileItemFull(self, item, tokenId, refileData):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        imageId = TokenOnlyPrefix + tokenId
        item = process.refile_image(
            item, user, tokenId, imageId, {imageId: {'fields': refileData}})
        return item

    @autoDescribeRoute(
        Description('Refile items in a folder with a specific token ID.')
        .modelParam('id', 'The folder ID', model=Folder, level=AccessType.READ)
        .param('tokenId', 'The new tokenId', required=True)
        .param('limit', 'Maximum number of items in folder to process',
               required=False, dataType='int')
        .param('recurse', 'Return items recursively under this folder.',
               dataType='boolean', default=False, required=False),
    )
    @access.user
    def refileFolderFull(self, folder, tokenId, limit=None, recurse=False):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        text = '_recurse_:' if recurse else None
        filters = {'largeImage.fileId': {'$exists': True}}
        sort = [('lowerName', SortDir.ASCENDING)]
        processedImageIds = []
        limit = int(limit or 0)
        for item in self._item_find(
                folder['_id'], text=text, name=None, limit=limit, offset=0,
                sort=sort, filters=filters):
            imageId = TokenOnlyPrefix + tokenId
            uploadInfo = item.get('wsi_uploadInfo')
            if uploadInfo and TokenOnlyPrefix + imageId in uploadInfo:
                imageId = TokenOnlyPrefix + imageId
            item = process.refile_image(item, user, tokenId, imageId, uploadInfo)
            processedImageIds += [imageId]
        return processedImageIds

    @autoDescribeRoute(
        Description('Refile multiple images at once.')
        .jsonParam('imageRefileData', 'Data used to refile images', paramType='body')
        .errorResponse()
        .errorResponse('Write access was denied for an item.', 403),
    )
    @access.user
    def refileItems(self, imageRefileData):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        folderNameField = config.getConfig('folder_name_field', 'TokenID')
        processedImageIds = []
        for itemId in imageRefileData:
            item = Item().load(itemId, user=user, level=AccessType.READ)
            uploadInfo = item.get('wsi_uploadInfo')
            tokenId = imageRefileData[itemId]['tokenId']
            imageId = imageRefileData[itemId]['imageId']
            if imageId and imageId != item['name'].split('.', 1)[0] and Item().findOne({
                    'name': {'$regex': '^' + re.escape(imageId) + r'\..*'}}):
                msg = 'An image with that name already exists.'
                raise RestException(msg)
            if not imageId:
                imageId = TokenOnlyPrefix + tokenId
            uploadInfo = item.get('wsi_uploadInfo')
            if uploadInfo and TokenOnlyPrefix + imageId in uploadInfo:
                imageId = TokenOnlyPrefix + imageId
            if uploadInfo and imageId in uploadInfo:
                tokenId = uploadInfo[imageId].get(folderNameField, tokenId)
            if not tokenId:
                tokenId = imageId.split('_', 1)[0]
            item = process.refile_image(item, user, tokenId, imageId, uploadInfo)
            processedImageIds += [imageId]
        return processedImageIds

    @autoDescribeRoute(
        Description('Pass a set of values to the Matching API.')
        .jsonParam('match', 'JSON match data', paramType='body'),
    )
    @access.public
    def callMatchingAPI(self, match):
        from .matching_api import APISearch

        apisearch = APISearch()
        match = {k: v for k, v in match.items() if v}
        for key in match:
            if 'date' in key:
                matches = {}
                apisearch.addMatches(matches, key, match[key])
                if len(matches[key]):
                    match[key] = matches[key][0]['value']
        queries = [match]
        if 'name_first' in match or 'name_last' in match:
            swaps = {'name_first': 'name_last', 'name_last': 'name_first'}
            alt_match = {swaps.get(k, k): v for k, v in match.items()}
            queries.append(alt_match)
        if 'date_of_service' in match or 'date_of_birth' in match:
            swaps = {'date_of_birth': 'date_of_service', 'date_of_service': 'date_of_birth'}
            for entry in queries.copy():
                alt_match = {swaps.get(k, k): v for k, v in entry.items()}
                queries.append(alt_match)
        return apisearch.lookupQueries(queries)

    @autoDescribeRoute(  # noqa
        Description('Simulate the SEER*DMS Matching API for testing.')
        .jsonParam('match', 'JSON match data', paramType='body'),
    )
    @access.public
    def fakeMatchingAPI(self, match):  # noqa
        from .matching_api import APISearch

        fakeData = []
        try:
            filepath = '/conf/fake_matches.json'
            if not os.path.exists(filepath):
                filepath = os.path.join(os.path.expanduser('~'), '.girder', 'fake_matches.json')
            fakeData = json.load(open(filepath))
        except Exception:
            pass
        results = []
        for matchMethod in APISearch.apiMatchMethods:
            for entry in fakeData:
                matched = True
                try:
                    for key in matchMethod:
                        if key not in match or key not in entry:
                            matched = False
                        elif (key in {'name_last', 'name_first'} and
                                match[key].lower() != entry[key].lower()):
                            matched = False
                        elif key == 'date_of_birth' and match[key].lower() != entry[key].lower():
                            matched = False
                        elif key == 'date_of_service' and abs((
                            datetime.datetime.strptime(match[key], '%m-%d-%Y').date() -
                            datetime.datetime.strptime(entry[key], '%m-%d-%Y').date()
                        ).days) > 10:
                            matched = False
                        elif key == 'path_case_num' and re.sub(
                                r'[^\w]', '', match[key]).lower() != re.sub(
                                    r'[^\w]', '', entry[key]).lower():
                            matched = False
                except Exception:
                    matched = False
                if matched:
                    results.append(entry['result'])
            if len(results):
                return results
        return results

    def _allItemStatus(self):
        project_folders = []
        results = {'folders': {}, 'items': {}}
        for key, val in ProjectFolders.items():
            if key == 'original':
                continue
            projFolderId = Setting().get(val)
            project_folders.append(ObjectId(projFolderId))
            results['folders'][projFolderId] = {
                'key': val,
                'name': Folder().load(projFolderId, force=True)['name'],
                'items': {}}
        pipeline = [
            {'$match': {'_id': {'$in': project_folders}}},
            {'$graphLookup': {
                'from': 'folder',
                'startWith': '$_id',
                'connectFromField': '_id',
                'connectToField': 'parentId',
                'as': 'descendants',
                'restrictSearchWithMatch': {'parentCollection': 'folder'}}},
            {'$project': {
                'rootFolderId': '$_id', 'rootFolderName': '$name', 'allFolders': {
                    '$concatArrays': [
                        ['$_id'],
                        {'$map': {'input': '$descendants', 'as': 'desc', 'in': '$$desc._id'}},
                    ]}}},
            {'$unwind': '$allFolders'},
            {'$lookup': {
                'from': 'item',
                'localField': 'allFolders',
                'foreignField': 'folderId',
                'as': 'item'}},
            {'$unwind': '$item'},
            {'$project': {
                'folderId': '$_id',
                'folderName': '$name',
                'itemId': '$item._id',
                'itemName': '$item.name'}},
        ]

        for entry in Folder().collection.aggregate(pipeline):
            results['folders'][str(entry['folderId'])]['items'][
                str(entry['itemId'])] = {'name': entry['itemName']}
            results['items'][str(entry['itemId'])] = {
                'folder': results['folders'][str(entry['folderId'])]['key'],
                'name': entry['itemName'],
            }
        return results

    @autoDescribeRoute(
        Description('Get the status of all tracked items in wsi_deid folders')
        .errorResponse(),
    )
    @access.admin
    def allItemStatus(self):
        return self._allItemStatus()

    @autoDescribeRoute(
        Description('Get the status of a tracked item.')
        .modelParam('id', model=Item, level=AccessType.READ)
        .errorResponse(),
    )
    @access.admin
    def itemStatus(self, item):
        results = self._allItemStatus()
        return results['items'].get(str(item['_id']), None)


def addSystemEndpoints(apiRoot):
    """
    This adds endpoints to routes that already exist in Girder.

    :param apiRoot: Girder api root class.
    """
    # Added to the system route
    apiRoot.system.route('GET', ('config',), getCurrentConfig)


@access.admin(scope=TokenScope.SETTINGS_READ)
@autoDescribeRoute(
    Description('Get the current system config and full settings.')
    .notes('Must be a system administrator to call this.')
    .param('includeSettings', 'False to only show config; true to include full '
           'settings.', required=False, dataType='boolean', default=False)
    .errorResponse('You are not a system administrator.', 403),
)
@boundHandler
def getCurrentConfig(self, includeSettings=False):
    import json

    from girder.utility import config
    result = {}
    for k, v in config.getConfig().items():
        if isinstance(v, dict):
            result[k] = {}
            for subk, subv in v.items():
                if not callable(subv):
                    try:
                        result[k][subk] = json.loads(json.dumps(subv))
                    except Exception:
                        print(k, subk, subv)
        elif not callable(v):
            result[k] = v
    if includeSettings:
        result['settings'] = {}
        for record in Setting().find({}):
            result['settings'][record['key']] = record['value']
        envkeys = {key for key in os.environ if key.startswith('GIRDER_SETTING_')}
        if len(envkeys):
            result['environment'] = {key: os.environ.get(key) for key in envkeys}
    return result
