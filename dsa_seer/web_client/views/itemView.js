import { AccessType } from '@girder/core/constants';
import { restRequest } from '@girder/core/rest';
import events from '@girder/core/events';
import { wrap } from '@girder/core/utilities/PluginUtils';
import ItemView from '@girder/core/views/body/ItemView';

import itemViewWidget from '../templates/itemView.pug';
import '../stylesheets/itemView.styl';

wrap(ItemView, 'render', function (render) {

    const getRedactList = () => {
        let redact_list = (this.model.get('meta') || {}).redact_list || {};
        redact_list.metadata = redact_list.metadata || {};
        redact_list.images = redact_list.images || {};
        return redact_list;
    };

    const flagRedaction = (event) => {
        event.stopPropagation();
        const target = $(event.currentTarget);
        const keyname = target.attr('keyname');
        const category = target.attr('category');
        const undo = target.hasClass('undo');
        const redact_list = getRedactList();
        let is_redacted = redact_list[category][keyname] !== undefined;
        if (is_redacted && undo) {
            delete redact_list[category][keyname];
        } else if (!is_redacted && !undo) {
            redact_list[category][keyname] = null;
        }
        this.model.editMetadata('redact_list', 'redact_list', redact_list);
        if (this.model.get('meta') === undefined) {
            this.model.set('meta', {});
        }
        this.model.get('meta').redact_list = redact_list;
        is_redacted = !is_redacted;
        target.toggleClass('undo');
        target.closest('td').toggleClass('redacted', is_redacted);
        target.closest('td').find('.redact-replacement').remove();
        return false;
    };

    const showRedactButton = (keyname) => {
        if (keyname.match(/^internal;openslide;openslide\.(?!comment$)/)) {
            return false;
        }
        if (keyname.match(/^internal;openslide;tiff.ResolutionUnit$/)) {
            return false;
        }
        return true;
    };

    const hideField = (keyname) => {
        const is_aperio = this.$el.find('.large_image_metadata_value[keyname="internal;openslide;aperio.Title"]').length > 0;
        if (is_aperio && keyname.match(/^internal;openslide;(openslide.comment|tiff.ImageDescription)$/)) {
            return true;
        }
        return false;
    };

    const addRedactionControls = () => {
        // default to showing the last metadata tab
        this.$el.find('.li-metadata-tabs .nav-tabs li').removeClass('active');
        this.$el.find('.li-metadata-tabs .nav-tabs li').last().addClass('active');
        this.$el.find('.li-metadata-tabs .tab-pane').removeClass('active');
        this.$el.find('.li-metadata-tabs .tab-pane').last().addClass('active');

        const redact_list = getRedactList();
        // Add redaction controls to metadata
        this.$el.find('table[keyname="internal"] .large_image_metadata_value').each((idx, elem) => {
            elem = $(elem);
            let keyname = elem.attr('keyname');
            if (!keyname || ['internal;tilesource'].indexOf(keyname) >= 0) {
                return;
            }
            let is_redacted = redact_list.metadata[keyname] !== undefined;
            elem.find('.g-hui-redact').remove();
            if (redact_list.metadata[keyname]) {
                elem.append($('<span class="redact-replacement"/>').text(redact_list.metadata[keyname]));
            }
            if (showRedactButton(keyname)) {
                elem.append($('<a class="g-hui-redact' + (is_redacted ? ' undo' : '') + '"><span>Redact</span></a>').attr({
                    keyname: keyname,
                    category: 'metadata',
                    title: 'Toggle redacting this metadata'
                }));
            }
            if (hideField(keyname)) {
                elem.closest('tr').css('display', 'none');
            }
            elem.toggleClass('redacted', is_redacted);
        });
        // Add redaction controls to images
        this.$el.find('.g-widget-metadata-container.auximage .g-widget-auximage').each((idx, elem) => {
            elem = $(elem);
            let keyname = elem.attr('auximage');
            let is_redacted = redact_list.images[keyname] !== undefined;
            elem.find('.g-hui-redact').remove();
            elem.find('.g-widget-auximage-title').append($('<a class="g-hui-redact' + (is_redacted ? ' undo' : '') + '"><span>Redact</span></a>').attr({
                keyname: keyname,
                category: 'images',
                title: 'Toggle redacting this image'
            }));
        });
        // For other folders, do we want other workflow buttons?
        this.events['click .g-hui-redact'] = flagRedaction;
        this.delegateEvents();
    };

    const workflowButton = (event) => {
        const target = $(event.currentTarget);
        const action = target.attr('action');
        const actions = {
            quarantine: {done: 'Item quarantined.', fail: 'Failed to quarantine item.'},
            unquarantine: {done: 'Item unquarantined.', fail: 'Failed to unquarantine item.'},
            processed: {done: 'Item processed.', fail: 'Failed to process item.'},
            rejected: {done: 'Item rejected.', fail: 'Failed to reject item.'},
            finished: {done: 'Item move to approved folder.', fail: 'Failed to finish item.'},
        };
        restRequest({
            type: 'PUT',
            url: 'dsaseer/item/' + this.model.id + '/action/' + action,
            error: null
        }).done((resp) => {
            console.log('done');
            events.trigger('g:alert', {
                icon: 'ok',
                text: actions[action].done,
                type: 'success',
                timeout: 4000
            });
            this.render();
        }).fail((resp) => {
            console.log('fail');
            events.trigger('g:alert', {
                icon: 'cancel',
                text: actions[action].fail,
                type: 'danger',
                timeout: 4000
            });
        });
    };

    this.once('g:largeImageItemViewRendered', function () {
        if (this.model.get('largeImage') && this.model.get('largeImage').fileId && this.accessLevel >= AccessType.WRITE) {
            restRequest({
                url: `dsaseer/project_folder/${this.model.get('folderId')}`,
                error: null
            }).done((resp) => {
                if (resp === 'ingest' || resp === 'quarantine') {
                    addRedactionControls();
                }
                if (resp) {
                    this.$el.append(itemViewWidget({
                        project_folder: resp
                    }));
                    this.events['click .g-workflow-button'] = workflowButton;
                    this.delegateEvents();
                }
            });
        }
    });
    render.call(this);
});
