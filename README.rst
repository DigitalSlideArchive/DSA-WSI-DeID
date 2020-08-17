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

TODO


.. |build-status| image:: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot.png?style=shield
    :target: https://circleci.com/gh/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot
    :alt: Build Status

.. |license-badge| image:: https://img.shields.io/badge/license-Apache%202-blue.svg
    :target: https://raw.githubusercontent.com/DigitalSlideArchive/NCI-SEER-Pediatric-WSI-Pilot/master/LICENSE
    :alt: License

