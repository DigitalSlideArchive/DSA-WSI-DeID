import $ from 'jquery';
import events from '@girder/core/events';
import { getApiRoot, restRequest } from '@girder/core/rest';
import View from '@girder/core/views/View';

import '@girder/core/utilities/jquery/girderModal';
import matchingDialog from '../templates/MatchingDialog.pug';
import '../stylesheets/MatchingDialog.styl';


const MatchingDialog = View.extend({
    events: {
        'click .h-lookup': '_lookup',
        'click .h-apply': '_apply'
    },

    initialize(settings) {
        this.model = settings.model;
        this.itemView = settings.itemView;
    },

    render() {
        this.$el.html(
            matchingDialog({
                label_image_url: `${getApiRoot()}/item/${this.model.id}/tiles/images/label?width=400&height=400&_${this.model.get('updated')}`
            })
        ).girderModal(this);
        return this;
    },

    _lookup(evt) {
        const params = {};
        this.$el.find('.matching-value').each(function () {
            const val = ($(this).val() || '').trim();
            const key = $(this).attr('key');
            if (val) {
                params[key] = val;
            }
        });
        this.$el.find('tr[record]').addClass('hidden');
        this.$el.find('#lookup-results').addClass('hidden');
        restRequest({
            method: 'POST',
            url: `wsi_deid/matching`,
            contentType: 'application/json',
            data: JSON.stringify(params),
            error: null
        }).done((resp) => {
            this.last_results = resp;
            if (!resp.length) {
                this.$el.find('tr[record="none"]').removeClass('hidden');
            } else {
                for (let idx = 0; idx < 5 && idx < resp.length; idx += 1) {
                    const results = [];
                    resp[idx].tumors.forEach((t) => {
                        Object.entries(t).forEach(([k, v]) => {
                            results.push($('<div>').text(`${k}: ${v}`));
                        });
                    });
                    this.$el.find(`tr[record="${idx}"] td.token-id-label`).text(resp[idx].token_id);
                    this.$el.find(`tr[record="${idx}"] td.result-entry`).empty();
                    results.forEach((d) => {
                        this.$el.find(`tr[record="${idx}"] td.result-entry`).append(d);
                    });
                    this.$el.find(`tr[record="${idx}"]`).removeClass('hidden');
                }
            }
            this.$el.find('#lookup-results').removeClass('hidden');
        });
    },

    _apply(evt) {
        evt.preventDefault();
        const record = this.last_results[+($(evt.target).closest('tr[record]').attr('record'))];
        restRequest({
            method: 'POST',
            url: `wsi_deid/item/${this.model.id}/action/refile/${record.token_id}`,
            contentType: 'application/json',
            data: JSON.stringify(record.tumors[0] || {}),
            error: null
        }).done((resp) => {
            const alertMessage = 'Item refiled.';
            $('.g-hui-loading-overlay').remove();
            events.trigger('g:alert', {
                icon: 'ok',
                text: alertMessage,
                type: 'success',
                timeout: 4000
            });
            delete this.itemView.model.parent;
            this.itemView.model.fetch({ success: () => this.render() });
        }).fail((resp) => {
            $('.g-hui-loading-overlay').remove();
            let text = 'Failed to refile item.';
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
        this.$el.modal('hide');
    }
});


function show(settings) {
    const dialog = new MatchingDialog({
        parentView: null,
        model: settings.model,
        itemView: settings.itemView,
        el: $('#g-dialog-container')
    });
    return dialog.render();
}

export default show;
