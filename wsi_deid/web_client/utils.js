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

export {
    goToNextUnprocessedItem
};
