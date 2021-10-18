import $ from 'jquery';
import _ from 'underscore';
import View from '@girder/core/views/View';

import PluginConfigBreadcrumbWidget from '@girder/core/views/widgets/PluginConfigBreadcrumbWidget';
import BrowserWidget from '@girder/core/views/widgets/BrowserWidget';
import { restRequest } from '@girder/core/rest';
import events from '@girder/core/events';
import router from '@girder/core/router';
import FolderModel from '@girder/core/models/FolderModel';

import ConfigViewTemplate from '../templates/ConfigView.pug';
import '../stylesheets/ConfigView.styl';

/**
 * Show the plugin's settings.
 */
var ConfigView = View.extend({
    events: {
        'click #g-hui-save': function (event) {
            this.$('#g-hui-error-message').text('');
            var settings = _.map(Object.keys(this.settingsKeys), (key) => {
                const element = this.$('#g-' + key.replace('histomicsui', 'hui').replace(/[_.]/g, '-'));
                var result = {
                    key,
                    value: element.val() || null
                };
                if (key.match(/_folder$/)) {
                    result.value = result.value ? result.value.split(' ')[0] : '';
                }
                return result;
            });
            this._saveSettings(settings);
        },
        'click #g-hui-cancel': function (event) {
            router.navigate('plugins', { trigger: true });
        },
        'click .g-open-browser': '_openBrowser'
    },
    initialize: function () {
        this.breadcrumb = new PluginConfigBreadcrumbWidget({
            pluginName: 'WSI DeID',
            parentView: this
        });

        this.settingsKeys = {
            'histomicsui.ingest_folder': { name: 'AvailableToProcess', id: 'g-hui-ingest-folder' },
            'histomicsui.quarantine_folder': { name: 'Quarantined', id: 'g-hui-quarantine-folder' },
            'histomicsui.processed_folder': { name: 'Redacted', id: 'g-hui-processed-folder' },
            'histomicsui.rejected_folder': { name: 'Rejected', id: 'g-hui-rejected-folder' },
            'histomicsui.original_folder': { name: 'Original', id: 'g-hui-original-folder' },
            'histomicsui.finished_folder': { name: 'Approved', id: 'g-hui-finished-folder' },
            'histomicsui.reports_folder': { name: 'Reports', id: 'g-hui-reports-folder' },
            'wsi_deid.import_path': { name: 'Internal Import Path', id: 'g-wsi-deid-import-path' },
            'wsi_deid.export_path': { name: 'Internal Export Path', id: 'g-wsi-deid-export-path' },
            'wsi_deid.remote_path': { name: 'Remote Export Path', id: 'g-wsi-deid-remote-path' },
            'wsi_deid.remote_host': { name: 'Remote SFTP Host', id: 'g-wsi-deid-remote_host' },
            'wsi_deid.remote_port': { name: 'Remote SFTP Port', id: 'g-wsi-deid-remote-port' },
            'wsi_deid.remote_user': { name: 'Remote SFTP User', id: 'g-wsi-deid-remote-user' },
            'wsi_deid.remote_password': { name: 'Remote SFTP Password', id: 'g-wsi-deid-remote-password' },
            'wsi_deid.sftp_mode': { name: 'SFTP Mode', id: 'g-wsi-deid-sftp-mode' },
            'wsi_deid.ocr_on_import': { name: 'Find Label Text on Import', id: 'g-wsi-deid-ocr-on-import' }
        };
        this._browserWidgetView = {};
        $.when(
            restRequest({
                method: 'GET',
                url: 'system/setting',
                data: {
                    list: JSON.stringify(Object.keys(this.settingsKeys)),
                    default: 'none'
                }
            }).done((resp) => {
                this.settings = resp;
            }),
            restRequest({
                method: 'GET',
                url: 'system/setting',
                data: {
                    list: JSON.stringify(Object.keys(this.settingsKeys)),
                    default: 'default'
                }
            }).done((resp) => {
                this.defaults = resp;
            })
        ).done(() => {
            this.render();

            for (const [key, value] of Object.entries(this.settingsKeys)) {
                if (key.match(/_folder$/)) {
                    if (this.settings[key]) {
                        let folder = new FolderModel();
                        folder.set({ _id: this.settings[key] }).once('g:fetched', () => {
                            this._createBrowserWidget(key, value, folder);
                        }).fetch();
                    } else {
                        this._createBrowserWidget(key, value);
                    }
                }
            }
        });
    },

    _createBrowserWidget: function (key, value, folder) {
        const id = '#' + value.id;
        this._browserWidgetView[value.id] = new BrowserWidget({
            parentView: this,
            titleText: value.name + ' Destination',
            helpText: 'Browse to a location to select it as the destination.',
            submitText: 'Select Destination',
            defaultSelectedResource: folder,
            validate: function (model) {
                let isValid = $.Deferred();
                if (!model || model.get('_modelType') !== 'folder') {
                    isValid.reject('Please select a folder.');
                } else {
                    isValid.resolve();
                }
                return isValid.promise();
            }
        });
        this.listenTo(this._browserWidgetView[value.id], 'g:saved', function (val) {
            this.$(id).val(val.id);
            restRequest({
                url: `resource/${val.id}/path`,
                method: 'GET',
                data: { type: val.get('_modelType') }
            }).done((result) => {
                // Only add the resource path if the value wasn't altered
                if (this.$(id).val() === val.id) {
                    this.$(id).val(`${val.id} (${result})`);
                }
            });
        });
    },

    render: function () {
        this.$el.html(ConfigViewTemplate({
            settings: this.settings,
            defaults: this.defaults
        }));
        this.breadcrumb.setElement(this.$('.g-config-breadcrumb-container')).render();
        return this;
    },

    _saveSettings: function (settings) {
        return restRequest({
            method: 'PUT',
            url: 'system/setting',
            data: {
                list: JSON.stringify(settings)
            },
            error: null
        }).done(() => {
            events.trigger('g:alert', {
                icon: 'ok',
                text: 'Settings saved.',
                type: 'success',
                timeout: 4000
            });
        }).fail((resp) => {
            this.$('#g-hui-error-message').text(
                resp.responseJSON.message
            );
        });
    },

    _openBrowser: function (event) {
        let id = $(event.currentTarget).closest('.input-group').find('input').attr('id');
        this._browserWidgetView[id].setElement($('#g-dialog-container')).render();
    }
});

export default ConfigView;
