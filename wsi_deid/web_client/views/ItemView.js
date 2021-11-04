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
import ItemViewNextTemplate from '../templates/ItemViewNext.pug';
import ItemViewRedactAreaTemplate from '../templates/ItemViewRedactArea.pug';
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

const systemRedactedReason = 'System Redacted';

const formats = {
    aperio: 'aperio',
    hamamatsu: 'hamamatsu',
    philips: 'philips',
    none: ''
};

let auxImageMaps = {};

wrap(ItemView, 'render', function (render) {
    this.getRedactList = () => {
        let redactList = (this.model.get('meta') || {}).redactList || {};
        redactList.metadata = redactList.metadata || {};
        redactList.images = redactList.images || {};
        redactList.area = redactList.area || {};
        ['images', 'metadata'].forEach((main) => {
            for (let key in redactList[main]) {
                if (!_.isObject(redactList[main][key]) || redactList[main][key] === null) {
                    redactList[main][key] = { value: redactList[main][key] };
                }
            }
        });
        return redactList;
    };

    this.putRedactList = function (redactList, source) {
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
    };

    const flagRedaction = (event) => {
        event.stopPropagation();
        let target = $(event.currentTarget);
        const isSquare = target.is('.g-hui-redact-square,.g-hui-redact-square-span');
        const isInput = target.is('.wsi-deid-replace-value');
        if (isSquare) {
            target = target.closest('.g-hui-redact-label').find('.g-hui-redact');
        }
        const keyname = target.attr('keyname');
        const category = target.attr('category');
        let reason = target.val();
        const redactList = this.getRedactList();
        let isRedacted = redactList[category][keyname] !== undefined;
        if (isSquare) {
            redactList[category][keyname].square = !redactList[category][keyname].square;
        } else if (isInput) {
            const newValue = target.find('.wsi-deid-replace-value-input').val();
            const oldValue = redactList[category][keyname].value;
            if (newValue === oldValue) {
                // no change
                return;
            } else {
                let redactRecord = redactList[category][keyname];
                redactList[category][keyname] = { value: newValue, reason: redactRecord.reason, category: redactRecord.category };
            }
        } else {
            if (target.is('a')) { // button, not select
                reason = isRedacted ? 'none' : 'No_Reason_Collected';
            }
            if (isRedacted && (!reason || reason === 'none')) {
                delete redactList[category][keyname];
                isRedacted = false;
            } else if ((!isRedacted || redactList[category][keyname].reason !== reason) && reason && reason !== 'none') {
                let redactRecordValue = '';
                let redactRecord = redactList[category][keyname];
                if (redactRecord) {
                    redactRecordValue = redactRecord.value;
                }
                redactList[category][keyname] = { value: redactRecordValue, reason: reason, category: $(':selected', target).attr('category') || reason };
                isRedacted = true;
            } else {
                // no change
                return;
            }
        }
        const redactSquare = (redactList[category][keyname] || {}).square || (!isRedacted && target.closest('.g-widget-auximage').hasClass('always-redact-square'));
        this.putRedactList(redactList, 'flagRedaction');
        target.closest('td.large_image_metadata_value').toggleClass('redacted', isRedacted);
        target.closest('td.large_image_metadata_value').find('.redact-replacement').remove();
        target.closest('.g-widget-auximage').toggleClass('redacted', isRedacted && !redactSquare);
        target.closest('.g-widget-auximage').toggleClass('redact-square', !!redactSquare);
        target.closest('.g-widget-auximage').find('input[type="checkbox"]').prop('checked', !!redactSquare);
        return isSquare && $(event.target).is('input[type="checkbox"]');
    };

    const getFormat = () => {
        if (this.$el.find('.large_image_metadata_value[keyname^="internal;openslide;openslide.vendor"]').text() === 'aperio') {
            return formats.aperio;
        } else if (this.$el.find('.large_image_metadata_value[keyname^="internal;openslide;openslide.vendor"]').text() === 'hamamatsu') {
            return formats.hamamatsu;
        } else if (this.$el.find('.large_image_metadata_value[keyname^="internal;xml;PIM_DP_"]').length > 0) {
            return formats.philips;
        } else {
            return formats.none;
        }
    };

    const isValidRegex = (string) => {
        try {
            void new RegExp(string);
        } catch (e) {
            console.error(`There was an error parsing "${string}" as a regular expression: ${e}.`);
            return false;
        }
        return true;
    };

    const validateRedactionPatternObject = (redactionPatterns) => {
        for (const key in redactionPatterns) {
            if (!isValidRegex(key) || !isValidRegex(redactionPatterns[key])) {
                delete redactionPatterns[key];
            }
        }
        return redactionPatterns;
    };

    const getRedactionDisabledPatterns = (settings) => {
        const format = getFormat();
        let patterns = settings.no_redact_control_keys || {}; // patterns is an object that looks like {key:value}, where `key` and `value` are both regular expressions
        patterns = Object.assign({}, patterns, settings['no_redact_control_keys_format_' + format] || {});
        return validateRedactionPatternObject(patterns);
    };

    const getHiddenMetadataPatterns = (settings) => {
        const format = getFormat();
        let patterns = settings.hide_metadata_keys || {};
        patterns = Object.assign({}, patterns, settings['hide_metadata_keys_format_' + format] || {});
        return validateRedactionPatternObject(patterns);
    };

    const showRedactButton = (keyname, disableRedactionPatterns) => {
        for (const metadataPattern in disableRedactionPatterns) {
            if (keyname.match(new RegExp(metadataPattern))) {
                const value = this.$el.find(`.large_image_metadata_value[keyname^="${keyname}"]`).text();
                const expectedValuePattern = new RegExp(disableRedactionPatterns[metadataPattern]);

                // If the value of the metadata field matches the expected pattern (e.g., a number
                // or comma-separated list of numbers), do not show the redact button
                return !(expectedValuePattern.test(value));
            }
        }
        return true;
    };

    const addRedactButton = (parentElem, keyname, redactRecord, category, settings, title) => {
        if (title === undefined || title === null) {
            title = 'Redact';
        }
        let elem;
        if (settings.require_redact_category !== false) {
            elem = $('<select class="g-hui-redact"/>');
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
            elem = $('<span class="g-hui-redact-label">' + title + '</span>').append(elem);
        } else {
            elem = $('<a class="g-hui-redact' + (redactRecord && redactRecord.reason ? ' undo' : '') + '"><span>' + title + '</span></a>').attr({
                keyname: keyname,
                category: category,
                title: 'Toggle redacting this ' + category
            });
            elem = $('<span class="g-hui-redact-label"></span>').append(elem);
        }
        if (['label', 'macro'].includes(keyname)) {
            const redactArea = ItemViewRedactAreaTemplate({ keyname: keyname });
            this.events['click .g-widget-auximage-title .g-widget-redact-area-container button'] = redactAreaAuxImage;
            parentElem.append(elem).append(redactArea);
        } else {
            parentElem.append(elem);
        }
    };

    const addNewValueEntryField = (parentElem, keyname, redactRecord, settings) => {
        if (!settings.edit_metadata) {
            return;
        }

        let inputId = `redact-value-${keyname}`;
        let inputField = $(`<input type="text" id="${inputId}" class="wsi-deid-replace-value-input">`);

        if (redactRecord && redactRecord.value) {
            inputField.attr({ value: redactRecord.value });
        }

        let inputControl = $(`<label for="${inputId}">New value:</label>`).append(inputField);
        inputControl = $('<span class="wsi-deid-replace-value"></span>').append(inputControl);
        inputControl.attr({
            keyname: keyname,
            category: 'metadata'
        });
        parentElem.append(inputControl);
    };

    const hideField = (keyname, hideFieldPatterns) => {
        for (const metadataPattern in hideFieldPatterns) {
            if (keyname.match(new RegExp(metadataPattern))) {
                const value = this.$el.find(`.large_image_metadata_value[keyname^="${keyname}"]`).text();
                const expectedValuePattern = new RegExp(hideFieldPatterns[metadataPattern]);

                // If the value of the metadata field matches the expected pattern,
                // hide the metadata field.
                return expectedValuePattern.test(value);
            }
        }
        return false;
    };

    const resizeRedactSquare = (elem) => {
        let image = elem.find('.g-widget-auximage-image img');
        if (!image.length) {
            return;
        }
        let minwh = Math.min(image.width(), image.height());
        if (minwh > 0) {
            let redactsquare = elem.find('.g-widget-auximage-image-redact-square');
            redactsquare.width(minwh);
            redactsquare.height(minwh);
            return;
        }
        window.setTimeout(() => resizeRedactSquare(elem), 1000);
    };

    const resizeRedactBackground = (elem) => {
        let image = elem.find('.g-widget-auximage-image img');
        if (!image.length) {
            return;
        }
        let minwh = Math.min(image.width(), image.height());
        if (minwh > 0) {
            let redact = elem.find('.g-widget-auximage-image');
            redact.width(image.width());
            redact.height(image.height());
            return;
        }
        window.setTimeout(() => resizeRedactBackground(elem), 1000);
    };

    const addAuxImageMaps = (settings, redactList) => {
        this.$el.find('.g-widget-metadata-container.auximage .g-widget-auximage').each((idx, elem) => {
            elem = $(elem);
            let imageElem = elem.find('.g-widget-auximage-image');
            elem.wrap($('<div class="wsi-deid-auximage-container"></div>'));
            let keyname = elem.attr('auximage');
            // return true to 'continue' the loop. use configuration to drive which images to skip map creation
            if (!['label', 'macro'].includes(keyname)) {
                return true;
            }
            if (keyname === 'macro' && settings.redact_macro_square) {
                return true;
            }
            if (keyname === 'label' && settings.always_redact_label) {
                return true;
            }
            let mapId = `${keyname}-map`;
            let tilesPath = `item/${this.model.id}/tiles`;
            let mapDiv = $(`<div id="${mapId}" class="wsi-deid-associated-image-map"></div>`);
            mapDiv.attr('keyname', keyname);
            elem.after(mapDiv);

            restRequest({
                url: `${tilesPath}/images/${keyname}/metadata`,
                error: null
            }).done((resp) => {
                try {
                    let params = window.geo.util.pixelCoordinateParams(
                        `#${mapId}`, resp.sizeX, resp.sizeY, resp.sizeX, resp.sizeY);
                    let imgH = imageElem.height();
                    let imgW = imageElem.width();
                    $(`#${mapId}`).width(imgW).height(imgH);
                    const map = window.geo.map(params.map);
                    auxImageMaps[keyname] = map;
                    params.layer.url = `/api/v1/${tilesPath}/images/${keyname}`;
                    map.createLayer('osm', params.layer);
                    const annLayer = map.createLayer('annotation', {
                        annotations: ['polygon'],
                        showLabels: false,
                        clickToEdit: false
                    });
                    if (redactList.images && redactList.images[keyname] && redactList.images[keyname].geojson) {
                        imageElem.addClass('no-disp');
                        annLayer.geojson(redactList.images[keyname].geojson);
                        annLayer.draw();
                        const button = this.$el.find(`.g-widget-auximage-title .g-widget-redact-area-container button[keyname=${keyname}]`);
                        const container = button.parent();
                        container.addClass('area-set').removeClass('area-adding');
                        annLayer.options('clickToEdit', true);
                    } else {
                        mapDiv.addClass('no-disp');
                    }
                } catch (e) {
                    mapDiv.addClass('no-disp');
                    console.error(`Failed to create map for ${keyname} image. ${e}.`);
                }
            });
        });
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
        const disableRedactionPatterns = getRedactionDisabledPatterns(settings);
        const hideFieldPatterns = getHiddenMetadataPatterns(settings);
        // Add redaction controls to metadata
        this.$el.find('table[keyname="internal"] .large_image_metadata_value').each((idx, elem) => {
            elem = $(elem);
            let keyname = elem.attr('keyname');
            if (!keyname || ['internal;tilesource'].indexOf(keyname) >= 0) {
                return;
            }
            elem.find('.g-hui-redact').remove();
            if (hideField(keyname, hideFieldPatterns)) {
                elem.closest('tr').css('display', 'none');
            }
            if (showControls) {
                let isRedacted = redactList.metadata[keyname] !== undefined;
                let redactButtonAllowed = true;
                const redactReason = isRedacted ? redactList.metadata[keyname].reason : '';
                if (isRedacted && redactList.metadata[keyname].value && (redactReason === systemRedactedReason || redactReason === undefined)) {
                    elem.append($('<span class="redact-replacement"/>').text(redactList.metadata[keyname].value));
                    redactButtonAllowed = false;
                }
                if (showRedactButton(keyname, disableRedactionPatterns) && redactButtonAllowed) {
                    addNewValueEntryField(elem, keyname, redactList.metadata[keyname], settings);
                    addRedactButton(elem, keyname, redactList.metadata[keyname], 'metadata', settings);
                }
                elem.toggleClass('redacted', isRedacted);
            }
        });
        // Add redaction controls to images
        if (showControls) {
            this.$el.find('.g-widget-metadata-container.auximage .g-widget-auximage').each((idx, elem) => {
                elem = $(elem);
                let keyname = elem.attr('auximage');
                elem.find('.g-hui-redact').remove();
                resizeRedactBackground(elem);
                let isRedacted = redactList.images[keyname] !== undefined;
                if (keyname !== 'label' || !settings.always_redact_label) {
                    addRedactButton(elem.find('.g-widget-auximage-title'), keyname, redactList.images[keyname], 'images', settings);
                } else {
                    isRedacted = true;
                }
                let redactSquare = false;
                if (keyname === 'macro') {
                    let redactsquare = $('<div class="g-widget-auximage-image-redact-square" title="This region will be blacked out"><div class="fill">&nbsp;</div></div>');
                    elem.find('.g-widget-auximage-image').append(redactsquare);
                    resizeRedactSquare(elem);
                    if (!settings.redact_macro_square) {
                        let check = $('<span class="g-hui-redact-square-span"><input type="checkbox" class="g-hui-redact-square"></input>Partial</span>');
                        if ((redactList.images[keyname] || {}).square) {
                            check.find('input[type="checkbox"]').prop('checked', true);
                            redactSquare = true;
                        }
                        elem.find('.g-widget-auximage-title .g-hui-redact-label').append(check);
                    } else {
                        redactSquare = true;
                        elem.addClass('always-redact-square');
                    }
                    if (redactSquare) {
                        elem.addClass('redact-square');
                    }
                }
                elem.toggleClass('redacted', isRedacted && !redactSquare);
            });
            if (showControls) {
                try {
                    addAuxImageMaps(settings, redactList);
                } catch (e) {
                    console.error(`Attempting to add GeoJS maps for associated images resulted in the following error: ${e}.`);
                }
            }
            this.events['input .g-hui-redact'] = flagRedaction;
            this.events['change .g-hui-redact'] = flagRedaction;
            this.events['click a.g-hui-redact'] = flagRedaction;
            this.events['click .g-hui-redact-square-span'] = flagRedaction;
            this.events['change .wsi-deid-replace-value'] = flagRedaction;
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

    const getWSIAnnotationLayer = () => {
        const map = this.imageViewerSelect.currentViewer.viewer;
        return map.layers().filter((l) => l instanceof window.geo.annotationLayer)[0];
    };

    /**
     * Toggle showing the image or a geojs map of the image.
     * If redacting the whole image or top/right square, no need to show the map.
     * @param {object} mapContainer The container element of the geojs map to show/hide
     * @param {object} imageContainer The container element of the associated image to show/hide
     * @param {boolean} showMap Truthy to show the map and hide the image, falsy to hide the map and show the original image
     */
    const toggleAuxImageMapDisplay = (mapContainer, imageContainer, showMap) => {
        if (showMap) {
            // adjust height and width of map, since they may be wrong on initial load of an image
            mapContainer.height(imageContainer.height());
            mapContainer.width(imageContainer.width());
            mapContainer.removeClass('no-disp');
            imageContainer.addClass('no-disp');
        } else {
            mapContainer.addClass('no-disp');
            imageContainer.removeClass('no-disp');
        }
    };

    /**
     * Helper function to toggle the display and remove checked status of the redact square control for macro images.
     * @param {boolean} showControl True to show the 'redact square' control, false to hide it
     */
    const toggleRedactSquareControlDisplay = (showControl) => {
        let redactSquareSpan = this.$el.find('.g-hui-redact-square-span');
        let redactSquareInput = redactSquareSpan.find('.g-hui-redact-square');
        redactSquareInput.prop('checked', false);
        redactSquareSpan.toggleClass('no-disp', !showControl);
    };

    const handleAuxImageAnnotationMode = (event) => {
        const eventMap = event.geo._triggeredBy;
        const annLayer = eventMap.layers().filter((l) => l instanceof window.geo.annotationLayer)[0];
        const mapContainer = eventMap.node();
        const keyname = mapContainer.attr('keyname');
        const button = this.$el.find(`.g-widget-auximage-title .g-widget-redact-area-container button[keyname=${keyname}]`);
        const container = button.parent();

        if (annLayer.mode()) {
            button.addClass('active');
            container.addClass('area-adding').removeClass('area-set');
            return;
        }
        annLayer.annotations().forEach((a) => a.style({ fillColor: 'white', fillOpacity: 0.5 }));
        annLayer.draw();
        let redactList = this.getRedactList();
        redactList.images = redactList.images || {};
        redactList.images[keyname] = redactList.images[keyname] || {};
        redactList.images[keyname].geojson = annLayer.geojson();
        if (!redactList.images[keyname].geojson) {
            delete redactList.images[keyname].geojson;
        }
        this.putRedactList(redactList, 'handleAuxImageAnnotationMode');
        button.removeClass('active');
        container.removeClass('area-adding').toggleClass('area-set', !!redactList.images[keyname].geojson);
    };

    const handleWSIAnnotationMode = () => {
        const annLayer = getWSIAnnotationLayer();
        if (annLayer.mode()) {
            this.$el.find('.g-item-info-header .g-widget-redact-area-container button').addClass('active');
            this.$el.find('.g-item-info-header .g-widget-redact-area-container').addClass('area-adding').removeClass('area-set');
            return;
        }
        annLayer.annotations().forEach((a) => a.style({ fillColor: 'white', fillOpacity: 0.5 }));
        annLayer.draw();
        let redactList = this.getRedactList();
        redactList.area = redactList.area || {};
        redactList.area._wsi = redactList.area._wsi || {};
        redactList.area._wsi.geojson = annLayer.geojson();
        if (!redactList.area._wsi.geojson) {
            delete redactList.area._wsi;
        } else {
            if (!redactList.area._wsi.reason) {
                redactList.area._wsi.reason = 'No_Reason_Collected';
                delete redactList.area._wsi.category;
                let reasonSelect = this.$el.find('.g-widget-redact-area-container select.g-hui-redact');
                if (reasonSelect.length) {
                    let reasonElem = $(':selected', reasonSelect);
                    if (!reasonElem.length || reasonElem.val() === 'none' || !reasonElem.val()) {
                        reasonElem = reasonSelect.find('option:last');
                    }
                    redactList.area._wsi.reason = reasonElem.val();
                    redactList.area._wsi.category = reasonElem.attr('category');
                    reasonElem.prop('selected', true);
                }
            }
        }
        this.putRedactList(redactList, 'handleWSIAnnotationMode');
        this.$el.find('.g-item-info-header .g-widget-redact-area-container button').removeClass('active');
        this.$el.find('.g-item-info-header .g-widget-redact-area-container').removeClass('area-adding').toggleClass('area-set', !!redactList.area._wsi);
    };

    const redactAreaAuxImage = (event) => {
        event.stopPropagation();
        let clickedButton = $(event.currentTarget);
        let buttonContainer = clickedButton.parent();
        let keyname = clickedButton.attr('keyname');
        const map = auxImageMaps[keyname];
        const imageElem = this.$el.find(`.g-widget-metadata-container.auximage .wsi-deid-auximage-container .g-widget-auximage[auximage=${keyname}] .g-widget-auximage-image img`);
        const annLayer = map.layers().filter((l) => l instanceof window.geo.annotationLayer)[0];
        let redactList = this.getRedactList();
        if (buttonContainer.hasClass('area-set') || buttonContainer.hasClass('area-adding')) {
            clickedButton.removeClass('active');
            buttonContainer.removeClass('area-set').removeClass('area-adding');
            redactList.images = redactList.images || {};
            delete redactList.images[keyname].geojson;
            this.putRedactList(redactList, 'redactAreaAuxImage');
            annLayer.annotations().forEach((a) => annLayer.removeAnnotation(a));
            annLayer.draw();
            if (annLayer.mode()) {
                annLayer.mode(null);
            }
            toggleAuxImageMapDisplay(map.node(), imageElem.parent(), false);
            if (keyname === 'macro') {
                toggleRedactSquareControlDisplay(true);
            }
            return false;
        }

        toggleAuxImageMapDisplay(map.node(), imageElem.parent(), true);
        if (keyname === 'macro') {
            toggleRedactSquareControlDisplay(false);
            redactList.images = redactList.images || {};
            if (redactList.images[keyname]) {
                delete redactList.images[keyname]['square'];
            }
        }
        annLayer.options('clickToEdit', true);
        annLayer.mode('polygon');
        clickedButton.addClass('active');
        buttonContainer.addClass('area-adding');

        annLayer.geoOff(window.geo.event.annotation.mode, handleAuxImageAnnotationMode);
        annLayer.geoOn(window.geo.event.annotation.mode, handleAuxImageAnnotationMode);
        return false;
    };

    const redactAreaWSI = (event) => {
        event.stopPropagation();
        const annLayer = getWSIAnnotationLayer();
        if (this.$el.find('.g-item-info-header .g-widget-redact-area-container.area-adding,.g-item-info-header .g-widget-redact-area-container.area-set').length) {
            let redactList = this.getRedactList();
            redactList.area = redactList.area || {};
            delete redactList.area._wsi;
            this.putRedactList(redactList, 'redactAreaWSI');
            this.$el.find('.g-item-info-header .g-widget-redact-area-container button').removeClass('active');
            this.$el.find('.g-item-info-header .g-widget-redact-area-container').removeClass('area-adding').removeClass('area-set');
            annLayer.annotations().forEach((a) => annLayer.removeAnnotation(a));
            annLayer.draw();
            if (annLayer.mode()) {
                annLayer.mode(null);
            }
            return;
        }
        annLayer.options('clickToEdit', true);
        annLayer.mode('polygon');
        this.$el.find('.g-item-info-header .g-widget-redact-area-container button').addClass('active');
        this.$el.find('.g-item-info-header .g-widget-redact-area-container').addClass('area-adding');
        // when entering any non-null mode, disable drawing on associated images
        annLayer.geoOff(window.geo.event.annotation.mode, handleWSIAnnotationMode);
        annLayer.geoOn(window.geo.event.annotation.mode, handleWSIAnnotationMode);
    };

    const adjustControls = (folderType, settings) => {
        let hasRedactionControls = (folderType === 'ingest' || folderType === 'quarantine');
        addRedactionControls(hasRedactionControls, settings || {});
        /* Start with the metadata section collapsed */
        this.$el.find('.g-widget-metadata-header:first').attr({ 'data-toggle': 'collapse', 'data-target': '.g-widget-metadata-container:first' });
        this.$el.find('.g-widget-metadata-container:first').addClass('collapse');
        /* Don't show the annotation list */
        this.$el.find('.g-annotation-list-container').remove();
        /* Show workflow buttons */
        $('#g-app-body-container').children(':not(.g-widget-next-container)').last().after(ItemViewTemplate({
            project_folder: folderType
        }));
        /* Place a copy of any reject buttons in the item header */
        this.$el.find('.g-item-image-viewer-select .g-item-info-header').append(this.$el.find('.g-workflow-button[action="reject"]').clone());
        this.events['click .g-workflow-button'] = workflowButton;
        /* Place an area redaction control in the item header */
        if (hasRedactionControls) {
            const redactArea = ItemViewRedactAreaTemplate({});
            this.$el.find('.g-item-image-viewer-select .g-item-info-header').append(redactArea);
            this.events['click .g-item-info-header .g-widget-redact-area-container button'] = redactAreaWSI;
            if (settings.require_redact_category !== false) {
                let redactList = (this.model.get('meta') || {}).redactList || {};
                addRedactButton(this.$el.find('.g-item-image-viewer-select .g-widget-redact-area-container'), '_wsi', (redactList.area || {})._wsi, 'area', settings, '');
            }
            // add an existing area
            addWSIRedactionArea();
        }
        this.delegateEvents();
    };

    const addWSIRedactionArea = () => {
        let redactList = this.getRedactList();
        if (!redactList.area || !redactList.area._wsi || !redactList.area._wsi.geojson) {
            return;
        }
        if (!this.imageViewerSelect.currentViewer.viewer) {
            window.setTimeout(addWSIRedactionArea, 1000);
            return;
        }
        const annLayer = getWSIAnnotationLayer();
        annLayer.geojson(redactList.area._wsi.geojson);
        annLayer.draw();
        this.$el.find('.g-item-info-header .g-widget-redact-area-container').removeClass('area-adding').addClass('area-set');
        annLayer.options('clickToEdit', true);
        annLayer.geoOff(window.geo.event.annotation.mode, handleWSIAnnotationMode);
        annLayer.geoOn(window.geo.event.annotation.mode, handleWSIAnnotationMode);
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

function _setNextPreviousImage(parent) {
    const model = parent.model;
    if (parent._nextPrevious.fetch) {
        parent._nextPrevious.fetch = false;
        const folder = model.parent ? model.parent.id : '';
        restRequest({
            url: `item/${model.id}/adjacent_images`,
            param: { folder: folder }
        }).done((images) => {
            parent._previousImage = images.index !== 0 ? images.previous._id : null;
            parent._previousName = images.previous.name;
            parent._nextImage = images.index + 1 !== images.count ? images.next._id : null;
            parent._nextName = images.next.name;
            parent.render();
        });
    }
}

wrap(ItemViewWidget, 'render', function (render) {
    /* Add any internal metadata items that will be added but don't already
     * exist. */
    let internal = this.metadata.internal || {};
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
    if (!this._nextPrevious) {
        this._nextPrevious = { fetch: true };
        _setNextPreviousImage(this);
    }
    render.call(this);
    this.parentView.$el.find('.g-widget-next-container').remove();
    const nextImageLink = this._nextImage ? `#item/${this._nextImage}` : null;
    const previousImageLink = this._previousImage ? `#item/${this._previousImage}` : null;
    const next = ItemViewNextTemplate({
        previousImageLink: previousImageLink,
        previousImageName: this._previousName,
        nextImageLink: nextImageLink,
        nextImageName: this._nextName
    });
    this.parentView.$el.find('.g-item-breadcrumb-container').eq(0).after(next);
    this.parentView.$el.children().last().after(next);
});
ItemViewWidget._deid = true;
