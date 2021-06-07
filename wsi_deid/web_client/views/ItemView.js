import $ from 'jquery';
import _ from 'underscore';

// import { AccessType } from '@girder/core/constants';
import events from '@girder/core/events';
import { getCurrentUser } from '@girder/core/auth';
import ItemView from '@girder/core/views/body/ItemView';
import { restRequest } from '@girder/core/rest';
import { wrap } from '@girder/core/utilities/PluginUtils';

import ItemViewWidget from '@girder/large_image/views/itemViewWidget';

import ItemViewTemplate from '../templates/ItemView.pug';
import '../stylesheets/ItemView.styl';
import { goToNextUnprocessedItem } from '../utils';

let PHIPIITypes = [{
    category: 'Personal_Info',
    text: 'Personal Information',
    types: [
        { key: 'Patient_Name', text: 'Patient Name' },
        { key: 'Patient_DOB', text: 'Date of Birth ' },
        { key: 'SSN', text: 'Social Security Number' },
        { key: 'Other_Personal', text: 'Other Personal' }
    ]
}, {
    category: 'Demographics',
    key: 'Demographics',
    text: 'Demographics'
}, {
    category: 'Facility_Physician',
    key: 'Facility_Physician',
    text: 'Facility/Physician Information'
}, {
    category: 'Other_PHIPII',
    key: 'Other_PHIPII',
    text: 'Other PHI/PII'
}];

wrap(ItemView, 'render', function (render) {
    this.getRedactList = () => {
        let redactList = (this.model.get('meta') || {}).redactList || {};
        redactList.metadata = redactList.metadata || {};
        redactList.images = redactList.images || {};
        ['images', 'metadata'].forEach((main) => {
            for (let key in redactList[main]) {
                if (!_.isObject(redactList[main][key]) || redactList[main][key] === null) {
                    redactList[main][key] = { value: redactList[main][key] };
                }
            }
        });
        return redactList;
    };

    const flagRedaction = (event) => {
        event.stopPropagation();
        const target = $(event.currentTarget);
        const keyname = target.attr('keyname');
        const category = target.attr('category');
        const reason = target.val();
        const redactList = this.getRedactList();
        let isRedacted = redactList[category][keyname] !== undefined;
        if (isRedacted && (!reason || reason === 'none')) {
            delete redactList[category][keyname];
            isRedacted = false;
        } else if ((!isRedacted || redactList[category][keyname].reason !== reason) && reason && reason !== 'none') {
            redactList[category][keyname] = { value: null, reason: reason, category: $(':selected', target).attr('category') };
            isRedacted = true;
        } else {
            // no change
            return;
        }
        restRequest({
            method: 'PUT',
            url: 'wsi_deid/item/' + this.model.id + '/redactList',
            contentType: 'application/json',
            data: JSON.stringify(redactList),
            error: null
        });
        if (this.model.get('meta') === undefined) {
            this.model.set('meta', {});
        }
        this.model.get('meta').redactList = redactList;
        target.closest('td.large_image_metadata_value').toggleClass('redacted', isRedacted);
        target.closest('td.large_image_metadata_value').find('.redact-replacement').remove();
        target.closest('.g-widget-auximage').toggleClass('redacted', isRedacted);
        return false;
    };

    const showRedactButton = (keyname) => {
        if (keyname.match(/^internal;aperio_version$/)) {
            return false;
        }
        if (keyname.match(/^internal;openslide;openslide\.(?!comment$)/)) {
            return false;
        }
        if (keyname.match(/^internal;openslide;tiff.(ResolutionUnit|XResolution|YResolution)$/)) {
            return false;
        }
        return true;
    };

    const addRedactButton = (parentElem, keyname, redactRecord, category) => {
        let elem = $('<select class="g-hui-redact"/>');
        elem.attr({
            keyname: keyname,
            category: category,
            title: 'Redact this ' + category
        });
        elem.append($('<option value="none">Keep (do not redact)</option>'));
        let matched = false;
        PHIPIITypes.forEach((cat) => {
            if (cat.types) {
                let optgroup = $('<optgroup/>');
                optgroup.attr({ label: cat.text });
                cat.types.forEach((phitype) => {
                    let opt = $('<option/>').attr({ value: phitype.key, category: cat.category }).text(phitype.text);
                    if (redactRecord && redactRecord.reason === phitype.key) {
                        opt.attr('selected', 'selected');
                        matched = true;
                    }
                    optgroup.append(opt);
                });
                elem.append(optgroup);
            } else {
                let opt = $('<option/>').attr({ value: cat.key, category: cat.category }).text(cat.text);
                if (redactRecord && redactRecord.reason === cat.key) {
                    opt.attr('selected', 'selected');
                    matched = true;
                }
                elem.append(opt);
            }
        });
        if (!matched && redactRecord) {
            $('[value="Other_PHIPII"]', elem).attr('selected', 'selected');
        }
        elem = $('<span class="g-hui-redact-label">Redact</span>').append(elem);
        parentElem.append(elem);
    };

    const hideField = (keyname) => {
        const isAperio = this.$el.find('.large_image_metadata_value[keyname^="internal;openslide;aperio."]').length > 0;
        if (isAperio && keyname.match(/^internal;openslide;(openslide.comment|tiff.ImageDescription)$/)) {
            return true;
        }
        if (keyname.match(/^internal;openslide;openslide.level\[/)) {
            return true;
        }
        if (keyname.match(/^internal;openslide;hamamatsu.(AHEX|MHLN)\[/)) {
            return true;
        }
        return false;
    };

    const addRedactionControls = (showControls, settings) => {
        /* if showControls is false, the tabs are still adjusted and some
         * fields may be hidden, but the actual redaction controls aren't
         * shown. */
        // default to showing the last metadata tab
        this.$el.find('.li-metadata-tabs .nav-tabs li').removeClass('active');
        this.$el.find('.li-metadata-tabs .nav-tabs li').last().addClass('active');
        this.$el.find('.li-metadata-tabs .tab-pane').removeClass('active');
        this.$el.find('.li-metadata-tabs .tab-pane').last().addClass('active');

        const redactList = this.getRedactList();
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
                let redactButtonAllowed = true;
                if (isRedacted && redactList.metadata[keyname].value) {
                    elem.append($('<span class="redact-replacement"/>').text(redactList.metadata[keyname].value));
                    redactButtonAllowed = false;
                }
                if (showRedactButton(keyname) && redactButtonAllowed) {
                    addRedactButton(elem, keyname, redactList.metadata[keyname], 'metadata');
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
                elem.find('.g-hui-redact').remove();
                addRedactButton(elem.find('.g-widget-auximage-title'), keyname, redactList.images[keyname], 'images');
                if (keyname === 'macro' && settings.redact_macro_square) {
                    elem.addClass('redact-square');
                    let redactsquare = $('<div class="g-widget-auximage-image-redact-square" title="This region will be blacked out">&nbsp;</div>');
                    elem.find('.g-widget-auximage-image').append(redactsquare);
                }
                let isRedacted = redactList.images[keyname] !== undefined;
                elem.toggleClass('redacted', isRedacted);
            });
            this.events['input .g-hui-redact'] = flagRedaction;
            this.events['change .g-hui-redact'] = flagRedaction;
            this.events['click .g-hui-redact-label'] = (event) => {
                event.stopPropagation();
                return false;
            };
            this.delegateEvents();
        }
    };

    const workflowButton = (event) => {
        const target = $(event.currentTarget);
        const action = target.attr('action');
        const actions = {
            quarantine: { done: 'Item quarantined.', fail: 'Failed to quarantine item.' },
            unquarantine: { done: 'Item unquarantined.', fail: 'Failed to unquarantine item.' },
            process: { done: 'Item redacted.', fail: 'Failed to redact item.' },
            reject: { done: 'Item rejected.', fail: 'Failed to reject item.' },
            finish: { done: 'Item moved to approved folder.', fail: 'Failed to approve item.' }
        };
        $('body').append(
            '<div class="g-hui-loading-overlay"><div>' +
            '<i class="icon-spin4 animate-spin"></i>' +
            '</div></div>');
        restRequest({
            method: 'PUT',
            url: 'wsi_deid/item/' + this.model.id + '/action/' + action,
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
            if (action === 'finish') {
                goToNextUnprocessedItem((resp) => {
                    if (!resp) {
                        this.model.fetch({ success: () => this.render() });
                    }
                });
            } else {
                this.model.fetch({ success: () => this.render() });
            }
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

    const adjustControls = (folderType, settings) => {
        addRedactionControls(folderType === 'ingest' || folderType === 'quarantine', settings || {});
        /* Start with the metadata section collapsed */
        this.$el.find('.g-widget-metadata-header:first').attr({ 'data-toggle': 'collapse', 'data-target': '.g-widget-metadata-container:first' });
        this.$el.find('.g-widget-metadata-container:first').addClass('collapse');
        /* Don't show the annotation list */
        this.$el.find('.g-annotation-list-container').remove();
        /* Show workflow buttons */
        this.$el.append(ItemViewTemplate({
            project_folder: folderType
        }));
        /* Place a copy of any reject buttons in the item header */
        this.$el.find('.g-item-image-viewer-select .g-item-info-header').append(this.$el.find('.g-workflow-button[action="reject"]').clone());
        this.events['click .g-workflow-button'] = workflowButton;
        this.delegateEvents();
    };

    this.once('g:largeImageItemViewRendered', function () {
        // if (this.model.get('largeImage') && this.model.get('largeImage').fileId && this.accessLevel >= AccessType.WRITE) {
        if (this.model.get('largeImage') && this.model.get('largeImage').fileId && getCurrentUser()) {
            restRequest({
                url: `wsi_deid/project_folder/${this.model.get('folderId')}`,
                error: null
            }).done((resp) => {
                if (resp) {
                    restRequest({
                        url: `wsi_deid/settings`,
                        error: null
                    }).done((settings) => {
                        adjustControls(resp, settings);
                    });
                }
            });
        }
    });

    render.call(this);
});

wrap(ItemViewWidget, 'render', function (render) {
    /* Add any internal metadata items that will be added but don't already
     * exist. */
    let internal = this.metadata.internal;
    Object.entries(this.parentView.getRedactList().metadata).forEach(([k, v]) => {
        let parts = k.split(';');
        if (parts[0] !== 'internal' || !v || v.value === undefined || parts.length !== 3) {
            return;
        }
        if (internal[parts[1]] && internal[parts[1]][parts[2]] === undefined) {
            internal[parts[1]][parts[2]] = '';
        }
        // sort the results
        let sorted = {};
        Object.keys(internal[parts[1]]).sort().forEach((k) => {
            sorted[k] = internal[parts[1]][k];
        });
        internal[parts[1]] = sorted;
    });
    render.call(this);
});
ItemViewWidget._deid = true;
