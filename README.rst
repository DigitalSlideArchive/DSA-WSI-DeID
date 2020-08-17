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

Initial Start
-------------

From a command prompt in the ``devops/nciseer`` directory, type::

    docker-compose pull
    docker-compose up -d

This will download some necessary files and start the system.  The database, local files, and some logs are stored in docker volumes.

The system will be available from a web browser on http://localhost:8080.

Update an Existing System
-------------------------

From a command prompt in the ``devops/nciseer`` directory, type::

    git pull
    docker-compose pull
    docker-compose down
    docker-compose up -d

This uses ``git`` to update the repository, fetches the latest build from docker, stops the currently running version, and starts the new version.

Import and Export Paths
-----------------------

It is useful to mount specific directories for import (ingest) and export of files.  This is most readily done by creating a secondary docker-compose yaml file in the ``devops/nciseer`` directory.  For instance, create a file called ``docker-compose.local.yml`` which contains::

    ---
    version: '3'
    services:
      girder:
        volumes:
          - c:\seer\ingest:/import
          - c:\seer\export:/export

where the first part of the last two lines are paths on the local system that should be mounted.  To use this file, instead of doing ``docker-compose up -d``, type::

    docker-compose -f docker-compose.yml -f docker-composer.local.yml up -d


.. |build-status| image:: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.png?style=shield
    :target: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot
    :alt: Build Status

.. |license-badge| image:: https://img.shields.io/badge/license-Apache%202-blue.svg
    :target: https://raw.githubusercontent.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot/master/LICENSE
    :alt: License

