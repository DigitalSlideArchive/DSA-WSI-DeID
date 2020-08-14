===========================
NCI SEER Pediatic WSI Pilot
===========================

This builds on the Digital Slide Archive, HistomicsUI, and Girder to provide controls and workflows for redacting PHI from whole slide images (WSI).  Initially, this works with Aperio, Hamamatsu (ndpi), and Philips WSI files.

Installation
============

Prerequisites
-------------

At a minimum, you need `Docker <https://docs.docker.com/install/>`_ and `docker-compose <https://docs.docker.com/compose/install/>`_.  You also need a copy of this repository, either obtained via ``git`` or downloaded directly.

Install commands need to be run from the ``devops/nciseer`` directory.  Examples are given via a command prompt, but a desktop version of Docker will work as well.

Initial Start
-------------

From a command prompt in the ``devops/nciseer`` directory, type::

    docker-compose up -d

This will download some necessary files and start the system.  The database, local files, and some logs are stored in docker volumes.

The system will be available from a web browser on `http://localhost:8080`_.

Update a Running System
-----------------------

From a command prompt in the ``devops/nciseer`` directory, type::

    docker-compose pull
    docker-compose down
    docker-compose up -d

Import and Export Paths
-----------------------

TODO

