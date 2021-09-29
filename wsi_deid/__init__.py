import easyocr
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
from .import_export import SftpMode
from .rest import WSIDeIDResource
from .process import get_image_text

# set up asynchronously running ocr
reader = None

def handle_ocr_item(event):
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'], gpu=False)
    item = event.info['item']
    ocr_results = get_image_text(item, reader)
    # TODO fix File already exists
    print(f'\n\n\nRESULTS: {ocr_results}')

events.bind('wsi_deid.ocr_item', 'ocr_handler', handle_ocr_item)

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
    if not doc['value'] in [mode.value for mode in SftpMode]:
        raise ValidationException('SFTP Mode must be one of "local", "remote", or "both"', 'value')


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
