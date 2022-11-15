import os

import pooch

registry = {
    # Aperio file with JP2K compression.
    # Source: TCGA-CV-7242-11A-01-TS1.1838afb1-9eee-4a70-9ae3-50e3ab45e242.svs
    'aperio_jp2k.svs': 'sha512:9a4312bc720e81ef4496cc33c71c122b82226f72bc4944b0192cc83a93b9ed7f69612d3f4369279c2ec41183e3f684cca7e068208b7d0a42bdca26cbdc3b9aac',  # noqa
    # Hamamatsu file
    # Source: OS-2.ndpi
    'hamamatsu.ndpi': 'sha512:f788288ed1f8ab55a05d33f218fd4bafbc59e3ecc2ade40b5127b53caaaaaf3c8c9ba42d022082c27b673e1ee6dd433eb21a1d57edf4e6694dcd7eea89778941',  # noqa
    # Philips file
    # Source: sample_image.ptif
    'philips.ptif': 'sha512:ec0ec688537080e4ec2abb3978c14577df87250a2c0af42beaadc8f00f0baba210997d5d2fe7cfeeceb841885b6adad0c9f607e35eddcc479eb487bd3c1e28ac',  # noqa
    # Sample mouse tissue files to use with default schema tests
    'SEER_Mouse_1_17158539.svs': 'sha512:1ace33abb4bf96382c8823706c43deb1115b08d46bf96e2b03f425697a85e767631f0dc5568cce68c9110f1df66d264a97671fd488466f3cf59295513d6c7792', # noqa
    'SEER_Mouse_1_17158540.svs': 'sha512:74a0d97e9f8e3f42409c10be37eca9fb5d3be06f0a4f258d4b58efb5adc67f3f787a868bce6aa75649d25b221f4a0b32109bcc1ca1c696d4060981cb7d6b65f1', # noqa
    'SEER_Mouse_1_17158541.svs': 'sha512:f5fcbc5f31201ff7a28886d2b386a34fe9c0eb84cf9ce4e30601e6abe43c120ed242e23b1af555e69abab7823aef59a7220e6159b12f2cf565a2de69eb2cf1cb', # noqa
    'SEER_Mouse_1_17158542.svs': 'sha512:e763630a72b307932c64e442253fbf3c1877e7c9db77abb93864d37418fe7f94b9ace5286dff44ff0242ca1acfc58e3282b71959a864abdd925dc409452e40b7', # noqa
    'SEER_Mouse_1_17158543.svs': 'sha512:60ef06d11da310b713327adcab122e128a8a9506a68047dcff3ac5a327766e168f97ec032ba92b997b0d83e455864f8f61998c8c5f24767471b8b3c951838de1'  # noqa
}


class DKCPooch(pooch.Pooch):
    def get_url(self, fname):
        self._assert_file_in_registry(fname)
        algo, hashvalue = self.registry[fname].split(':')
        return self.base_url.format(algo=algo, hashvalue=hashvalue)


datastore = DKCPooch(
    path=pooch.utils.cache_location(
        os.path.join(os.environ.get('TOX_WORK_DIR', pooch.utils.os_cache('pooch')), 'dkc_datastore')
    ),
    base_url='https://data.kitware.com/api/v1/file/hashsum/{algo}/{hashvalue}/download',
    registry=registry,
)
