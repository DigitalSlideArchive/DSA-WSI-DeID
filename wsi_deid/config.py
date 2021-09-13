import girder.utility.config

CONFIG_SECTION = 'wsi_deid'

defaultConfig = {
    'redact_macro_square': False,
    'always_redact_label': False,
    'require_redact_category': True,
    'add_title_to_label': True,
    'show_import_button': True,
    'show_export_button': True,
    'show_next_item': True,
    'disable_redaction_for_metadata': [
        r'^internal;aperio_version$',
        r'^internal;openslide;openslide\.(?!comment$)',
        r'^internal;openslide;tiff.(ResolutionUnit|XResolution|YResolution)$',
    ],
    'disable_redaction_for_metadata_format_aperio': [],
    'disable_redaction_for_metadata_format_hamamatsu': [],
    'disable_redaction_for_metadata_format_philips': [],
    'hide_metadata': [
        r'^internal;openslide;openslide.level\[',
        r'^internal;openslide;hamamatsu.(AHEX|MHLN)\[',
        r'^internal;openslide;(openslide.comment|tiff.ImageDescription)$',
    ],
    'hide_metadata_format_aperio': [],
    'hide_metadata_format_hamamatsu': [],
    'hide_metadata_format_philips': [],
}


def getConfig(key=None, fallback=None):
    configDict = girder.utility.config.getConfig().get(CONFIG_SECTION) or {}
    if key is None:
        config = defaultConfig.copy()
        config.update(configDict)
        return config
    if key in configDict:
        return configDict[key]
    if key in defaultConfig:
        return defaultConfig[key]
    return fallback
