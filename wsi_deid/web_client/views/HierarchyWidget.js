import $ from 'jquery';
import events from '@girder/core/events';
import { getCurrentUser } from '@girder/core/auth';
import { restRequest } from '@girder/core/rest';
import router from '@girder/core/router';
import { wrap } from '@girder/core/utilities/PluginUtils';
import HierarchyWidget from '@girder/core/views/widgets/HierarchyWidget';
import { formatCount } from '@girder/core/misc';

import '../stylesheets/HierarchyWidget.styl';

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
            if (['duplicate', 'missing', 'unlisted', 'failed', 'notexcel', 'badformat', 'badentry'].some((key) => resp[key])) {
                text = 'Import process completed with errors.';
            }
            [
                ['added', 'added'],
                ['present', 'already present'],
                ['replaced', 'replaced'],
                ['duplicate', 'with duplicate ImageID.  Check DeID Upload file'],
                ['missing', 'missing from import folder.  Check DeID Upload File and WSI image filenames'],
                ['badentry', 'with invalid data in a DeID Upload File'],
                ['unlisted', 'in the import folder, but not listed in a DeID Upload Excel/CSV file'],
                ['failed', 'failed to import.  Check if image file(s) are in an accepted WSI format']
            ].forEach(([key, desc]) => {
                if (resp[key]) {
                    if (key === 'unlisted' && !resp.parsed && !resp.notexcel && !resp.badformat) {
                        text += '  No DeID Upload file present.';
                    } else {
                        text += `  ${resp[key]} image${resp[key] > 1 ? 's' : ''} ${desc}.`;
                    }
                    any = true;
                }
            });
            [
                ['parsed', 'parsed'],
                ['notexcel', 'could not be read'],
                ['badformat', 'incorrectly formatted']
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
                ['present', 'previously exported and already exist(s) in export folder'],
                ['different', 'with the same ImageID but different WSI file size already present in export folder. Remove the corresponding image(s) from the export directory and select Export again'],
                ['quarantined', 'currently quarantined.  Only files in "Approved" workflow stage are transferred to export folder'],
                ['rejected', 'with rejected status.  Only files in "Approved" workflow stage are transferred to export folder']
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
        if (resp.fileId) {
            events.once('g:alert', () => {
                $('#g-alerts-container:last div.alert:last').append($('<span> </span>')).append($('<a/>').text('See the Excel report for more details.').attr('href', `/api/v1/file/${resp.fileId}/download`));
            }, this);
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
        /*
        if (resp.responseJSON && resp.responseJSON.message) {
            text += ' ' + resp.responseJSON.message;
        }
        */
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

wrap(HierarchyWidget, 'fetchAndShowChildCount', function (fetchAndShowChildCount) {
    let showSubtreeCounts = () => {
        const folders = this.parentModel.get('nFolders') || 0;
        const items = this.parentModel.get('nItems') || 0;
        const subfolders = Math.max(folders, this.parentModel.get('nSubtreeCount').folders - 1 || 0);
        const subitems = Math.max(items, this.parentModel.get('nSubtreeCount').items || 0);
        let folderCount = formatCount(folders) + (subfolders > folders ? (' (' + formatCount(subfolders) + ')') : '');
        let itemCount = formatCount(items) + (subitems > items ? (' (' + formatCount(subitems) + ')') : '');
        let folderTooltip = `${folders} folder${folders === 1 ? '' : 's'}`;
        if (folders < subfolders) {
            folderTooltip += ` (current folder), ${subfolders} total folder${subfolders === 1 ? '' : 's'} (including subfolders)`;
        } else if (folders) {
            folderTooltip += ' (all in current folder)';
        }
        let itemTooltip = `${items} file${items === 1 ? '' : 's'}`;
        if (items < subitems) {
            itemTooltip += ` (current folder), ${subitems} total file${subitems === 1 ? '' : 's'} (including in subfolders)`;
        } else if (items) {
            itemTooltip += ' (all in current folder)';
        }
        if (!this.$('.g-item-count').length) {
            this.$('.g-subfolder-count-container').after($('<div class="g-item-count-container"><i class="icon-doc-text-inv"></i><div class="g-item-count"></div></div>'));
        }
        this.$('.g-subfolder-count').text(folderCount);
        this.$('.g-item-count').text(itemCount);
        this.$('.g-subfolder-count-container').attr('title', folderTooltip);
        this.$('.g-item-count-container').attr('title', itemTooltip);
        this.$('.g-subfolder-count-container').toggleClass('subtree-info', subfolders > folders);
        this.$('.g-item-count-container').toggleClass('subtree-info', subitems > items);
    };

    let reshowSubtreeCounts = () => {
        restRequest({
            url: `wsi_deid/resource/${this.parentModel.id}/subtreeCount`,
            data: { type: this.parentModel.get('_modelType') }
        }).done((data) => {
            this.parentModel.set('nSubtreeCount', data);
            showSubtreeCounts();
        });
    };

    fetchAndShowChildCount.call(this);
    if (this.parentModel.has('nSubtreeCount')) {
        showSubtreeCounts();
    } else {
        this.parentModel.set('nSubtreeCount', {}); // prevents fetching details twice
        reshowSubtreeCounts();
    }
    this.parentModel.off('change:nItems', reshowSubtreeCounts, this)
        .on('change:nItems', reshowSubtreeCounts, this)
        .off('change:nFolders', reshowSubtreeCounts, this)
        .on('change:nFolders', reshowSubtreeCounts, this);
    return this;
});
