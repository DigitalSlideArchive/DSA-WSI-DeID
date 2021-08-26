import girder.utility.config

CONFIG_SECTION = 'wsi_deid'

defaultConfig = {
    'redact_macro_square': True,
    'always_redact_label': True,
    'require_redact_category': True,
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
