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
    'no_redact_control_keys': [
        r'^internal;aperio_version$',
        r'^internal;openslide;openslide\.(?!comment$)',
        r'^internal;openslide;tiff.(ResolutionUnit|XResolution|YResolution)$',
    ],
    'no_redact_control_keys_format_aperio': [
        r'^internal;openslide;aperio.AppMag',
    ],
    'no_redact_control_keys_format_hamamatsu': [],
    'no_redact_control_keys_format_philips': [],
    'hide_metadata_keys': [
        r'^internal;openslide;openslide.level\[',
    ],
    'hide_metadata_keys_format_aperio': [
        r'^internal;openslide;(openslide.comment|tiff.ImageDescription)$',
    ],
    'hide_metadata_keys_format_hamamatsu': [
        r'^internal;openslide;hamamatsu.(AHEX|MHLN)\[',
    ],
    'hide_metadata_keys_format_philips': [],
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
