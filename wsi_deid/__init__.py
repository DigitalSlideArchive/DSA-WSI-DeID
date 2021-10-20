import easyocr
import girder
import psutil
from girder import plugin
from girder.constants import AssetstoreType
from girder.exceptions import GirderException, ValidationException
from girder.models.assetstore import Assetstore
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.utility import setting_utilities
from girder_jobs.models.job import Job, JobStatus
from pkg_resources import DistributionNotFound, get_distribution

from .constants import PluginSettings
from .import_export import SftpMode
from .process import get_image_text
from .rest import WSIDeIDResource

# set up asynchronously running ocr
reader = None


def get_reader():
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return reader


def start_ocr_item_job(job):
    Job().updateJob(job, log=f'Job {job.get("title")} started\n', status=JobStatus.RUNNING)
    job_args = job.get('args', None)
    if job_args is None:
        Job().updateJob(
            job,
            log='Expected a Girder item as an argument\n',
            status=JobStatus.ERROR
        )
        return
    item = job_args[0]
    ocr_reader = get_reader()
    label_text = get_image_text(item, ocr_reader)
    if len(label_text) > 0:
        message = f'Found label text {label_text} for file {item["name"]}\n',
    else:
        message = f'Could not find label tet for file {item["name"]}\n'
    Job().updateJob(job, log=message, status=JobStatus.SUCCESS)


def start_ocr_batch_job(job):
    """
    Function to be run for girder jobs of type wsi_deid.batch_ocr. Jobs using this function
    should include a list of girder item ids as an argument.

    :param job: A girder job
    """
    Job().updateJob(
        job,
        log='Starting batch job to find label text on items...\n\n',
        status=JobStatus.RUNNING
    )
    job_args = job.get('args', None)
    if job_args is None:
        Job().updateJob(
            job,
            log='Expected a list of girder items as an argument.\n',
            status=JobStatus.ERROR
        )
        return
    itemIds = job_args[0]
    ocr_reader = get_reader()
    for itemId in itemIds:
        item = Item().load(itemId, force=True)
        Job().updateJob(job, log=f'Finding label text for file: {item["name"]}...\n')
        label_text = get_image_text(item, ocr_reader)
        if len(label_text) > 0:
            message = f'Found label text {label_text} for file {item["name"]}.\n\n'
        else:
            message = f'Could not find label text for file {item["name"]}.\n\n'
        Job().updateJob(job, log=message)
    Job().updateJob(job, log='Finished batch job.\n', status=JobStatus.SUCCESS)


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
    PluginSettings.WSI_DEID_OCR_ON_IMPORT,
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
