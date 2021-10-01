import events from '@girder/core/events';
import router from '@girder/core/router';
import { restRequest } from '@girder/core/rest';

function goToNextUnprocessedItem(callback) {
    restRequest({
        url: 'wsi_deid/next_unprocessed_item',
        error: null
    }).done((resp) => {
        if (resp) {
            events.trigger('g:alert', {
                icon: 'right-big',
                text: 'Switching to next unprocessed item',
                timeout: 4000
            });
            router.navigate('item/' + resp, { trigger: true });
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

function pollForOcrResults(itemId, callback, maxAttempts) {
    let gotOcrData = false;
    let attempts = 0;

    const executePoll = () => {
        attempts++;
        restRequest({
            url: 'item/' + itemId,
            error: null
        }).done((resp) => {
            if (gotOcrData) {
                callback(resp['meta']['label_ocr']);
            } else if (attempts >= maxAttempts) {
                callback('Too many attempts');
            } else {
                setTimeout(executePoll, 1000);
            }
        });
    };
    restRequest({
        url: 'item/' + itemId,
        error: null
    }).done((resp) => {
        gotOcrData = resp['meta']['label_ocr'];
        if (gotOcrData) {
            callback(resp['meta']['label_ocr']);
        } else if (attempts >= maxAttempts) {
            callback('Too many attempts');
        } else {
            setTimeout(executePoll, 1000);
        }
    });
    return false;
}

export {
    goToNextUnprocessedItem, pollForOcrResults
};
