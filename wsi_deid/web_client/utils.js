import $ from 'jquery';
import _ from 'underscore';

import events from '@girder/core/events';
import router from '@girder/core/router';
import { restRequest } from '@girder/core/rest';

const formats = {
    aperio: 'aperio',
    hamamatsu: 'hamamatsu',
    philips: 'philips',
    ometiff: 'ometiff',
    dicom: 'dicom',
    isyntax: 'isyntax',
    none: ''
};


const systemRedactedReason = 'System Redacted';

function sanitizeInput(input) {
    // SECURITY: Basic input sanitization to prevent XSS
    return $('<div>').text(input).html();
}

function goToNextUnprocessedItem(callback) {
    restRequest({
        url: 'wsi_deid/next_unprocessed_item',
        error: function (err) {
            // SECURITY: Handle errors gracefully
            console.error('Error fetching next unprocessed item:', err);
        }
    }).done((resp) => {
        if (resp) {
            events.trigger('g:alert', {
                icon: 'right-big',
                text: 'Switching to next unprocessed item',
                timeout: 4000
            });
            // SECURITY: Ensure the ID is a valid format before navigating
            const itemId = sanitizeInput(resp);
            router.navigate('item/' + itemId, { trigger: true });
            window.scrollTo(0, 0);
        } else {
            events.trigger('g:alert', {
                icon: 'ok',
                text: 'All items are processed',
                type: 'success',
                timeout: 4000
            });
        }
        if (callback) {
            callback(resp);
        }
    });
    return false;
}

function goToNextUnprocessedFolder(callback, skipId) {
    restRequest({
        url: 'wsi_deid/next_unprocessed_folders',
        error: function (err) {
            // SECURITY: Handle errors gracefully
            console.error('Error fetching next unprocessed folder:', err);
        }
    }).done((resp) => {
        if (resp && resp.length > 1) {
            events.trigger('g:alert', {
                icon: 'right-big',
                text: 'Switching to next unprocessed folder',
                timeout: 4000
            });
            // SECURITY: Ensure the ID is a valid format before navigating
            const folderId = sanitizeInput(resp.filter((i) => i !== skipId)[0]);
            router.navigate('folder/' + folderId, { trigger: true });
            window.scrollTo(0, 0);
        } else {
            events.trigger('g:alert', {
                icon: 'ok',
                text: 'All folders are processed or in use',
                type: 'success',
                timeout: 4000
            });
            if (resp) {
                // SECURITY: Ensure the ID is a valid format before navigating
                const folderId = sanitizeInput(resp.filter((i) => i !== skipId)[0]);
                router.navigate('folder/' + folderId, { trigger: true });
                window.scrollTo(0, 0);
            }
        }
        if (callback) {
            callback(resp);
        }
    });
    return false;
}

function getRedactList(itemModel) {
    // SECURITY: Validate the structure of the returned data
    const redactList = ((itemModel.get && itemModel.get('meta')) || itemModel.meta || {}).redactList || {};
    redactList.metadata = redactList.metadata || {};
    redactList.images = redactList.images || {};
    redactList.area = redactList.area || {};
    ['images', 'metadata'].forEach((main) => {
        for (const key in redactList[main]) {
            if (!_.isObject(redactList[main][key]) || redactList[main][key] === null) {
                redactList[main][key] = { value: redactList[main][key] };
            }
        }
    });
    return redactList;
}

function putRedactList(itemModel, redactList, source) {
    const id = itemModel.get ? itemModel.id : itemModel._id;
    restRequest({
        method: 'PUT',
        url: `wsi_deid/item/${id}/redactList`,
        contentType: 'application/json',
        data: JSON.stringify(redactList),
        error: function (err) {
            // SECURITY: Handle errors gracefully
            console.error('Error updating redact list:', err);
        }
    });
    if (itemModel.get) {
        if (itemModel.get('meta') === undefined) {
            itemModel.set('meta', {});
        }
        itemModel.get('meta').redactList = redactList;
    } else {
        itemModel.meta = itemModel.meta || {};
        itemModel.meta.redactList = redactList;
    }
}

function isValidRegex(string) {
    try {
        new RegExp(string); // eslint-disable-line no-new
    } catch (e) {
        console.error(`There was an error parsing "${string}" as a regular expression: ${e}.`);
        return false;
    }
    return true;
}

function validateRedactionPatternObject(redactionPatterns) {
    for (const key in redactionPatterns) {
        if (!isValidRegex(key) || !isValidRegex(redactionPatterns[key])) {
            delete redactionPatterns[key];
        }
    }
    return redactionPatterns;
}

function getRedactionDisabledPatterns(settings, format) {
    // patterns is an object that looks like {key:value}, where `key` and
    // `value` are both regular expressions
    let patterns = settings.no_redact_control_keys || {};
    patterns = Object.assign({}, patterns, settings['no_redact_control_keys_format_' + format] || {});
    return validateRedactionPatternObject(patterns);
}

function getHiddenMetadataPatterns(settings, format) {
    let patterns = settings.hide_metadata_keys || {};
    patterns = Object.assign({}, patterns, settings['hide_metadata_keys_format_' + format] || {});
    return validateRedactionPatternObject(patterns);
}

function matchFieldPattern(keyname, fieldPatterns, elem, value) {
    const sanitizedKeyname = sanitizeInput(keyname);

    for (const metadataPattern in fieldPatterns) {
        if (keyname.match(new RegExp(metadataPattern))) {
            let _value = value;
            if (_value === undefined) {
                _value = elem.find(`.large_image_metadata_value[keyname^="${sanitizedKeyname}"]:first`).text();
            }
            const expectedValuePattern = new RegExp(fieldPatterns[metadataPattern]);
            // If the value of the metadata field matches the expected pattern,
            // hide the metadata field.
            if (expectedValuePattern.test(_value)) {
                return true;
            }
        }
    }
    return false;
}

function flagRedactionOnItem(itemModel, event) {
    event.stopPropagation();
    let target = $(event.currentTarget);
    const isSquare = target.is('.g-hui-redact-square,.g-hui-redact-square-span');
    const isInput = target.is('.wsi-deid-replace-value');
    if (isSquare) {
        target = target.closest('.g-hui-redact-label').find('.g-hui-redact');
    }

    const keyname = sanitizeInput(target.attr('keyname'));
    const category = sanitizeInput(target.attr('category'));

    let reason = target.val();
    const redactList = getRedactList(itemModel);
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
            const redactRecord = redactList[category][keyname];
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
            const redactRecord = redactList[category][keyname];
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
    putRedactList(itemModel, redactList, 'flagRedaction');
    target.closest('.large_image_metadata_value').toggleClass('redacted', isRedacted);
    target.closest('.large_image_metadata_value').find('.redact-replacement').remove();
    target.closest('.g-widget-auximage').toggleClass('redacted', isRedacted && !redactSquare);
    target.closest('.g-widget-auximage').toggleClass('redact-square', !!redactSquare);
    target.closest('.g-widget-auximage').find('input[type="checkbox"]').prop('checked', !!redactSquare);
    return isSquare && $(event.target).is('input[type="checkbox"]');
}


export {
    formats,
    systemRedactedReason,

    flagRedactionOnItem,
    getHiddenMetadataPatterns,
    getRedactionDisabledPatterns,
    getRedactList,
    goToNextUnprocessedFolder,
    goToNextUnprocessedItem,
    matchFieldPattern,
    putRedactList
};
