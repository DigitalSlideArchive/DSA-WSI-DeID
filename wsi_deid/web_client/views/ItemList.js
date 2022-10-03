import $ from 'jquery';
import _ from 'underscore';

import events from '@girder/core/events';
import { getApiRoot, restRequest } from '@girder/core/rest';
import { wrap } from '@girder/core/utilities/PluginUtils';
import { formatSize } from '@girder/core/misc';
import ItemListWidget from '@girder/large_image/views/itemList';

import {
    formats, flagRedactionOnItem, getRedactList, getRedactionDisabledPatterns,
    getHiddenMetadataPatterns, matchFieldPattern, systemRedactedReason,
    PHIPIITypes
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
        if (meta.xml && Object.keys(meta.xml).some((key) => key.startsWith('PIM_DP_'))) {
            return formats.philips;
        }
        return formats.none;
    };

    this.fetchItemList = () => {
        this._wsi_deid_item_list = undefined;
        const items = this.collection.toArray();
        // const parent = this.$el;
        const hasAnyLargeImage = _.some(items, (item) => item.has('largeImage'));
        if (!hasAnyLargeImage) {
            return;
        }
        const folder = this.parentView.parentModel;
        restRequest({
            url: `wsi_deid/folder/${folder.id}/item_list`,
            data: {
                limit: 0,
                images: JSON.stringify(this.collection.map((i) => i.id))
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
                    if (matchFieldPattern(keyname, hideFieldPatterns, undefined, value)) {
                        return;
                    }
                    i._metadict[keyname] = value;
                    if (matchFieldPattern(keyname, disableRedactionPatterns, undefined, value) || ['internal;tilesource'].indexOf(keyname) >= 0) {
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
                if (this._folderKey === 'unfiled') {
                    restRequest({
                        url: `wsi_deid/folder/${folder.id}/refileList`
                    }).done((refileList) => {
                        this._refileList = refileList;
                        if (this.collection.length) {
                            this.fetchItemList();
                        }
                    });
                }
            });
        }
    });
    return result;
});

wrap(ItemListWidget, 'bindOnChanged', function (bindOnChanged) {
    this._wsi_deid_item_list = undefined;
    const result = bindOnChanged.apply(this, _.rest(arguments));
    if (this._folderKey && this._wsi_deid_settings && this._wsi_deid_settings.show_metadata_in_lists !== false && this.collection.length) {
        this.fetchItemList();
    }
    return result;
});

wrap(ItemListWidget, 'render', function (render) {
    function updateChecked() {
        const anyChecked = this.checked.some((cid) => this._wsi_deid_item_list.byId[this.collection.get(cid).id]);
        this.parentView.$el.find('.wsi_deid-redactlist-button,.wsi_deid-finishlist-button,.wsi_deid-refile-button').toggleClass('disabled', !anyChecked);
        $('.wsi_deid-bulk-refile').toggleClass('no-disp', !anyChecked);
        updateRefileControls();
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

    const generateStringFromPattern = (pattern) => {
        const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const randomLetter = () => letters.charAt(Math.floor(Math.random() * letters.length));
        const randomNumber = () => Math.floor(Math.random() * 10);
        const result = pattern.split('');
        result.forEach((char, index) => {
            let newChar = char;
            if (char === '#') {
                newChar = randomNumber();
            } else if (char === '@') {
                newChar = randomLetter();
            }
            result[index] = newChar;
        });
        return result.join('');
    };

    const refileCheckedItems = () => {
        const togetherSelect = $('.g-refile-select-togetherness');
        const newOrExistingSelect = $('.g-refile-select-new-or-existing');
        const fileTogether = togetherSelect.find(':selected').val() === 'together';
        const useExistingToken = newOrExistingSelect.find(':selected').val() === 'existing';
        const tokenPattern = this._wsi_deid_settings['new_token_pattern'];
        const checkedImages = this.checked.map((cid) => this._wsi_deid_item_list.byId[this.collection.get(cid).id]);
        const checkedItemIds = checkedImages.map((image) => image.item._id);
        const existingTokens = JSON.parse(JSON.stringify(this._refileList));
        if (!checkedItemIds.length) {
            return;
        }
        $('body').append(
            '<div class="g-hui-loading-overlay"><div>' +
            '<i class="icon-spin4 animate-spin"><i>' +
            '</div></div>'
        );
        const imageRefileData = {};
        if (fileTogether) {
            let newToken;
            if (useExistingToken) {
                const existingTokenSelect = $('.g-refile-select-existing');
                newToken = existingTokenSelect.find(':selected').val();
            } else {
                do {
                    newToken = generateStringFromPattern(tokenPattern);
                } while (existingTokens.includes(newToken));
            }
            _.forEach(checkedItemIds, (id) => {
                imageRefileData[id] = {
                    tokenId: newToken,
                    imageId: ''
                };
            });
        } else {
            _.forEach(checkedItemIds, (id) => {
                let newToken;
                do {
                    newToken = generateStringFromPattern(tokenPattern);
                } while (existingTokens.includes(newToken));
                existingTokens.push(newToken);
                imageRefileData[id] = {
                    tokenId: newToken,
                    imageId: ''
                };
            });
        }
        restRequest({
            method: 'PUT',
            url: 'wsi_deid/action/bulkRefile',
            data: JSON.stringify(imageRefileData),
            contentType: 'application/json'
        }).done((resp) => {
            $('.g-hui-loading-overlay').remove();
            events.trigger('g:alert', {
                icon: 'ok',
                text: 'Successfully refiled image(s)',
                type: 'success',
                timeout: 5000
            });
            this.parentView.parentModel.increment('nItems', -1 * Object.keys(imageRefileData).length);
            this.parentView.setCurrentModel(this.parentView.parentModel, { setRout: false });
        });
    };

    const updateRefileControls = () => {
        const together = $('.g-refile-select-togetherness').find(':selected').val() === 'together';
        const existing = $('.g-refile-select-new-or-existing').find(':selected').val() === 'existing';
        const existingOption = $('.g-refile-options-existing');
        const tokenSelect = $('.g-refile-select-existing');
        if (existing) {
            if (together) {
                tokenSelect.removeClass('no-disp');
            } else {
                tokenSelect.addClass('no-disp');
                $('.g-refile-select-new-or-existing').val('new_token');
            }
        } else {
            tokenSelect.addClass('no-disp');
        }
        if (together && this._refileList.length) {
            existingOption.prop('disabled', false);
        } else {
            existingOption.prop('disabled', true);
        }
    };

    /* Largely taken from girder/web_client/src/views/widgets/ItemListWidget.js
     */
    this.checked = [];
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
        hasRefileControls: this._folderKey === 'unfiled',
        refileList: this._refileList,
        systemRedactedReason: systemRedactedReason,
        PHIPIITypes: PHIPIITypes,
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
    this.events['change .g-refile-select-togetherness'] = updateRefileControls;
    this.events['change .g-refile-select-new-or-existing'] = updateRefileControls;
    this.events['click .g-refile-button'] = refileCheckedItems;
    this.delegateEvents();
    this.listenTo(this, 'g:checkboxesChanged', updateChecked);
    return this;
});

export default ItemListWidget;
