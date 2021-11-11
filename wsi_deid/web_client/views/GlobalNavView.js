import $ from 'jquery';

import { wrap } from '@girder/core/utilities/PluginUtils';
import LayoutGlobalNavView from '@girder/core/views/layout/GlobalNavView';
import { getCurrentUser } from '@girder/core/auth';
import { restRequest } from '@girder/core/rest';

import { goToNextUnprocessedItem, goToNextUnprocessedFolder } from '../utils';
import '../stylesheets/GlobalNavView.styl';

wrap(LayoutGlobalNavView, 'render', function (render) {
    render.call(this);

    if (getCurrentUser()) {
        restRequest({
            url: `wsi_deid/settings`,
            error: null
        }).done((settings) => {
            if (settings.show_next_item !== false) {
                this.$el.find('ul.g-global-nav').append($(
                    '<li class="g-global-nav-li" title="Go to next unprocessed item">' +
                    '  <a class="g-nav-extra g-nav-next-unprocessed">' +
                    '    <i class="icon-right-big"></i><span>Next Item</span>' +
                    '  </a>' +
                    '</li>'));
                this.events['click .g-nav-next-unprocessed'] = () => goToNextUnprocessedItem();
                this.delegateEvents();
            }
            if (settings.show_next_folder) {
                this.$el.find('ul.g-global-nav').append($(
                    '<li class="g-global-nav-li" title="Go to next unprocessed folder">' +
                    '  <a class="g-nav-extra g-nav-next-unprocessed-folder">' +
                    '    <i class="icon-right-big"></i><span>Next Folder</span>' +
                    '  </a>' +
                    '</li>'));
                this.events['click .g-nav-next-unprocessed-folder'] = () => goToNextUnprocessedFolder();
                this.delegateEvents();
            }
        });
    }
    return this;
});
