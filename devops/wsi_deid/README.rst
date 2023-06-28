===========================
WSI DeID via Docker Compose
===========================

This directory contains a docker-compose set up for the WSI DeID project.

Database files and local assetstore files are persistently stored in docker volumes.  You may want to extend the docker-compose.yml file to mount external file system directories for easier import and export.

Prerequisites
-------------

Before using this, you need both Docker and docker-compose.  See the `official installation instructions <https://docs.docker.com/compose/install>`_.

Start
-----

To start the program::

    docker-compose up

Note that this does not add any sample files.  By default, it creates an ``admin`` user with a password of ``password``.  The ``WSI DeID`` collection is created with a set of standard workflow folders.

Developers
----------

See the ``docker-compose.developer.yml`` for a way to use the docker instance and change source code locally.
