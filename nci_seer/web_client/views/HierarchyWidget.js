import events from '@girder/core/events';
import { getCurrentUser } from '@girder/core/auth';
import { restRequest } from '@girder/core/rest';
import router from '@girder/core/router';
import { wrap } from '@girder/core/utilities/PluginUtils';
import HierarchyWidget from '@girder/core/views/widgets/HierarchyWidget';

function performAction(action) {
    const actions = {
        ingest: { done: 'Import complete.', fail: 'Failed to import.' },
        export: { done: 'Recent export complete.', fail: 'Failed to export recent items.' },
        exportall: { done: 'Export all complete.', fail: 'Failed to export all item.' }
    };

    restRequest({
        type: 'PUT',
        url: `nciseer/action/${action}`,
        error: null
    }).done((resp) => {
        let text = actions[action].done;
        if (resp.action === 'ingest') {
            [
                ['added', 'added'],
                ['replaced', 'replaced'],
                ['missing', 'missing from import folder'],
                ['unlisted', 'missing from manifests'],
                ['present', 'already present']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                }
            });
        }
        if (resp.action === 'export' || resp.action === 'exportall') {
            [
                ['export', 'exported'],
                ['different', 'already present but different'],
                ['present', 'already exported']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                }
            });
        }
        events.trigger('g:alert', {
            icon: 'ok',
            text: text,
            type: 'success',
            timeout: 10000
        });
        if (resp.action === 'ingest' && this.parentModel.get('_modelType') === 'folder') {
            router.navigate('folder/' + this.parentModel.id + '?_=' + Date.now(), { trigger: true });
        }
    }).fail((resp) => {
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
    this.events['click .nciseer-import-button'] = () => { performAction.call(this, 'ingest'); };
    this.delegateEvents();
}

function addExportControls() {
    var btns = this.$el.find('.g-hierarchy-actions-header .g-folder-header-buttons');
    btns.prepend(
        '<button class="nciseer-export-button btn btn-info">Export Recent</button>' +
        '<button class="nciseer-exportall-button btn btn-info">Export All</button>'
    );
    this.events['click .nciseer-export-button'] = () => { performAction.call(this, 'export'); };
    this.events['click .nciseer-exportall-button'] = () => { performAction.call(this, 'exportall'); };
    this.delegateEvents();
}

wrap(HierarchyWidget, 'render', function (render) {
    render.call(this);

    if (this.parentModel.resourceName === 'folder' && getCurrentUser()) {
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
