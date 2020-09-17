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
        method: 'PUT',
        url: `wsi_deid/action/${action}`,
        error: null
    }).done((resp) => {
        let text = actions[action].done;
        let any = false;
        if (resp.action === 'ingest') {
            [
                ['added', 'added'],
                ['replaced', 'replaced'],
                ['missing', 'missing from import folder'],
                ['unlisted', 'missing from DeID Upload files'],
                ['present', 'already present'],
                ['failed', 'failed to import']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    any = true;
                }
            });
            [
                ['parsed', 'parsed'],
                ['notexcel', 'could not be read']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} Excel file${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    any = true;
                }
            });
            if (!any) {
                text += '  Nothing to import.';
            }
        }
        if (resp.action === 'export' || resp.action === 'exportall') {
            [
                ['finished', 'exported'],
                ['different', 'already present but different'],
                ['present', 'already exported'],
                ['quarantined', 'currently quarantined'],
                ['rejected', 'with rejected status']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    any = true;
                }
            });
            if (!any) {
                text += '  Nothing to export.';
            }
        }
        events.trigger('g:alert', {
            icon: 'ok',
            text: text,
            type: 'success',
            timeout: 0
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
            timeout: 0
        });
    });
}

function addIngestControls() {
    var btns = this.$el.find('.g-hierarchy-actions-header .g-folder-header-buttons');
    btns.prepend('<button class="wsi_deid-import-button btn btn-info">Import</button>');
    this.events['click .wsi_deid-import-button'] = () => { performAction.call(this, 'ingest'); };
    this.delegateEvents();
}

function addExportControls() {
    var btns = this.$el.find('.g-hierarchy-actions-header .g-folder-header-buttons');
    btns.prepend(
        '<button class="wsi_deid-export-button btn btn-info">Export Recent</button>' +
        '<button class="wsi_deid-exportall-button btn btn-info">Export All</button>'
    );
    this.events['click .wsi_deid-export-button'] = () => { performAction.call(this, 'export'); };
    this.events['click .wsi_deid-exportall-button'] = () => { performAction.call(this, 'exportall'); };
    this.delegateEvents();
}

wrap(HierarchyWidget, 'render', function (render) {
    render.call(this);

    if (this.parentModel.resourceName === 'folder' && getCurrentUser()) {
        restRequest({
            url: `wsi_deid/project_folder/${this.parentModel.id}`,
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
