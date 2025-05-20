import $ from 'jquery';
import _ from 'underscore';

import { getApiRoot, restRequest } from '@girder/core/rest';
import { wrap } from '@girder/core/utilities/PluginUtils';
import { formatSize } from '@girder/core/misc';
import ItemListWidget from '@girder/large_image/views/itemList';

import {
    formats, flagRedactionOnItem, getRedactList, getRedactionDisabledPatterns,
    getHiddenMetadataPatterns, matchFieldPattern, systemRedactedReason
} from '../utils';

import '../stylesheets/ItemList.styl';
import ItemListTemplate from '../templates/itemList.pug';

wrap(ItemListWidget, 'initialize', function (initialize) {
    const result = initialize.apply(this, _.rest(arguments));

    this.getFormat = (item) => {
        const meta = item.internal_metadata || {};
        if (meta.openslide && meta.openslide['openslide.vendor']) {
            return formats[meta.openslide['openslide.vendor']];
        }
        if (meta.isyntax) {
            return formats.isyntax;
        }
        if (meta.xml && Object.keys(meta.xml).some((key) => key.startsWith('PIM_DP_'))) {
            return formats.philips;
        }
        if (meta.omeinfo) {
            return formats.ometiff;
        }
        return formats.none;
    };

    this.fetchItemList = () => {
        this._wsi_deid_item_list = undefined;
        const items = this.collection.toArray();
        const hasAnyLargeImage = _.some(items, (item) => item.has('largeImage'));
        if (!hasAnyLargeImage) {
            return;
        }
        const folder = this.parentView.parentModel;
        restRequest({
            url: `wsi_deid/folder/${folder.id}/item_list`,
            data: {
                limit: 0,
                images: JSON.stringify(this.collection.map((i) => i.id)),
                recurse: !!this._recurse
            },
            error: null
        }).done((info) => {
            info.byId = {};
            info._redactable = [];
            info._visible = [];
            info.items.forEach((i) => {
                info.byId[i.item._id] = i;
                i._format = this.getFormat(i);
                i._redactList = getRedactList(i.item);
                const disableRedactionPatterns = getRedactionDisabledPatterns(info.wsi_deid_settings, i._format);
                const hideFieldPatterns = getHiddenMetadataPatterns(info.wsi_deid_settings, i._format);
                i._redactable = [];
                i._visible = [];
                i._metadict = {};
                const imeta = i.internal_metadata;
                info.all_metadata_keys.forEach((keylist) => {
                    const keyname = 'internal;' + keylist.join(';');
                    let value = imeta;
                    for (let i = 0; i < keylist.length; i += 1) {
                        if (value[keylist[i]] === undefined) {
                            return;
                        }
                        value = value[keylist[i]];
                    }
                    if (matchFieldPattern(keyname, hideFieldPatterns, undefined, value) || ['internal;populatedLevels', 'internal;iccprofiles;0'].includes(keyname)) {
                        return;
                    }
                    i._metadict[keyname] = value;
                    if (matchFieldPattern(keyname, disableRedactionPatterns, undefined, value) || ['internal;tilesource', 'internal;populatedLevels', 'internal;iccprofiles;0'].includes(keyname)) {
                        i._visible.push(keylist);
                        if (info._visible.indexOf(keylist) < 0) {
                            info._visible.push(keylist);
                        }
                    } else {
                        i._redactable.push(keylist);
                        if (info._redactable.indexOf(keylist) < 0) {
                            info._redactable.push(keylist);
                        }
                    }
                });
            });
            info._redactable.sort();
            info._visible = info._visible.filter((keylist) => info._redactable.indexOf(keylist) < 0);
            info._visible.sort();
            this._wsi_deid_item_list = info;
            this.phiPiiTypes = info.wsi_deid_settings.phi_pii_types;
            this.render();
        });
    };

    const folder = this.parentView.parentModel;
    restRequest({
        url: `wsi_deid/project_folder/${folder.id}`,
        error: null
    }).done((folderKey) => {
        this._folderKey = folderKey;
        if (folderKey) {
            restRequest({
                url: `wsi_deid/settings`,
                error: null
            }).done((settings) => {
                this._wsi_deid_settings = settings;
                if (settings.show_metadata_in_lists === false) {
                    return;
                }
                if (this.collection.length) {
                    this.fetchItemList();
                }
            });
        }
    });
    return result;
});

wrap(ItemListWidget, 'changedFunc', function (changedFunc) {
    this._wsi_deid_item_list = undefined;
    const result = changedFunc.apply(this, _.rest(arguments));
    if (this._folderKey && this._wsi_deid_settings && this._wsi_deid_settings.show_metadata_in_lists !== false && this.collection.length) {
        this.fetchItemList();
    }
    return result;
});

wrap(ItemListWidget, 'render', function (render) {
    function updateChecked() {
        const anyChecked = this.checked.some((cid) => this._wsi_deid_item_list.byId[this.collection.get(cid).id]);
        this.parentView.$el.find('.wsi_deid-redactlist-button,.wsi_deid-finishlist-button').toggleClass('disabled', !anyChecked);
        this.parentView.updateRefileControls(anyChecked);
    }

    this.stopListening(this, 'g:checkboxesChanged', updateChecked);
    if (!this._wsi_deid_item_list) {
        return render.apply(this, _.rest(arguments));
    }

    /* Chrome limits the number of connections to a single domain, which means
     * that time-consuming requests for thumbnails can bind-up the web browser.
     * To avoid this, limit the maximum number of thumbnails that are requested
     * at a time.  At this time (2016-09-27), Chrome's limit is 6 connections;
     * to preserve some overhead, use a number a few lower than that. */
    var maxSimultaneous = 3;

    /**
     * When we might need to load another image, check how many are waiting or
     * currently being loaded, and ask an appropriate additional number to
     * load.
     *
     * @param {jquery element} parent parent under which the large_image
     *      thumbnails are located.
     */
    function _loadMoreImages(parent) {
        var loading = $('.large_image_thumbnail img.loading,.large_image_associated img.loading', parent).length;
        if (maxSimultaneous > loading) {
            $('.large_image_thumbnail img.waiting,.large_image_associated img.waiting', parent).slice(0, maxSimultaneous - loading).each(function () {
                var img = $(this);
                img.removeClass('waiting').addClass('loading');
                img.attr('src', img.attr('deferred-src'));
            });
        }
    }

    const flagRedaction = (event) => {
        const id = $(event.currentTarget).closest('[item_id]').attr('item_id');
        const entry = this._wsi_deid_item_list.byId[id];
        const result = flagRedactionOnItem(entry.item, event);
        entry._redactList = getRedactList(entry.item);
        return result;
    };

    /* Largely taken from girder/web_client/src/views/widgets/ItemListWidget.js
     */
    // If we set a selected item in the beginning we will center the selection while loading
    if (this._selectedItem && this._highlightItem) {
        this.scrollPositionObserver();
    }

    this.$el.html(ItemListTemplate({
        items: this.collection.toArray(),
        isParentPublic: this.public,
        formatSize: formatSize,
        downloadLinks: this._downloadLinks,
        viewLinks: this._viewLinks,
        showSizes: this._showSizes,
        highlightItem: this._highlightItem,
        selectedItemId: (this._selectedItem || {}).id,
        apiRoot: getApiRoot(),
        info: this._wsi_deid_item_list,
        hasRedactionControls: (this._folderKey === 'ingest' || this._folderKey === 'quarantine'),
        systemRedactedReason: systemRedactedReason,
        PHIPIITypes: this.phiPiiTypes,
        showAllVisible: false
    }));
    var parent = this.$el;
    $('.large_image_thumbnail', parent).each(function () {
        var elem = $(this);
        /* Handle images loading or failing. */
        $('img', elem).one('error', function () {
            $('img', elem).addClass('failed-to-load');
            $('img', elem).removeClass('loading waiting');
            elem.addClass('failed-to-load');
            _loadMoreImages(parent);
        });
        $('img', elem).one('load', function () {
            $('img', elem).addClass('loaded');
            $('img', elem).removeClass('loading waiting');
            _loadMoreImages(parent);
        });
    });
    _loadMoreImages(parent);
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
    this.listenTo(this, 'g:checkboxesChanged', updateChecked);
    const itemCheckboxes = this.$el.find('.g-list-checkbox');
    itemCheckboxes.each((index, checkbox) => {
        const cid = $(checkbox).attr('g-item-cid');
        if (this.checked.includes(cid)) {
            $(checkbox).attr('checked', true);
        }
    });
    this.trigger('g:checkboxesChanged');
    return this;
});

export default ItemListWidget;
