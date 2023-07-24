import $ from 'jquery';
import { restRequest } from '@girder/core/rest';
import { wrap } from '@girder/core/utilities/PluginUtils';
import ItemView from '@girder/core/views/body/ItemView';
import View from '@girder/core/views/View';

import * as XLSX from 'xlsx/xlsx';
import CanvasDatagrid from 'canvas-datagrid';

import itemViewSpreadsheet from '../templates/ItemViewSpreadsheet.pug';
import '../stylesheets/ItemViewSpreadsheet.styl';

const Formats = {
    'application/vnd.ms-excel': {
        name: 'Spreadsheet'
    }
};
Formats['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'] = Formats['application/vnd.ms-excel'];
Formats['text/csv'] = Formats['application/vnd.ms-excel'];
Formats['text/tab-separated-values'] = Formats['application/vnd.ms-excel'];

const SpreadsheetWidget = View.extend({
    initialize: function (settings) {
        this.file = settings.file;
        this.accessLevel = settings.accessLevel;
        this.mimeType = settings.mimeType;
        restRequest({
            url: `file/${this.file.id}/download`,
            xhrFields: {
                responseType: 'arraybuffer'
            },
            error: null
        }).done((resp) => {
            this._contents = resp;
            try {
                this.workbook = XLSX.read(this._contents, { type: 'array' });
                this.workbook_json = XLSX.utils.sheet_to_json(this.workbook.Sheets[this.workbook.SheetNames[0]]);
                this.render();
            } catch (err) {
                console.warn('Failed to parse spreadsheet: ' + err);
            }
        });
    },

    render: function () {
        this.$el.html(itemViewSpreadsheet({
            formatName: Formats[this.mimeType].name
        }));
        this._cdg = CanvasDatagrid({
            parentNode: this.$el.find('.editor')[0],
            autoResizeColumns: true,
            autoResizeRows: true,
            style: {
                activeCellFont: '14px sans-serif',
                cellFont: '14px sans-serif',
                columnHeaderCellFont: '12px sans-serif',
                rowHeaderCellFont: '14px sans-serif'
            }
        });
        /* set up table headers */
        let collen = 0;
        this.workbook_json.forEach((row) => {
            if (collen < row.length) {
                collen = row.length;
            }
        });
        for (let i = this.workbook_json[0].length; i < collen; i += 1) {
            this.workbook_json[0][i] = '';
        }
        this._cdg.data = this.workbook_json;
        return this;
    }
});

wrap(ItemView, 'render', function (render) {
    this.once('g:rendered', () => {
        if (this.spreadsheetWidget) {
            this.spreadsheetWidget.remove();
        }
        if (this.fileListWidget.collection.models.length !== 1) {
            return;
        }
        const firstFile = this.fileListWidget.collection.models[0];
        const mimeType = firstFile.get('mimeType');
        if (!Formats[mimeType] || firstFile.get('size') > 100000) {
            return;
        }
        this.spreadsheetWidget = new SpreadsheetWidget({
            el: $('<div>', { class: 'g-spreadsheet-container' })
                .insertAfter(this.$('.g-item-files')),
            file: firstFile,
            parentView: this,
            mimeType: mimeType,
            accessLevel: this.accessLevel
        });
    });
    return render.call(this);
});
