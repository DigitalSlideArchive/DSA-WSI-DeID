=======================================
WSI DeID |build-status| |license-badge|
=======================================

This tool builds on the Digital Slide Archive, HistomicsUI, and Girder to provide controls and workflows for redacting PHI/PII from whole slide images (WSI).  Initially, this works with Aperio, Hamamatsu (ndpi), Philips WSI, some OME TIFF, and some DICOM files.  It can work with Philips iSyntax files if provided with the appropriate SDK.

Developed by Kitware, Inc. with funding from The National Cancer Institute of the National Institutes of Health.

.. |build-status| image:: https://circleci.com/gh/DigitalSlideArchive/DSA-WSI-DeID.png?style=shield
    :target: https://circleci.com/gh/DigitalSlideArchive/DSA-WSI-DeID
    :alt: Build Status

.. |license-badge| image:: https://img.shields.io/badge/license-Apache%202-blue.svg
    :target: https://raw.githubusercontent.com/DigitalSlideArchive/DSA-WSI-DeID/master/LICENSE
    :alt: License

Browser Support
===============

WSI DeID works best using a recent version of the Chrome or Firefox browser.

Navigating the Documentation
============================


* `docs/INSTALL.rst <docs/INSTALL.rst>`_ contains system installation and administration information, mostly focused on running terminal commands.
* `docs/GIRDER.rst <docs/GIRDER.rst>`_ contains reference information on the Girder platform, which is the basis for the WSI DeID.
* `docs/USAGE.rst <docs/USAGE.rst>`_ contains usage information, mostly focused on interacting with the system through a web browser.
* `docs/GLOSSARY.rst <docs/GLOSSARY.rst>`_ contains a glossary of technical terms.
* `docs/ERROR-TABLES.rst <docs/ERROR-TABLES.rst>`_ contains tables of explanations for error messages that users may encounter.
* `docs/CUSTOMIZING.rst <docs/CUSTOMIZING.rst>`_ contains details on customizing the workflow for different use cases.
* `docs/TASKS.rst <docs/TASKS.rst>`_ contains an alternative deployment to allow running external tasks, such as a slide selection algorithm.
* `docs/APIUSAGE.rst <docs/APIUSAGE.rst>`_ describes how to make API called for perform common workflow actions.
* `docs/rationale.md <docs/rationale.md>`_ contains a rationale of the SEER WSI DeID pilot project.
