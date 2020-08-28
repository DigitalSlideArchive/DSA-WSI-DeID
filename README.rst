==========================================================
NCI SEER Pediatic WSI Pilot |build-status| |license-badge|
==========================================================

This builds on the Digital Slide Archive, HistomicsUI, and Girder to provide controls and workflows for redacting PHI from whole slide images (WSI).  Initially, this works with Aperio, Hamamatsu (ndpi), and Philips WSI files.

Developed by Kitware, Inc. with funding from The National Cancer Institute.

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

Debugging
---------

You can access logs of specific docker containers via::

    docker-compose logs

There are more detailed logs for the main container that can be viewed via::

    docker-compose exec girder cat /logs/info.log

You can follow the logs and see them update as they change::

    docker-compose logs -f
    docker-compose exec girder tail -F /logs/info.log
    
Fixing Common Problems
----------------------

If you accidentally delete one of the ``SEER`` collection folders, simply restart the system with::

    docker-compose down
    docker-compose up
    
substituting whichever specific ``docker-compose up`` variant you normally use to run the system. This system restart will automatically recreate any of the ``SEER`` collection folders that are tied to specific workflow states.


.. |build-status| image:: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.png?style=shield
    :target: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot
    :alt: Build Status

.. |license-badge| image:: https://img.shields.io/badge/license-Apache%202-blue.svg
    :target: https://raw.githubusercontent.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot/master/LICENSE
    :alt: License


Usage
=====

See USAGE.rst for usage information.
