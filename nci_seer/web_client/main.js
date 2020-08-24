import events from '@girder/core/events';
import router from '@girder/core/router';

import { registerPluginNamespace } from '@girder/core/pluginUtils';
import { exposePluginConfig } from '@girder/core/utilities/PluginUtils';

import * as NCISeer from './index';

// import modules for side effects
import './views/HierarchyWidget';
import './views/ItemView';

import ConfigView from './views/ConfigView';

const pluginName = 'nci_seer';
const configRoute = `plugins/${pluginName}/config`;

registerPluginNamespace('nci_seer', NCISeer);

exposePluginConfig(pluginName, configRoute);

router.route(configRoute, 'NCISeerConfig', function () {
    events.trigger('g:navigateTo', ConfigView);
});
