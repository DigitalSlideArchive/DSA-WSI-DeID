import events from '@girder/core/events';
import router from '@girder/core/router';

import { registerPluginNamespace } from '@girder/core/pluginUtils';
import { exposePluginConfig } from '@girder/core/utilities/PluginUtils';

import * as DSASeer from './index';

// import modules for side effects
import './views/itemView';

import ConfigView from './views/ConfigView';

const pluginName = 'dsa_seer';
const configRoute = `plugins/${pluginName}/config`;

registerPluginNamespace('dsa_seer', DSASeer);

exposePluginConfig(pluginName, configRoute);

router.route(configRoute, 'DSASeerConfig', function () {
    events.trigger('g:navigateTo', ConfigView);
});
