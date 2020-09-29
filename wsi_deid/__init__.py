from girder import plugin
from girder.models.folder import Folder
from girder.utility import setting_utilities
from pkg_resources import DistributionNotFound, get_distribution

from .constants import PluginSettings
from .rest import WSIDeIDResource


try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = 'development'


@setting_utilities.validator({
    PluginSettings.HUI_INGEST_FOLDER,
    PluginSettings.HUI_QUARANTINE_FOLDER,
    PluginSettings.HUI_PROCESSED_FOLDER,
    PluginSettings.HUI_REJECTED_FOLDER,
    PluginSettings.HUI_ORIGINAL_FOLDER,
    PluginSettings.HUI_FINISHED_FOLDER,
    PluginSettings.HUI_REPORTS_FOLDER,
})
def validateSettingsFolder(doc):
    if not doc.get('value', None):
        doc['value'] = None
    else:
        Folder().load(doc['value'], force=True, exc=True)


@setting_utilities.validator({
    PluginSettings.WSI_DEID_IMPORT_PATH,
    PluginSettings.WSI_DEID_EXPORT_PATH,
})
def validateSettingsImportExport(doc):
    if not doc.get('value', None):
        doc['value'] = None


class GirderPlugin(plugin.GirderPlugin):
    DISPLAY_NAME = 'WSI DeID'
    CLIENT_SOURCE_PATH = 'web_client'

    def load(self, info):
        plugin.getPlugin('histomicsui').load(info)
        info['apiRoot'].wsi_deid = WSIDeIDResource()
