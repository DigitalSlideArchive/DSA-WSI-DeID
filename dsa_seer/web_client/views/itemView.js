import { wrap } from '@girder/core/utilities/PluginUtils';
import ItemView from '@girder/core/views/body/ItemView';

wrap(ItemView, 'render', function (render) {
    this.once('g:rendered', function () {
        if (this.model.get('largeImage') && this.model.get('largeImage').fileId) {
            console.log('HERE');
            // DWM::
        }
    });
    render.call(this);
});
