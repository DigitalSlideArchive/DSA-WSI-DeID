/* globals girderTest, describe, it, expect, waitsFor, runs, $ */

girderTest.importPlugin('homepage', 'jobs', 'large_image', 'large_image_annotation', 'slicer_cli_web', 'histomicsui', 'wsi_deid')

girderTest.startApp();

var tokenId = '0590XY112001';

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
            waitsFor(function() {
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
            runs(function() {
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
        it('clicks the import button', function () {
            runs(function () {
                $('.wsi_deid-import-button').click();
            });
            waitsFor(function () {
                return $('.g-item-list-entry').length
            }, 'imported images to load as items');
            girderTest.waitForLoad();
        });
        it('expects 1 to be 1', function () {
            runs(function () {
                expect(1).toBe(1);
            });
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
                return $('.g-refile-button').length
            }, 'refile button to appear');
        });
        it('refiles the image', function () {
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
});
