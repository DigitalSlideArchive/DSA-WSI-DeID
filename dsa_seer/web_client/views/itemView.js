import { AccessType } from '@girder/core/constants';
import { restRequest } from '@girder/core/rest';
import { wrap } from '@girder/core/utilities/PluginUtils';
import ItemView from '@girder/core/views/body/ItemView';

import '../stylesheets/itemView.styl';

wrap(ItemView, 'render', function (render) {

    const getRedactList = () => {
        let redact_list = (this.model.get('meta') || {}).redact_list || {};
        redact_list.metadata = redact_list.metadata || [];
        redact_list.images = redact_list.images || [];
        return redact_list;
    };

    const flagRedaction = (event) => {
        event.stopPropagation();
        const target = $(event.currentTarget);
        const keyname = target.attr('keyname');
        const category = target.attr('category');
        const undo = target.hasClass('undo');
        const redact_list = getRedactList();
        const index = redact_list[category].indexOf(keyname);
        if (index >= 0 && undo) {
            redact_list[category].splice(index, 1);
        } else if (index < 0 && !undo) {
            redact_list[category].push(keyname);
        }
        this.model.editMetadata('redact_list', 'redact_list', redact_list);
        target.toggleClass('undo');
        if (this.model.get('meta') === undefined) {
            this.model.set('meta', {});
        }
        this.model.get('meta').redact_list = redact_list;
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
            let is_redacted = redact_list.metadata.indexOf(keyname) >= 0;
            elem.find('.g-hui-redact').remove();
            elem.append($('<a class="g-hui-redact' + (is_redacted ? ' undo' : '') + '"><span>Redact</span></a>').attr({
                keyname: keyname,
                category: 'metadata',
                title: 'Toggle redacting this metadata'
            }));
        });
        // Add redaction controls to images
        this.$el.find('.g-widget-metadata-container.auximage .g-widget-auximage').each((idx, elem) => {
            elem = $(elem);
            let keyname = elem.attr('auximage');
            let is_redacted = redact_list.images.indexOf(keyname) >= 0;
            elem.find('.g-hui-redact').remove();
            elem.find('.g-widget-auximage-title').append($('<a class="g-hui-redact' + (is_redacted ? ' undo' : '') + '"><span>Redact</span></a>').attr({
                keyname: keyname,
                category: 'images',
                title: 'Toggle redacting this image'
            }));
        });
        // TODO: add Process / Reject buttons
        // For other folders, do we want other workflow buttons?
        this.events['click .g-hui-redact'] = flagRedaction;
        this.delegateEvents();
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
            });
        }
    });
    render.call(this);
});
