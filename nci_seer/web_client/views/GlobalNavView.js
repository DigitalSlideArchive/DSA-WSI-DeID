import $ from 'jquery';

import { wrap } from '@girder/core/utilities/PluginUtils';
import LayoutGlobalNavView from '@girder/core/views/layout/GlobalNavView';
import { getCurrentUser } from '@girder/core/auth';

import { goToNextUnprocessedItem } from '../utils';
import '../stylesheets/GlobalNavView.styl';

wrap(LayoutGlobalNavView, 'render', function (render) {
    render.call(this);

    if (getCurrentUser()) {
        this.$el.find('ul.g-global-nav').append($(
            '<li class="g-global-nav-li" title="Go to next unprocessed item">' +
            '  <a class="g-nav-extra g-nav-next-unprocessed">' +
            '    <i class="icon-right-big"></i><span>Next Item</span>' +
            '  </a>' +
            '</li>'));
        this.events['click .g-nav-next-unprocessed'] = goToNextUnprocessedItem;
        this.delegateEvents();
    }
    return this;
});
