import events from '@girder/core/events';
import router from '@girder/core/router';

import { registerPluginNamespace } from '@girder/core/pluginUtils';
import { exposePluginConfig } from '@girder/core/utilities/PluginUtils';

import * as WSIDeID from './index';

// import modules for side effects
import './views/GlobalNavView';
import './views/HierarchyWidget';
import './views/ItemList';
import './views/ItemView';
import './views/ItemViewSpreadsheet';

import ConfigView from './views/ConfigView';

const pluginName = 'wsi_deid';
const configRoute = `plugins/${pluginName}/config`;

registerPluginNamespace('wsi_deid', WSIDeID);

exposePluginConfig(pluginName, configRoute);

router.route(configRoute, 'WSIDeIDConfig', function () {
    events.trigger('g:navigateTo', ConfigView);
});
