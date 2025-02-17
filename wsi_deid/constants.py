from enum import Enum

from girder.settings import SettingDefault


class PluginSettings:
    HUI_INGEST_FOLDER = 'histomicsui.ingest_folder'
    HUI_QUARANTINE_FOLDER = 'histomicsui.quarantine_folder'
    HUI_PROCESSED_FOLDER = 'histomicsui.processed_folder'
    HUI_REJECTED_FOLDER = 'histomicsui.rejected_folder'
    HUI_ORIGINAL_FOLDER = 'histomicsui.original_folder'
    HUI_FINISHED_FOLDER = 'histomicsui.finished_folder'
    HUI_REPORTS_FOLDER = 'histomicsui.reports_folder'
    WSI_DEID_IMPORT_PATH = 'wsi_deid.import_path'
    WSI_DEID_EXPORT_PATH = 'wsi_deid.export_path'
    WSI_DEID_REMOTE_PATH = 'wsi_deid.remote_path'
    WSI_DEID_REMOTE_HOST = 'wsi_deid.remote_host'
    WSI_DEID_REMOTE_USER = 'wsi_deid.remote_user'
    WSI_DEID_REMOTE_PASSWORD = 'wsi_deid.remote_password'
    WSI_DEID_REMOTE_PORT = 'wsi_deid.remote_port'
    WSI_DEID_SFTP_MODE = 'wsi_deid.sftp_mode'
    WSI_DEID_OCR_ON_IMPORT = 'wsi_deid.ocr_on_import'
    WSI_DEID_UNFILED_FOLDER = 'wsi_deid.unfiled_folder'
    WSI_DEID_SCHEMA_FOLDER = 'wsi_deid.schema_folder'
    WSI_DEID_DB_API_URL = 'wsi_deid.db_api_url'
    WSI_DEID_DB_API_KEY = 'wsi_deid.db_api_key'
    WSI_DEID_BASE = 'wsi_deid.base_'


class SftpMode(Enum):
    LOCAL_EXPORT_ONLY = 'local'
    SFTP_ONLY = 'remote'
    SFTP_AND_EXPORT = 'both'


class ExportResult(Enum):
    EXPORTED_SUCCESSFULLY = 'success'
    PREVIOUSLY_EXPORTED = 'previously exported'
    ALREADY_EXISTS_AT_DESTINATION = 'already exists'
    EXPORT_FAILED = 'failed'


# This is a list of where WSI may be stored, so excludes the reports folder
ProjectFolders = {
    'ingest': PluginSettings.HUI_INGEST_FOLDER,
    'quarantine': PluginSettings.HUI_QUARANTINE_FOLDER,
    'processed': PluginSettings.HUI_PROCESSED_FOLDER,
    'rejected': PluginSettings.HUI_REJECTED_FOLDER,
    'original': PluginSettings.HUI_ORIGINAL_FOLDER,
    'finished': PluginSettings.HUI_FINISHED_FOLDER,
    'unfiled': PluginSettings.WSI_DEID_UNFILED_FOLDER,
}


# Prefix used to indicate a partial entry only contains folder (also called
# token) information and not name (ImageID) information.
TokenOnlyPrefix = '_folder_'

SystemRedactedReason = 'System Redacted'

SettingDefault.defaults[PluginSettings.WSI_DEID_SFTP_MODE] = SftpMode.LOCAL_EXPORT_ONLY
