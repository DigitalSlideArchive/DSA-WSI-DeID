import importlib.metadata
import json
import os
import re
import string

import girder
import PIL.Image
import psutil
from girder import events, plugin
from girder.constants import AssetstoreType
from girder.exceptions import GirderException, ValidationException
from girder.models.assetstore import Assetstore
from girder.models.file import File
from girder.models.folder import Folder
from girder.models.setting import Setting
from girder.utility import setting_utilities

from . import assetstore_import
from .config import configSchemas
from .constants import PluginSettings
from .import_export import SftpMode
from .rest import WSIDeIDResource, addSystemEndpoints

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    # package is not installed
    __version__ = '0.0.0'


@setting_utilities.validator({
    PluginSettings.HUI_INGEST_FOLDER,
    PluginSettings.HUI_QUARANTINE_FOLDER,
    PluginSettings.HUI_PROCESSED_FOLDER,
    PluginSettings.HUI_REJECTED_FOLDER,
    PluginSettings.HUI_ORIGINAL_FOLDER,
    PluginSettings.HUI_FINISHED_FOLDER,
    PluginSettings.HUI_REPORTS_FOLDER,
    PluginSettings.WSI_DEID_UNFILED_FOLDER,
    PluginSettings.WSI_DEID_SCHEMA_FOLDER,
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
    PluginSettings.WSI_DEID_DB_API_URL,
    PluginSettings.WSI_DEID_DB_API_KEY,
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
            msg = 'Remote SFTP Port must be an integer value'
            raise ValidationException(msg)


@setting_utilities.validator(PluginSettings.WSI_DEID_SFTP_MODE)
def validateSettingSftpMode(doc):
    if doc['value'] not in [mode.value for mode in SftpMode]:
        msg = 'SFTP Mode must be one of "local", "remote", or "both"'
        raise ValidationException(msg, 'value')


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'add_title_to_label',
    PluginSettings.WSI_DEID_BASE + 'always_redact_label',
    PluginSettings.WSI_DEID_BASE + 'redact_macro_square',
    PluginSettings.WSI_DEID_BASE + 'show_import_button',
    PluginSettings.WSI_DEID_BASE + 'show_export_button',
    PluginSettings.WSI_DEID_BASE + 'show_next_item',
    PluginSettings.WSI_DEID_BASE + 'show_next_folder',
    PluginSettings.WSI_DEID_BASE + 'require_redact_category',
    PluginSettings.WSI_DEID_BASE + 'require_reject_reason',
    PluginSettings.WSI_DEID_BASE + 'edit_metadata',
    PluginSettings.WSI_DEID_BASE + 'show_metadata_in_lists',
    PluginSettings.WSI_DEID_BASE + 'reimport_if_moved',
    PluginSettings.WSI_DEID_BASE + 'validate_image_id_field',
})
def validateBoolean(doc):
    if doc.get('value', None) is not None:
        doc['value'] = str(doc['value']).lower() in {'true', 'on', 'yes'}


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'redact_macro_long_axis_percent',
    PluginSettings.WSI_DEID_BASE + 'redact_macro_short_axis_percent',
})
def validateDecimalPercent(doc):
    if doc.get('value', None) is not None:
        doc['value'] = float(doc['value'])
        if doc['value'] < 0 or doc['value'] > 100:
            msg = 'Percent must be between 0 and 100'
            raise ValidationException(msg)


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'folder_name_field',
})
def validateFolderNameField(doc):
    if doc.get('value', None):
        doc['value'] = str(doc['value']).strip()
    if not doc['value']:
        doc['value'] = None


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'image_name_field',
})
def validateImageNameField(doc):
    if doc.get('value', None) is not None:
        doc['value'] = str(doc['value']).strip()


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'new_token_pattern',
})
def validateNewTokenPattern(doc):
    if doc.get('value', None) is not None:
        doc['value'] = str(doc['value']).strip()
        if doc['value'] and '@' not in doc['value'] and '#' not in doc['value']:
            msg = 'The token pattern must contain at least one @ or # character for templating'
            raise ValidationException(msg)
    if not doc['value']:
        doc['value'] = None


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'name_template',
    PluginSettings.WSI_DEID_BASE + 'folder_template',
})
def validateStringTemplate(doc):
    if doc.get('value', None) is not None:
        doc['value'] = re.sub(
            r'\{tokenid\}', '{tokenId}', str(doc['value']).strip(),
            flags=re.IGNORECASE)
        try:
            names = [fn for _, fn, _, _ in string.Formatter().parse(doc['value']) if fn is not None]
        except Exception:
            names = []
        if not len(names):
            msg = 'The template string must contain at least one reference in brases'
            raise ValidationException(msg)

    if not doc['value']:
        doc['value'] = None


@setting_utilities.validator({
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys',
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys_format_aperio',
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys_format_dicom',
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys_format_hamamatsu',
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys_format_isyntax',
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys_format_ometiff',
    PluginSettings.WSI_DEID_BASE + 'hide_metadata_keys_format_philips',
    PluginSettings.WSI_DEID_BASE + 'import_text_association_columns',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys_format_aperio',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys_format_dicom',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys_format_hamamatsu',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys_format_isyntax',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys_format_ometiff',
    PluginSettings.WSI_DEID_BASE + 'no_redact_control_keys_format_philips',
    PluginSettings.WSI_DEID_BASE + 'ocr_parse_values',
    PluginSettings.WSI_DEID_BASE + 'phi_pii_types',
    PluginSettings.WSI_DEID_BASE + 'reject_reasons',
    PluginSettings.WSI_DEID_BASE + 'upload_metadata_add_to_images',
    PluginSettings.WSI_DEID_BASE + 'upload_metadata_for_export_report',
})
def validateJsonSchema(doc):
    import jsonschema

    if doc.get('value', None):
        schemakey = doc['key']
        if schemakey.startswith(PluginSettings.WSI_DEID_BASE):
            schemakey = schemakey[len(PluginSettings.WSI_DEID_BASE):]
        if schemakey not in configSchemas and '_key' in schemakey:
            schemakey = schemakey.split('_keys')[0] + '_keys'
        if isinstance(doc['value'], str):
            doc['value'] = json.loads(doc['value'])
        jsonschema.validate(instance=doc['value'], schema=configSchemas[schemakey])
        if '_keys' in schemakey:
            for k, v in doc['value'].items():
                try:
                    re.compile(k)
                    re.compile(v)
                except Exception:
                    msg = f'All keys and values if {doc["key"]} must be regular expressions'
                    raise ValidationException(msg)
    else:
        doc.get('value', None)


class GirderPlugin(plugin.GirderPlugin):
    DISPLAY_NAME = 'WSI DeID'
    CLIENT_SOURCE_PATH = 'web_client'

    def load(self, info):
        plugin.getPlugin('histomicsui').load(info)
        info['apiRoot'].wsi_deid = WSIDeIDResource(info['apiRoot'])
        addSystemEndpoints(info['apiRoot'])
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
            if path is not None and os.path.exists(path):
                space = psutil.disk_usage(path).free
                girder.logprint.info('Available disk space for %s: %3.1f GB' % (
                    pathkey, space / 1024**3))
        idx1 = ([('path', 1)], {})
        if idx1 not in File()._indices:
            File().ensureIndex(idx1)
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

        events.bind('rest.post.assetstore/:id/import.after', 'wsi_deid',
                    assetstore_import.assetstoreImportEvent)

        try:
            import large_image_source_dicom
            import large_image_source_openslide
            from large_image.constants import SourcePriority

            large_image_source_dicom.DICOMFileTileSource.extensions['dcm'] = SourcePriority.HIGH  # noqa
            large_image_source_dicom.DICOMFileTileSource.mimeTypes['application/dicom'] = SourcePriority.HIGH  # noqa
            large_image_source_openslide.OpenslideFileTileSource.extensions['dcm'] = SourcePriority.PREFERRED  # noqa
            large_image_source_openslide.OpenslideFileTileSource.mimeTypes['application/dicom'] = SourcePriority.PREFERRED  # noqa
            girder.logprint.info('Setting openslide as preferred dicom reader')
        except Exception:
            pass
