/* globals girder, girderTest, describe, it, expect, waitsFor, runs, $ */

girderTest.importPlugin('homepage', 'jobs', 'large_image', 'large_image_annotation', 'slicer_cli_web', 'histomicsui', 'wsi_deid');

girderTest.startApp();

var tokenId = '0590XY112001';
var usedTokenIds = [tokenId];

describe('Mock WebGL', function () {
    it('mock Webgl', function () {
        var girder = window.girder;
        var GeojsViewer = girder.plugins.large_image.views.imageViewerWidget.geojs;
        girder.utilities.PluginUtils.wrap(GeojsViewer, 'initialize', function (initialize) {
            this.once('g:beforeFirstRender', function () {
                window.geo.util.restoreWebglRenderer();
                window.geo.util.mockWebglRenderer();
            });
            initialize.apply(this, arguments);
        });
    });
});

describe('Test WSI DeID plugin with default schema', function () {
    describe('import', function () {
        it('logs in as admin', function () {
            girderTest.login('admin', 'Admin', 'Admin', 'password')();
            waitsFor(function () {
                return $('a.g-nav-link[g-target="admin"]').length > 0;
            }, 'admin console link to load');
        });
        it('goes to the WSI DeID collections page', function () {
            runs(function () {
                $('a.g-nav-link[g-target="collections"]').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            });
            runs(function () {
                $('.g-collection-list-entry .g-collection-link').click();
            });
            girderTest.waitForLoad();
        });
        it('goes to the unfiled folder', function () {
            runs(function () {
                expect($('.g-folder-list-link').eq(8).text()).toEqual('Unfiled');
                $('.g-folder-list-link').eq(8).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.wsi_deid-import-button').length;
            }, 'import button to appear');
            waitsFor(function () {
                return $('.g-upload-here-button').first().css('display') === 'none';
            }, 'upload button to disappear');
        });
        it('clicks the import button', function () {
            runs(function () {
                $('.wsi_deid-import-button').click();
            });
            waitsFor(function () {
                return $('.g-item-list-entry').length;
            }, 'imported images to load as items');
            girderTest.waitForLoad();
        });
    });
    describe('refile one image', function () {
        it('checks length of items', function () {
            expect($('.g-item-list-entry').length).toEqual(5);
        });
        it('opens the first item', function () {
            runs(function () {
                $('.g-item-list-link').eq(0).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-refile-button').length;
            }, 'refile button to appear');
            waitsFor(function () {
                return $('.g-matching-button').length;
            }, 'Database lookup button to appear');
        });
        it('clicks the lookup button to open the dialog', function () {
            runs(function () {
                $('.g-matching-button').eq(0).click();
            });
            girderTest.waitForDialog();
            runs(function () {
                expect($('h3.modal-title').text()).toBe('Database Lookup');
            });
            expect($('.token-label-id').length).toEqual(0);
        });
        it('makes an API call', function () {
            runs(function () {
                $('.h-lookup').eq(0).click();
            });
            waitsFor(function () {
                return $('.token-id-label').length;
            }, 'The results table to appear');
        });
        it('closes the lookup dialog', function () {
            $('#g-dialog-container').girderModal('close');
            waitsFor(function () {
                return $('body.modal-open').length === 0;
            }, 'The lookup dialog to be closed');
        });
        it('refiles the image manually', function () {
            runs(function () {
                var tokenInput = $('input.g-refile-tokenid').first();
                tokenInput.val(tokenId);
            });
            runs(function () {
                expect($('input.g-refile-tokenid').first().val()).toEqual(tokenId);
            });
            runs(function () {
                $('.g-refile-button').first().click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-hui-redact').length;
            });
            waitsFor(function () {
                return $('.g-workflow-button[action="process"]').length;
            }, 'redaction controls to become available');
            runs(function () {
                expect($('.g-workflow-button[action="process"]').length).toBe(1);
            });
        });
    });
    describe('refile multiple images together under new TokenID', function () {
        it('goes to the WSI DeID collections page', function () {
            runs(function () {
                $('a.g-nav-link[g-target="collections"]').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            });
            runs(function () {
                $('.g-collection-list-entry .g-collection-link').click();
            });
            girderTest.waitForLoad();
        });
        it('goes to the unfiled folder', function () {
            runs(function () {
                expect($('.g-folder-list-link').eq(8).text()).toEqual('Unfiled');
                $('.g-folder-list-link').eq(8).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.wsi_deid-import-button').length;
            }, 'import button to appear');
        });
        it('selects multiple images for refile', function () {
            runs(function () {
                var checkboxes = $('input.g-list-checkbox');
                checkboxes.eq(0).click();
                checkboxes.eq(1).click();
                waitsFor(function () {
                    return $('.g-refile-button').length;
                }, 'refile button to appear');
            });
        });
        it('refiles the images', function () {
            runs(function () {
                $('.g-refile-button').first().click();
            });
            girderTest.waitForLoad();
            runs(function () {
                expect($('.g-item-list-entry').length).toEqual(2);
            });
        });
        it('goes to the WSI DeID collections page', function () {
            runs(function () {
                $('a.g-nav-link[g-target="collections"]').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            });
            runs(function () {
                $('.g-collection-list-entry .g-collection-link').click();
            });
            girderTest.waitForLoad();
        });
        it('verifies a new folder in AvailableToProcess', function () {
            runs(function () {
                expect($('.g-folder-list-link').eq(1).text()).toEqual('AvailableToProcess');
                $('.g-folder-list-link').eq(1).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.wsi_deid-import-button').length;
            }, 'import button to appear');
            runs(function () {
                expect($('.g-folder-list-link').length).toEqual(2);
            });
        });
        it('verifies 2 images in new folder', function () {
            runs(function () {
                var newFolder = $('.g-folder-list-link').filter(function () {
                    return $(this).text() !== tokenId;
                }).first();
                usedTokenIds.push(newFolder.text());
                newFolder.click();
            });
            girderTest.waitForLoad();
            runs(function () {
                expect($('.g-item-list-entry').length).toEqual(2);
            });
        });
    });
    describe('refile multiple images separately under new TokenIDs', function () {
        it('goes to the WSI DeID collections page', function () {
            runs(function () {
                $('a.g-nav-link[g-target="collections"]').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            });
            runs(function () {
                $('.g-collection-list-entry .g-collection-link').click();
            });
            girderTest.waitForLoad();
        });
        it('goes to the unfiled folder', function () {
            runs(function () {
                expect($('.g-folder-list-link').eq(8).text()).toEqual('Unfiled');
                $('.g-folder-list-link').eq(8).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.wsi_deid-import-button').length;
            }, 'import button to appear');
        });
        it('selects multiple images for refile', function () {
            runs(function () {
                var checkboxes = $('input.g-list-checkbox');
                checkboxes.eq(0).click();
                checkboxes.eq(1).click();
                waitsFor(function () {
                    return $('.g-refile-button').length;
                }, 'refile button to appear');
            });
        });
        it('refiles the images separately', function () {
            runs(function () {
                var togetherSelect = $('.g-refile-select-togetherness').first();
                togetherSelect.val('separately');
                $('.g-refile-button').first().click();
            });
            girderTest.waitForLoad();
            runs(function () {
                expect($('.g-item-list-entry').length).toEqual(0);
            });
        });
        it('goes to the WSI DeID collections page', function () {
            runs(function () {
                $('a.g-nav-link[g-target="collections"]').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            });
            runs(function () {
                $('.g-collection-list-entry .g-collection-link').click();
            });
            girderTest.waitForLoad();
        });
        it('verifies two new folders in AvailableToProcess', function () {
            runs(function () {
                expect($('.g-folder-list-link').eq(1).text()).toEqual('AvailableToProcess');
                $('.g-folder-list-link').eq(1).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.wsi_deid-import-button').length;
            }, 'import button to appear');
            runs(function () {
                expect($('.g-folder-list-link').length).toEqual(4);
            });
        });
        it('verifies one image in each of the new folders', function () {
            var newFolders;
            runs(function () {
                newFolders = $('.g-folder-list-link').filter(function () {
                    return !usedTokenIds.includes($(this).text());
                });
                expect(newFolders.length).toEqual(2);
                var imageCount = new Array(newFolders.length).fill(0);
                newFolders.each(function (index, folder) {
                    var folderId = $(folder).attr('href').split('/')[1];
                    girder.rest.restRequest({
                        url: 'item?folderId=' + folderId
                    }).done(function (response) {
                        imageCount[index] = response.length;
                    });
                    waitsFor(function () {
                        return imageCount.length === imageCount.filter(function (val) {
                            return val === 1;
                        }).length;
                    });
                });
            });
        });
    });
});
