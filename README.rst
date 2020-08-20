==========================================================
NCI SEER Pediatic WSI Pilot |build-status| |license-badge|
==========================================================

This builds on the Digital Slide Archive, HistomicsUI, and Girder to provide controls and workflows for redacting PHI from whole slide images (WSI).  Initially, this works with Aperio, Hamamatsu (ndpi), and Philips WSI files.

Installation
============

Prerequisites
-------------

At a minimum, you need `Docker <https://docs.docker.com/install/>`_ and `docker-compose <https://docs.docker.com/compose/install/>`_.  You also need a copy of this repository, either obtained via ``git`` or downloaded directly.  If you have ``git`` installed, this can be::

    git clone https://github.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.git

Install commands need to be run from the ``devops/nciseer`` directory.  Examples are given via a command prompt, but a desktop version of Docker will work as well.

Import and Export Paths
-----------------------

If you want to import and export data from your local filesystem into the Pilot, you'll need to set up import and export paths, by mounting specific directories for import and export of files.  This is most readily done by creating a secondary docker-compose yaml file in the ``devops/nciseer`` directory, named ``docker-compose.local.yml`` which contains::

    ---
    version: '3'
    services:
      girder:
        volumes:
          - c:\seer\import:/import
          - c:\seer\export:/export

where the first part of the last two lines are paths on the local system that should be mounted into the ``import`` and ``export`` paths of the Pilot system, i.e. ``c:\seer\import:/import`` specifies that the local filesystem directory ``c:\seer\import`` is mounted into the Pilot as the ``/import`` path.  To use these defined import and export paths, instead of typing ``docker-compose up -d``, type::

    docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d

which will extend and override the definitions in ``docker-compose.yml`` with those in ``docker-compose.local.yml``.

Initial Start
-------------

From a command prompt in the ``devops/nciseer`` directory, if you are using import and export paths, type::

    docker-compose pull
    docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d

or without the import and export paths, type::

    docker-compose pull
    docker-compose up -d


This will download some necessary files (pre-built docker images) and start the system.  The database, local files, and some logs are stored in docker volumes.

The system will be available from a web browser on http://localhost:8080.

Note: If you prefer a different locally mounted port, you can specific that via an ENV VAR ``DSA_PORT``, e.g.::

    DSA_PORT=8888 docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d

Update an Existing System
-------------------------

From a command prompt in the ``devops/nciseer`` directory, if you are using import and export paths, type::

    git pull
    docker-compose pull
    docker-compose down
    docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d

or without the import and export paths, type::

    git pull
    docker-compose pull
    docker-compose down
    docker-compose up -d


This uses ``git`` to update the repository, fetches the latest build from docker, stops the currently running version, and starts the new version.


.. |build-status| image:: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.png?style=shield
    :target: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot
    :alt: Build Status

.. |license-badge| image:: https://img.shields.io/badge/license-Apache%202-blue.svg
    :target: https://raw.githubusercontent.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot/master/LICENSE
    :alt: License


Workflow States and Transitions
===============================

There are several states an image can be in, including:

 - imported
 - quarantine
 - processed
 - rejected
 - original
 - finished

Which correspond to named folders, i.e., an image will be in the ``imported`` state at the time it lives in the ``imported`` folder, as long as users move images between states using the DSA UI tools. By using other Girder admin tools, it is possible to break the correspondence between the state and the folder name, but that should be an exceptional and unusual case.

The reason that there are named states that are separate from named folders is so that workflow provenance can be tracked. An image may currently be in the ``quarantine`` state in the ``quarantine`` folder, but the image's workflow history indicates that it had previously been in the ``imported`` state before the ``quarantine`` state.

Import
------

When an image is first brought into the system, through the usual mechanism of putting the image plus metadata into an import filesystem folder and running an import script, the image is deposited into the ``import`` folder and is in the ``import`` state.

TODO: describe structure for file/folder layout and csv file, which should go into import folder for data ingest

Quarantine
----------

The ``quarantine`` state is for holding images that may hold PHI and should be inspected. This state provides controls to allow the user to indicate PHI that should be redacted, staging that PHI for processing.

Generally a user would first quarantine an image after import, which moves the image to the ``quarantine`` folder (for the remainder of this discussion, assume that the name of the folder corresponds to the name of the state). The user should then inspect the image and metadata for PHI, can mark individual metadata fields for redaction, and can indicate if any of the non-primary images should be redacted. When all PHI has been staged for redaction, the user can click the ``Process`` button, which will move the data to the ``processed`` state and TODO:move it elsewhere also??. As part of moving the data to the ``processed`` state, the metadata fields and non-primary images marked for redaction will be deleted. TODO: deleted or overwritten or changed??

TODO: better wording than non-primary images

TODO: can images be quarantined from any state?

Processed
---------

Images in the ``processed`` state have gone through the redaction process, but should be inspected to determine if they still contain PHI or are fully cleared and ready for release. Once the images have been fully cleared for release, the ``Finish`` button should be pressed, moving the images to the ``finished`` state.

Rejected
--------

The ``rejected`` state is available at any time. If an image is determined to be too difficult to confirm that PHI has been removed, or if so much data would be removed to de-identify the image that the image data would be useless for research purposes, then the image can be sent to the ``rejected`` state by clicking on the ``rejected`` button.

TODO: should we add a reason textbox so that users can indicate why an image was rejected?

Original
--------

TODO: When does this come into play ??

Finished
--------

When an image has been de-identified and is cleared for release, it will be in the `finished` state. From the ``finished`` state the user can export images by clicking on the ``export`` button, which will copy images from the ``finished`` folder in DSA to the ``export`` folder on the host filesystem.

TODO: What happens after export? Do images get removed from the finished folder?
