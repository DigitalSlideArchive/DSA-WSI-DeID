import $ from 'jquery';

import { AccessType } from '@girder/core/constants';
import events from '@girder/core/events';
import { restRequest } from '@girder/core/rest';
import { wrap } from '@girder/core/utilities/PluginUtils';
import HierarchyWidget from '@girder/core/views/widgets/HierarchyWidget';

function performAction(action) {
    const actions = {
        ingest: { done: 'Started import process', fail: 'Failed to start import process.' },
        export: { done: 'Started recent export process', fail: 'Failed to start recent export process.' },
        exportall: { done: 'Started export all process', fail: 'Failed to start export all process.' }
    };

    restRequest({
        type: 'PUT',
        url: 'nciseer/action/ingest',
        error: null
    }).done((resp) => {
        $('.g-hui-loading-overlay').remove();
        events.trigger('g:alert', {
            icon: 'ok',
            text: actions[action].done,
            type: 'success',
            timeout: 4000
        });
        delete this.model.parent;
        this.model.fetch({ success: () => this.render() });
    }).fail((resp) => {
        $('.g-hui-loading-overlay').remove();
        let text = actions[action].fail;
        if (resp.responseJSON && resp.responseJSON.message) {
            text += ' ' + resp.responseJSON.message;
        }
        events.trigger('g:alert', {
            icon: 'cancel',
            text: text,
            type: 'danger',
            timeout: 5000
        });
    });
}

function addIngestControls() {
    var btns = this.$el.find('.g-hierarchy-actions-header .g-folder-header-buttons');
    btns.prepend('<button class="nciseer-import-button btn btn-info">Import</button>');
    this.events['click .nciseer-import-button'] = () => { performAction('ingest'); };
    this.delegateEvents();
}

function addExportControls() {
    var btns = this.$el.find('.g-hierarchy-actions-header .g-folder-header-buttons');
    btns.prepend(
        '<button class="nciseer-export-button btn btn-info">Export Recent</button>' +
        '<button class="nciseer-exportall-button btn btn-info">Export All</button>'
    );
    this.events['click .nciseer-export-button'] = () => { performAction('export'); };
    this.events['click .nciseer-exportall-button'] = () => { performAction('exportall'); };
    this.delegateEvents();
}

wrap(HierarchyWidget, 'render', function (render) {
    render.call(this);

    if (this.parentModel.resourceName === 'folder' &&
            this.parentModel.getAccessLevel() >= AccessType.WRITE) {
        restRequest({
            url: `nciseer/project_folder/${this.parentModel.id}`,
            error: null
        }).done((resp) => {
            if (resp) {
                if (resp === 'ingest') {
                    addIngestControls.call(this);
                } else if (resp === 'finished') {
                    addExportControls.call(this);
                }
            }
        });
    }
    return this;
});
