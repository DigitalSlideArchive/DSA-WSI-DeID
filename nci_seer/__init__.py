from girder import plugin
from girder.models.folder import Folder
from girder.utility import setting_utilities
from pkg_resources import DistributionNotFound, get_distribution

from .constants import PluginSettings
from .rest import NCISeerResource


try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass


@setting_utilities.validator({
    PluginSettings.HUI_INGEST_FOLDER,
    PluginSettings.HUI_QUARANTINE_FOLDER,
    PluginSettings.HUI_PROCESSED_FOLDER,
    PluginSettings.HUI_REJECTED_FOLDER,
    PluginSettings.HUI_ORIGINAL_FOLDER,
    PluginSettings.HUI_FINISHED_FOLDER,
})
def validateSettingsFolder(doc):
    if not doc.get('value', None):
        doc['value'] = None
    else:
        Folder().load(doc['value'], force=True, exc=True)


class GirderPlugin(plugin.GirderPlugin):
    DISPLAY_NAME = 'NCI SEER Pediatic WSI Pilot'
    CLIENT_SOURCE_PATH = 'web_client'

    def load(self, info):
        info['apiRoot'].nciseer = NCISeerResource()
