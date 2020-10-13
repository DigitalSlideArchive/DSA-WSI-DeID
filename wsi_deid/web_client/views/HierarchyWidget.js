import events from '@girder/core/events';
import { getCurrentUser } from '@girder/core/auth';
import { restRequest } from '@girder/core/rest';
import router from '@girder/core/router';
import { wrap } from '@girder/core/utilities/PluginUtils';
import HierarchyWidget from '@girder/core/views/widgets/HierarchyWidget';

function performAction(action) {
    const actions = {
        ingest: { done: 'Import completed.', fail: 'Failed to import.' },
        export: { done: 'Recent export task completed.', fail: 'Failed to export recent items.  Check export file location for disk drive space or other system issues.' },
        exportall: { done: 'Export all task completed.', fail: 'Failed to export all items.  Check export file location for disk drive space or other system issues.' }
    };

    restRequest({
        method: 'PUT',
        url: `wsi_deid/action/${action}`,
        error: null
    }).done((resp) => {
        let text = actions[action].done;
        let any = false;
        if (resp.action === 'ingest') {
            if (['duplicate', 'missing', 'unlisted', 'failed', 'notexcel'].some((key) => resp[key])) {
                text = 'Import process completed with errors.';
            }
            [
                ['added', 'added'],
                ['present', 'already present'],
                ['replaced', 'replaced'],
                ['duplicate', 'with duplicate ImageID.  Check DeID Upload file'],
                ['missing', 'missing from import folder.  Check DeID Upload File and WSI image filenames'],
                ['unlisted', 'in the import folder, but not listed in a DeID Upload Excel/CSV file'],
                ['failed', 'failed to import.  Check if image files is in an accepted WSI format']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    if (key === 'unlisted' && !resp.parsed && !resp.notexcel) {
                        text += '  No DeID Upload file present.';
                    } else {
                        text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    }
                    any = true;
                }
            });
            [
                ['parsed', 'parsed'],
                ['notexcel', 'could not be read']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} DeID Upload Excel file${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    any = true;
                }
            });
            if (!any) {
                text = 'Nothing to import.  Import folder is empty.';
            }
        }
        if (resp.action === 'export' || resp.action === 'exportall') {
            [
                ['finished', 'exported'],
                ['present', 'previously exported and already exist in export folder'],
                ['different', 'with the same ImageID but different WSI file size already present in Export Folder. Remove the corresponding image(s) from the export directory and select Export again'],
                ['quarantined', 'currently quarantined.  Only files in "Approved" workflow stage are transferred to Export folder'],
                ['rejected', 'with rejected status.  Only files in "Approved" workflow stage are transferred to Export folder']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    any = true;
                }
            });
            if (!any) {
                text = 'Nothing to export.';
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
