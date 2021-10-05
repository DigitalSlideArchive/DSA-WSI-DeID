import girder.utility.config

CONFIG_SECTION = 'wsi_deid'
NUMERIC_VALUES = (
    r'^\s*[+-]?(\d+([.]\d*)?([eE][+-]?\d+)?|[.]\d+([eE][+-]?\d+)?)(\s*,\s*[+-]?'
    r'(\d+([.]\d*)?([eE][+-]?\d+)?|[.]\d+([eE][+-]?\d+)?))*\s*$'
)

defaultConfig = {
    'redact_macro_square': False,
    'always_redact_label': False,
    'require_redact_category': True,
    'edit_meatadata': False,
    'add_title_to_label': True,
    'show_import_button': True,
    'show_export_button': True,
    'show_next_item': True,
    'no_redact_control_keys': {
        r'^internal;aperio_version$': '',
        r'^internal;openslide;openslide\.(?!comment$)': '',
        r'^internal;openslide;tiff\.(XResolution|YResolution)$': NUMERIC_VALUES,
        r'^internal;openslide;tiff\.ResolutionUnit$': '',
    },
    'no_redact_control_keys_format_aperio': {
        r'^internal;openslide;aperio\.(AppMag|MPP|Exposure (Time|Scale))$': NUMERIC_VALUES,
    },
    'no_redact_control_keys_format_hamamatsu': {
        r'^internal;openslide;hamamatsu\.SourceLens$': NUMERIC_VALUES,
    },
    'no_redact_control_keys_format_philips': {},
    'hide_metadata_keys': {
        r'^internal;openslide;openslide\.level\[': NUMERIC_VALUES,
    },
    'hide_metadata_keys_format_aperio': {
        r'^internal;openslide;(openslide\.comment|tiff\.ImageDescription)$': '',
        (
            r'^internal;openslide;aperio\.(Original(Height|Width)|Left|Top|Right|Bottom'
            r'|LineArea(X|Y)Offset|LineCameraSkew|Focus Offset|StripeWidth|DisplayColor)'
        ): NUMERIC_VALUES,
    },
    'hide_metadata_keys_format_hamamatsu': {
        (
            r'^internal;openslide;hamamatsu\.((AHEX|MHLN|YRNP|zCoarse|zFine)\['
            r'|(X|Y)OffsetFromSlideCentre|ccd.(width|height)|(focalplane|slant)\.(left|right)'
            r'(top|bottom)|stage.center)'
        ): NUMERIC_VALUES,
    },
    'hide_metadata_keys_format_philips': {},
    'sftp_mode': 0
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
