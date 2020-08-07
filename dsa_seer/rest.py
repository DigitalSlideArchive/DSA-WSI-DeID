from girder.api import access
from girder.api.describe import Description, autoDescribeRoute
from girder.api.rest import Resource
from girder.constants import AccessType, TokenScope
from girder.models.folder import Folder as FolderModel
from girder.models.setting import Setting

from .constants import PluginSettings


class DSASeerResource(Resource):
    def __init__(self):
        super(DSASeerResource, self).__init__()
        self.resourceName = 'dsaseer'
        self.route('GET', ('project_folder', ':id'), self.isProjectFolder)

    @autoDescribeRoute(
        Description('Check if a folder is a project folder.')
        .modelParam('id', model=FolderModel, level=AccessType.WRITE)
        .errorResponse()
        .errorResponse('Read access was denied on the folder.', 403)
    )
    @access.public(scope=TokenScope.DATA_READ)
    def isProjectFolder(self, folder):
        project_folders = {
            'quarantine': PluginSettings.HUI_QUARANTINE_FOLDER,
            'processed': PluginSettings.HUI_PROCESSED_FOLDER,
            'rejected': PluginSettings.HUI_REJECTED_FOLDER,
            'original': PluginSettings.HUI_ORIGINAL_FOLDER,
        }
        result = None
        for key in project_folders:
            projFolderId = Setting().get(project_folders[key])
            if str(folder['_id']) == projFolderId:
                result = key
                break
        return result
