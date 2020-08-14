from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

setup(
    author='Kitware, Inc.',
    author_email='kitware@kitware.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    description='NCI SEER Pediatric WSI Pilot plugin.',
    install_requires=[
        'histomicsui',
        'large_image[tiff,openslide,memcached]',
    ],
    license='Apache Software License 2.0',
    long_description=readme,
    long_description_content_type='text/x-rst',
    include_package_data=True,
    keywords='girder-plugin, nci_seer',
    name='nci_seer',
    packages=find_packages(exclude=['test', 'test.*']),
    url='https://github.com/DigitalSlideArchive',
    version='0.1.0',
    zip_safe=False,
    entry_points={
        'girder.plugin': [
            'nci_seer = nci_seer:GirderPlugin'
        ]
    }
)
