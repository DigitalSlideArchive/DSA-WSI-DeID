from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource
from girder.constants import AccessType, TokenScope
from girder.exceptions import RestException
from girder.models.folder import Folder as FolderModel
from girder.models.item import Item as ItemModel
from girder.models.setting import Setting

from histomicsui.rest.hui_resource import quarantine_item, restore_quarantine_item

from .constants import PluginSettings


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
    folder = FolderModel().load(folderId, force=True)
    if not folder:
        raise RestException('The appropriate folder does not exist.')
    if str(folder['_id']) == str(item['folderId']):
        raise RestException('The item is already in the appropriate folder.')
    # Do we want to mirror the location in the destination that we are in a
    # current folder (do we need to move to a specific subfolder)?
    return ItemModel().move(item, folder)


def process_item(item):
    pass


class NCISeerResource(Resource):
    def __init__(self):
        super(NCISeerResource, self).__init__()
        self.resourceName = 'nciseer'
        self.route('GET', ('project_folder', ':id'), self.isProjectFolder)
        self.route('PUT', ('item', ':id', 'action', ':action'), self.itemAction)

    @autoDescribeRoute(
        Description('Check if a folder is a project folder.')
        .modelParam('id', model=FolderModel, level=AccessType.WRITE)
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
            if folder['parentType'] != 'folder':
                break
            folder = FolderModel.load(folder['parentId'], force=True)
        return None

    @autoDescribeRoute(
        Description('Perform an action on an item.')
        .modelParam('id', model=ItemModel, level=AccessType.WRITE)
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
            'quarantine': (quarantine_item, (user, item)),
            'unquarantine': (restore_quarantine_item, (item, )),
            'reject': (move_item, (item, PluginSettings.HUI_REJECTED_FOLDER)),
            'finish': (move_item, (item, PluginSettings.HUI_FINISHED_FOLDER)),
            'process': (process_item, (item, )),
        }
        actionfunc, actionargs = actionmap[action]
        return actionfunc(*actionargs)
