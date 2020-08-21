import $ from 'jquery';

import { AccessType } from '@girder/core/constants';
import { restRequest } from '@girder/core/rest';
import events from '@girder/core/events';
import { wrap } from '@girder/core/utilities/PluginUtils';
import ItemView from '@girder/core/views/body/ItemView';

import itemViewWidget from '../templates/itemView.pug';
import '../stylesheets/itemView.styl';

wrap(ItemView, 'render', function (render) {
    const getRedactList = () => {
        let redactList = (this.model.get('meta') || {}).redactList || {};
        redactList.metadata = redactList.metadata || {};
        redactList.images = redactList.images || {};
        // TODO: If appropriate metadata is populated with replacement title,
        // date, etc., populate the redaction list per file format
        // appropriately.  Alternately, we may want an endpoint which is
        // "default redaction list" so that all the code is in Python.
        return redactList;
    };

    const flagRedaction = (event) => {
        event.stopPropagation();
        const target = $(event.currentTarget);
        const keyname = target.attr('keyname');
        const category = target.attr('category');
        const undo = target.hasClass('undo');
        const redactList = getRedactList();
        let isRedacted = redactList[category][keyname] !== undefined;
        if (isRedacted && undo) {
            delete redactList[category][keyname];
        } else if (!isRedacted && !undo) {
            redactList[category][keyname] = null;
        }
        this.model.editMetadata('redactList', 'redactList', redactList);
        if (this.model.get('meta') === undefined) {
            this.model.set('meta', {});
        }
        this.model.get('meta').redactList = redactList;
        isRedacted = !isRedacted;
        target.toggleClass('undo');
        target.closest('td').toggleClass('redacted', isRedacted);
        target.closest('td').find('.redact-replacement').remove();
        return false;
    };

    const showRedactButton = (keyname) => {
        if (keyname.match(/^internal;openslide;openslide\.(?!comment$)/)) {
            return false;
        }
        if (keyname.match(/^internal;openslide;tiff.(ResolutionUnit|XResolution|YResolution)$/)) {
            return false;
        }
        return true;
    };

    const hideField = (keyname) => {
        const isAperio = this.$el.find('.large_image_metadata_value[keyname="internal;openslide;aperio.Title"]').length > 0;
        if (isAperio && keyname.match(/^internal;openslide;(openslide.comment|tiff.ImageDescription)$/)) {
            return true;
        }
        return false;
    };

    const addRedactionControls = (showControls) => {
        /* if showControls is false, the tabs are still adjusted and some
         * fields may be hidden, but the actual redaction controls aren't
         * shown. */
        // default to showing the last metadata tab
        this.$el.find('.li-metadata-tabs .nav-tabs li').removeClass('active');
        this.$el.find('.li-metadata-tabs .nav-tabs li').last().addClass('active');
        this.$el.find('.li-metadata-tabs .tab-pane').removeClass('active');
        this.$el.find('.li-metadata-tabs .tab-pane').last().addClass('active');

        const redactList = getRedactList();
        // Add redaction controls to metadata
        this.$el.find('table[keyname="internal"] .large_image_metadata_value').each((idx, elem) => {
            elem = $(elem);
            let keyname = elem.attr('keyname');
            if (!keyname || ['internal;tilesource'].indexOf(keyname) >= 0) {
                return;
            }
            elem.find('.g-hui-redact').remove();
            if (showControls) {
                let isRedacted = redactList.metadata[keyname] !== undefined;
                if (redactList.metadata[keyname]) {
                    elem.append($('<span class="redact-replacement"/>').text(redactList.metadata[keyname]));
                }
                if (showRedactButton(keyname)) {
                    elem.append($('<a class="g-hui-redact' + (isRedacted ? ' undo' : '') + '"><span>Redact</span></a>').attr({
                        keyname: keyname,
                        category: 'metadata',
                        title: 'Toggle redacting this metadata'
                    }));
                }
                elem.toggleClass('redacted', isRedacted);
            }
            if (hideField(keyname)) {
                elem.closest('tr').css('display', 'none');
            }
        });
        // Add redaction controls to images
        if (showControls) {
            this.$el.find('.g-widget-metadata-container.auximage .g-widget-auximage').each((idx, elem) => {
                elem = $(elem);
                let keyname = elem.attr('auximage');
                let isRedacted = redactList.images[keyname] !== undefined;
                elem.find('.g-hui-redact').remove();
                elem.find('.g-widget-auximage-title').append($('<a class="g-hui-redact' + (isRedacted ? ' undo' : '') + '"><span>Redact</span></a>').attr({
                    keyname: keyname,
                    category: 'images',
                    title: 'Toggle redacting this image'
                }));
            });
            this.events['click .g-hui-redact'] = flagRedaction;
            this.delegateEvents();
        }
    };

    const workflowButton = (event) => {
        const target = $(event.currentTarget);
        const action = target.attr('action');
        const actions = {
            quarantine: { done: 'Item quarantined.', fail: 'Failed to quarantine item.' },
            unquarantine: { done: 'Item unquarantined.', fail: 'Failed to unquarantine item.' },
            process: { done: 'Item processed.', fail: 'Failed to process item.' },
            reject: { done: 'Item rejected.', fail: 'Failed to reject item.' },
            finish: { done: 'Item move to approved folder.', fail: 'Failed to finish item.' }
        };
        $('body').append(
            '<div class="g-hui-loading-overlay"><div>' +
            '<i class="icon-spin4 animate-spin"></i>' +
            '</div></div>');
        restRequest({
            type: 'PUT',
            url: 'nciseer/item/' + this.model.id + '/action/' + action,
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
    };

    this.once('g:largeImageItemViewRendered', function () {
        if (this.model.get('largeImage') && this.model.get('largeImage').fileId && this.accessLevel >= AccessType.WRITE) {
            restRequest({
                url: `nciseer/project_folder/${this.model.get('folderId')}`,
                error: null
            }).done((resp) => {
                if (resp) {
                    addRedactionControls(resp === 'ingest' || resp === 'quarantine');
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
