import datetime
import os
import tempfile

from girder import logger
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource
from girder.constants import AccessType, SortDir, TokenScope
from girder.exceptions import RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.upload import Upload
from girder.models.user import User
from girder.utility.progress import setResponseTimeLimit, ProgressContext

from girder_large_image.models.image_item import ImageItem
import histomicsui.handlers

from .constants import PluginSettings
from . import process
from . import import_export


ProjectFolders = {
    'ingest': PluginSettings.HUI_INGEST_FOLDER,
    'quarantine': PluginSettings.HUI_QUARANTINE_FOLDER,
    'processed': PluginSettings.HUI_PROCESSED_FOLDER,
    'rejected': PluginSettings.HUI_REJECTED_FOLDER,
    'original': PluginSettings.HUI_ORIGINAL_FOLDER,
    'finished': PluginSettings.HUI_FINISHED_FOLDER,
}


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
    projFolderIds = [Setting().get(ProjectFolders[key]) for key in ProjectFolders]
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
    # create new folder structre
    for name in origPath:
        folder = Folder().createFolder(folder, name=name, creator=user, reuseExisting=True)
    return folder, origFolders


def move_item(item, user, settingkey):
    """
    Move an item to one of the folders specified by a setting.

    :param item: the item model to move.
    :param user: a user for folder creation.
    :param settingkey: one of the PluginSettings values.
    :returns: the item after move.
    """
    folderId = Setting().get(settingkey)
    if not folderId:
        raise RestException('The appropriate folder is not configured.')
    folder = Folder().load(folderId, force=True)
    if not folder:
        raise RestException('The appropriate folder does not exist.')
    if str(folder['_id']) == str(item['folderId']):
        raise RestException('The item is already in the appropriate folder.')
    folder, origFolders = create_folder_hierarchy(item, user, folder)
    if settingkey == PluginSettings.HUI_QUARANTINE_FOLDER:
        quarantineInfo = {
            'originalFolderId': item['folderId'],
            'originalBaseParentType': item['baseParentType'],
            'originalBaseParentId': item['baseParentId'],
            'originalUpdated': item['updated'],
            'quarantineUserId': user['_id'],
            'quarantineTime': datetime.datetime.utcnow()
        }
    # move the item
    item = Item().move(item, folder)
    if settingkey == PluginSettings.HUI_QUARANTINE_FOLDER:
        # When quarantining, add metadata and don't prune folders
        item = Item().setMetadata(item, {'quarantine': quarantineInfo})
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


def process_item(item, user=None):
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
        raise RestException('The appropriate folder is not configured.')
    origFolder = Folder().load(origFolderId, force=True)
    procFolder = Folder().load(procFolderId, force=True)
    if not origFolder or not procFolder:
        raise RestException('The appropriate folder does not exist.')
    creator = User().load(item['creatorId'], force=True)
    # Generate the redacted file first, so if it fails we don't do anything
    # else
    with tempfile.TemporaryDirectory(prefix='nciseer') as tempdir:
        try:
            filepath, info = process.redact_item(item, tempdir)
        except Exception as e:
            logger.exception('Failed to redact item')
            raise RestException(e.args[0])
        origFolder, _ = create_folder_hierarchy(item, user, origFolder)
        origItem = Item().copyItem(item, creator, folder=origFolder)
        origItem = Item().setMetadata(origItem, {
            'nciseerProcessed': {
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
        if len(os.path.splitext(newName)[1]) <= 1:
            newName = os.path.splitext(item['name'])[0] + os.path.splitext(filepath)[1]
        newSize = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            Upload().uploadFromFile(
                f, size=os.path.getsize(filepath), name=newName,
                parentType='item', parent=item, user=creator,
                mimeType=info['mimetype'])
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
    if 'nciseerExported' in item['meta']:
        item['meta']['redacted'][-1]['previousExports'] = item['meta']['nciseerExported']
    item['meta'].pop('nciseerExported', None)
    item['updated'] = datetime.datetime.utcnow()
    item = move_item(item, user, PluginSettings.HUI_PROCESSED_FOLDER)
    return item


def get_first_item(folder, user):
    """
    Get the first item in a folder or any subfolder of that folder.  The items
    are sorted aalphabetically.

    :param folder: the folder to search
    :returns: an item or None.
    """
    for item in Folder().childItems(folder, limit=1, sort=[('lowerName', SortDir.ASCENDING)]):
        return item
    for subfolder in Folder().childFolders(
            folder, 'folder', user=user, sort=[('lowerName', SortDir.ASCENDING)]):
        item = get_first_item(subfolder, user)
        if item is not None:
            return item


def ingestData(user=None, progress=True):
    """
    Ingest data from the import folder.

    :param user: the user that started this.
    """
    with ProgressContext(progress, user=user, title='Importing data') as ctx:
        result = import_export.ingestData(ctx, user)
    result['action'] = 'ingest'
    return result


def exportData(user=None, progress=True):
    """
    Export data to the export folder.

    :param user: the user that started this.
    """
    with ProgressContext(progress, user=user, title='Exporting recent finished items') as ctx:
        result = import_export.exportItems(ctx, user)
    result['action'] = 'export'
    return result


class NCISeerResource(Resource):
    def __init__(self):
        super(NCISeerResource, self).__init__()
        self.resourceName = 'nciseer'
        self.route('GET', ('project_folder', ':id'), self.isProjectFolder)
        self.route('GET', ('next_unprocessed_item', ), self.nextUnprocessedItem)
        self.route('PUT', ('item', ':id', 'action', ':action'), self.itemAction)
        self.route('PUT', ('item', ':id', 'redactList'), self.setRedactList)
        self.route('PUT', ('action', 'ingest'), self.ingest)
        self.route('PUT', ('action', 'export'), self.export)
        self.route('PUT', ('action', 'exportall'), self.exportAll)

    @autoDescribeRoute(
        Description('Check if a folder is a project folder.')
        .modelParam('id', model=Folder, level=AccessType.READ)
        .errorResponse()
        .errorResponse('Write access was denied on the folder.', 403)
    )
    @access.public(scope=TokenScope.DATA_READ)
    def isProjectFolder(self, folder):
        while folder:
            for key in ProjectFolders:
                projFolderId = Setting().get(ProjectFolders[key])
                if str(folder['_id']) == projFolderId:
                    return key
            if folder['parentCollection'] != 'folder':
                break
            folder = Folder().load(folder['parentId'], force=True)
        return None

    @autoDescribeRoute(
        Description('Perform an action on an item.')
        # Allow all users to do redaction actions; change to WRITE otherwise
        .modelParam('id', model=Item, level=AccessType.READ)
        .param('action', 'Action to perform on the item.  One of process, '
               'reject, quarantine, unquarantine, finish.', paramType='path',
               enum=['process', 'reject', 'quarantine', 'unquarantine', 'finish'])
        .errorResponse()
        .errorResponse('Write access was denied on the item.', 403)
    )
    @access.user
    def itemAction(self, item, action):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        actionmap = {
            'quarantine': (histomicsui.handlers.quarantine_item, (item, user, False)),
            'unquarantine': (histomicsui.handlers.restore_quarantine_item, (item, user)),
            'reject': (move_item, (item, user, PluginSettings.HUI_REJECTED_FOLDER)),
            'finish': (move_item, (item, user, PluginSettings.HUI_FINISHED_FOLDER)),
            'process': (process_item, (item, user)),
        }
        actionfunc, actionargs = actionmap[action]
        return actionfunc(*actionargs)

    @autoDescribeRoute(
        Description('Set the redactList meta value on an item.')
        .responseClass('Item')
        # we allow all users to do this; change to WRITE to do otherwise.
        .modelParam('id', model=Item, level=AccessType.READ)
        .jsonParam('redactList', 'A JSON object containing the redactList to set',
                   paramType='body', requireObject=True)
        .errorResponse()
    )
    @access.user
    def setRedactList(self, item, redactList):
        return Item().setMetadata(item, {'redactList': redactList})

    @autoDescribeRoute(
        Description('Ingest data from the import folder asynchronously.')
        .errorResponse()
    )
    @access.user
    def ingest(self):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        return ingestData(user)

    @autoDescribeRoute(
        Description('Export recently finished items to the export folder asynchronously.')
        .errorResponse()
    )
    @access.user
    def export(self):
        setResponseTimeLimit(86400)
        user = self.getCurrentUser()
        return exportData(user)

    @autoDescribeRoute(
        Description('Export all finished items to the export folder asynchronously.')
        .errorResponse()
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
        Description('Get the ID of the next unprocessed item.')
        .errorResponse()
    )
    @access.user
    def nextUnprocessedItem(self):
        user = self.getCurrentUser()
        for settingKey in (
                PluginSettings.HUI_INGEST_FOLDER, PluginSettings.HUI_QUARANTINE_FOLDER):
            folder = Folder().load(Setting().get(settingKey), user=user, level=AccessType.READ)
            item = get_first_item(folder, user)
            if item is not None:
                return str(item['_id'])
