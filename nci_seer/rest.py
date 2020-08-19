import datetime
import os
import tempfile

from girder import logger
from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource
from girder.constants import AccessType, TokenScope
from girder.exceptions import RestException
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.upload import Upload
from girder.models.user import User

from girder_large_image.models.image_item import ImageItem
from histomicsui.rest.hui_resource import quarantine_item, restore_quarantine_item

from .constants import PluginSettings
from . import process


def move_item(item, settingkey):
    """
    Move an item to one of the folders specified by a setting.

    :param item: the item model to move.
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
    # Do we want to mirror the location in the destination that we are in a
    # current folder (do we need to move to a specific subfolder)?
    return Item().move(item, folder)


def process_item(item, user=None):
    """
    Copy an item to the original folder.  Modify the item by processing it and
    generating a new, redacted file.  Move the item to the processed folder.

    :param item: the item model to move.
    :param user: the user performing the processing.
    :returns: the item after move.
    """
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
            filepath, mimetype = process.redact_item(item, tempdir)
        except Exception as e:
            logger.exception('Failed to redact item')
            raise RestException(e.args[0])
        origItem = Item().copyItem(item, creator, folder=origFolder)
        origItem = Item().setMetadata(origItem, {
            'nciseerProcessed': {
                'itemId': str(item['_id']),
                'time': datetime.datetime.utcnow().isoformat(),
            },
        })
        ImageItem().delete(item)
        for childFile in Item().childFiles(item):
            File().remove(childFile)
        newName = os.path.splitext(item['name'])[0] + os.path.splitext(filepath)[1]
        with open(filepath, 'rb') as f:
            Upload().uploadFromFile(
                f, size=os.path.getsize(filepath), name=newName,
                parentType='item', parent=item, user=creator,
                mimeType=mimetype)
        item = Item().load(item['_id'], force=True)
        item['name'] = newName
    item.setdefault('meta', {})
    item['meta'].setdefault('redacted', [])
    item['meta']['redacted'].append({
        'user': str(user['_id']) if user else None,
        'time': datetime.datetime.utcnow().isoformat(),
    })
    item['meta'].pop('quarantine', None)
    item = Item().move(item, procFolder)
    return item


class NCISeerResource(Resource):
    def __init__(self):
        super(NCISeerResource, self).__init__()
        self.resourceName = 'nciseer'
        self.route('GET', ('project_folder', ':id'), self.isProjectFolder)
        self.route('PUT', ('item', ':id', 'action', ':action'), self.itemAction)

    @autoDescribeRoute(
        Description('Check if a folder is a project folder.')
        .modelParam('id', model=Folder, level=AccessType.WRITE)
        .errorResponse()
        .errorResponse('Write access was denied on the folder.', 403)
    )
    @access.public(scope=TokenScope.DATA_READ)
    def isProjectFolder(self, folder):
        project_folders = {
            'ingest': PluginSettings.HUI_INGEST_FOLDER,
            'quarantine': PluginSettings.HUI_QUARANTINE_FOLDER,
            'processed': PluginSettings.HUI_PROCESSED_FOLDER,
            'rejected': PluginSettings.HUI_REJECTED_FOLDER,
            'original': PluginSettings.HUI_ORIGINAL_FOLDER,
            'finished': PluginSettings.HUI_FINISHED_FOLDER,
        }
        while folder:
            for key in project_folders:
                projFolderId = Setting().get(project_folders[key])
                if str(folder['_id']) == projFolderId:
                    return key
            if folder['parentCollection'] != 'folder':
                break
            folder = Folder().load(folder['parentId'], force=True)
        return None

    @autoDescribeRoute(
        Description('Perform an action on an item.')
        .modelParam('id', model=Item, level=AccessType.WRITE)
        .param('action', 'Action to perform on the item.  One of process, '
               'reject, quarantine, unquarantine, finish.', paramType='path',
               enum=['process', 'reject', 'quarantine', 'unquarantine', 'finish'])
        .errorResponse()
        .errorResponse('Write access was denied on the item.', 403)
    )
    @access.public(scope=TokenScope.DATA_READ)
    def itemAction(self, item, action):
        user = self.getCurrentUser()
        actionmap = {
            'quarantine': (quarantine_item, (item, user, False)),
            'unquarantine': (restore_quarantine_item, (item, )),
            'reject': (move_item, (item, PluginSettings.HUI_REJECTED_FOLDER)),
            'finish': (move_item, (item, PluginSettings.HUI_FINISHED_FOLDER)),
            'process': (process_item, (item, user)),
        }
        actionfunc, actionargs = actionmap[action]
        return actionfunc(*actionargs)
