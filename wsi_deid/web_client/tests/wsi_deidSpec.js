/* globals girderTest, describe, it, expect, waitsFor, runs, $ */

girderTest.importPlugin('homepage', 'jobs', 'large_image', 'large_image_annotation', 'slicer_cli_web', 'histomicsui', 'wsi_deid');

girderTest.startApp();

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

describe('Test the WSI DeID plugin', function () {
    it('change the WSI DeID settings', function () {
        girderTest.login('admin', 'Admin', 'Admin', 'password')();
        waitsFor(function () {
            return $('a.g-nav-link[g-target="admin"]').length > 0;
        }, 'admin console link to load');
        runs(function () {
            $('a.g-nav-link[g-target="admin"]').click();
        });
        waitsFor(function () {
            return $('.g-plugins-config').length > 0;
        }, 'the admin console to load');
        runs(function () {
            $('.g-plugins-config').click();
        });
        girderTest.waitForLoad();
        waitsFor(function () {
            return $('.g-plugin-config-link').length > 0;
        }, 'the plugins page to load');
        runs(function () {
            expect($('.g-plugin-config-link[g-route="plugins/wsi_deid/config"]').length > 0);
            $('.g-plugin-config-link[g-route="plugins/wsi_deid/config"]').click();
        });
        girderTest.waitForLoad();
        waitsFor(function () {
            return $('#g-wsi_deid-form input').length > 0;
        }, 'settings to be shown');
        /* test folders folder */
        runs(function () {
            $('.g-open-browser').click();
        });
        girderTest.waitForDialog();
        runs(function () {
            $('#g-root-selector').val($('#g-root-selector')[0].options[1].value).trigger('change');
        });
        waitsFor(function () {
            return $('.g-folder-list-link').length >= 2;
        });
        runs(function () {
            $('.g-folder-list-link').click();
        });
        waitsFor(function () {
            return $('#g-selected-model').val() !== '';
        });
        runs(function () {
            $('.g-submit-button').click();
        });
        girderTest.waitForLoad();
        /* Cancel the changes */
        runs(function () {
            $('.g-hui-buttons #g-hui-cancel').click();
        });
        waitsFor(function () {
            return $('.g-plugin-config-link').length > 0;
        }, 'the plugins page to load');
        girderTest.waitForLoad();
    });

    describe('test import', function () {
        it('go to WSI DeID collections page', function () {
            runs(function () {
                $("a.g-nav-link[g-target='collections']").click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            }, 'navigate to collections page');
            runs(function () {
                $('.g-collection-list-entry .g-collection-link').click();
            });
            girderTest.waitForLoad();
        });
        it('go to the AvailbleToProcess folder', function () {
            runs(function () {
                expect($('.g-folder-list-link').eq(1).text()).toEqual('AvailableToProcess');
                $('.g-folder-list-link').eq(1).click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.wsi_deid-import-button').length;
            }, 'import button to appear');
        });
        it('click the import button', function () {
            runs(function () {
                $('.wsi_deid-import-button').click();
            });
            waitsFor(function () {
                return $('.g-folder-list-link').length;
            });
            girderTest.waitForLoad();
        });
    });
    describe('test redact one', function () {
        it('click next item', function () {
            runs(function () {
                $('a.g-nav-next-unprocessed').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-hui-redact').length && $('.g-widget-redact-area-container').length;
            });
            waitsFor(function () {
                return $('.g-workflow-button[action="process"]').length;
            });
            runs(function () {
                expect($('.g-workflow-button[action="process"]').length).toBe(1);
            });
        });
        it('click redact', function () {
            runs(function () {
                $('.g-workflow-button[action="process"]').click();
            });
            girderTest.waitForLoad();
            runs(function () {
                expect($('.g-workflow-button[action="finish"]').length).toBe(1);
            });
        });
        it('click finish', function () {
            runs(function () {
                $('.g-workflow-button[action="finish"]').click();
            });
            waitsFor(function () {
                return $('.g-workflow-button[action="process"]').length;
            });
            girderTest.waitForLoad();
            runs(function () {
                expect($('.g-workflow-button[action="process"]').length).toBe(1);
            });
        });
    });
});
