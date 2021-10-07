import psutil

import girder
from girder import plugin, events
from girder.constants import AssetstoreType
from girder.exceptions import GirderException, ValidationException
from girder.models.assetstore import Assetstore
from girder.models.folder import Folder
from girder.models.setting import Setting
from girder.utility import setting_utilities
from pkg_resources import DistributionNotFound, get_distribution

from .constants import PluginSettings
from .rest import WSIDeIDResource
from .import_export import sftp_items


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
    PluginSettings.WSI_DEID_REMOTE_PATH,
    PluginSettings.WSI_DEID_REMOTE_HOST,
    PluginSettings.WSI_DEID_REMOTE_USER,
    PluginSettings.WSI_DEID_REMOTE_PASSWORD,
})
def validateSettingsImportExport(doc):
    if not doc.get('value', None):
        doc['value'] = None


@setting_utilities.validator(PluginSettings.WSI_DEID_REMOTE_PORT)
def validateRemoteSftpPort(doc):
    value = doc.get('value', None)
    if value is None:
        doc['value'] = None
    else:
        if not isinstance(value, int):
            raise ValidationException('Remote SFTP Port must be an integer value')


@setting_utilities.validator(PluginSettings.WSI_DEID_SFTP_MODE)
def validateSettingSftpMode(doc):
    if not doc['value'] in ['local', 'remote', 'both']:
        raise ValidationException('SFTP Mode must be one of "local", "remote", or "both"', 'value')


def handle_sftp_export(event):
    export_folder = event.info['export_folder']
    user = event.info['user']
    sftp_items(export_folder, user)


events.bind('wsi_deid.sftp_export', handle_sftp_export.__name__, handle_sftp_export)


class GirderPlugin(plugin.GirderPlugin):
    DISPLAY_NAME = 'WSI DeID'
    CLIENT_SOURCE_PATH = 'web_client'

    def load(self, info):
        plugin.getPlugin('histomicsui').load(info)
        info['apiRoot'].wsi_deid = WSIDeIDResource()
        memory = psutil.virtual_memory().total
        girder.logprint.info('Total system memory: %3.1f GB' % (memory / 1024**3))
        if memory < 3.5 * 1024**3:
            girder.logprint.warning(
                'Total system memory is lower than recommended.  Please '
                'increase it to 4 GB or more.')
        try:
            assetstore = Assetstore().getCurrent()
            assetstorePath = assetstore.get('root') if assetstore.get(
                'type') == AssetstoreType.FILESYSTEM else None
        except GirderException:
            assetstorePath = None
        for pathkey, path in (
                ('import', Setting().get(PluginSettings.WSI_DEID_IMPORT_PATH)),
                ('export', Setting().get(PluginSettings.WSI_DEID_EXPORT_PATH)),
                ('assetstore', assetstorePath)):
            if path is not None:
                space = psutil.disk_usage(path).free
                girder.logprint.info('Available disk space for %s: %3.1f GB' % (
                    pathkey, space / 1024**3))
