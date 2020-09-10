/* globals girderTest, describe, it, expect, waitsFor, runs, $ */

girderTest.importPlugin('homepage', 'jobs', 'worker', 'large_image', 'large_image_annotation', 'slicer_cli_web', 'histomicsui', 'nci_seer');

girderTest.startApp();

describe('Test the NCI SEER plugin', function () {
    it('change the NCI SEER settings', function () {
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
            expect($('.g-plugin-config-link[g-route="plugins/nci_seer/config"]').length > 0);
            $('.g-plugin-config-link[g-route="plugins/nci_seer/config"]').click();
        });
        girderTest.waitForLoad();
        waitsFor(function () {
            return $('#g-nciseer-form input').length > 0;
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
});
