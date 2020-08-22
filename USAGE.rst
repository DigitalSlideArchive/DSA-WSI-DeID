=================================
NCI SEER Pediatic WSI Pilot Usage
=================================

See README.rst for installation.

Importing Data
==============

TODO: clean this up when the process is worked out

- Add image files and the metadata excel file to the import directory on the local filesystem
- Run the import process
- TODO: describe structure for file/folder layout and csv file, which should go into import folder for data ingest
- TODO: describe the file renaming
- The imported files will now appear in the DSA in the ``SEER`` collection, in the ``Imported`` folder


Exporting Data
==============

TODO: clean this up when the process is worked out

- When images are in the ``SEER`` collection, in the ``Finished`` folder, they can be exported
- Run the export process
- The exported files will now appear on the local filesystem in the export directory


Redaction
=========

Many of the workflow states provide controls to allow the user to indicate PHI that should be redacted, staging that PHI for processing.

The user can inspect the image and metadata for PHI, can mark individual metadata fields for redaction, and can indicate if any of the non-primary images should be redacted. When all PHI has been staged for redaction, the user can click the ``Process`` button, which will make a copy of the existing image and place that copy in the``original`` state, ond will move the image to the ``processed`` state. As part of moving the data to the ``processed`` state, the metadata fields and non-primary images marked for redaction will be deleted.

TODO: from which states do the redaction controls exist?
TODO: deleted or overwritten or changed??
TODO: better name for non-primary images?


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

For the remainder of this discussion, assume that the name of the folder corresponds to the name of the current state of the image, e.g., when an image is in the ``imported`` state it will also be in the ``imported`` folder.


Import
------

When an image is first imported into the DSA from the host filesystem, it will be renamed according to the import process and will be in the ``imported`` state.

Once an image is in the ``imported`` state, the user can click:

 - "Process" to redact it
 - "Quarantine" for more reprocessing
 - "Reject" to mark that it is impossible to fix


Processed
---------

Images in the ``processed`` state have gone through the redaction process, but should be inspected to determine if they still contain PHI or are fully cleared and ready for release.

Once an image is in the ``processed`` state, the user can click:

 - "Finish" to approve it, once it has been fully cleared for release
 - "Reject" to mark that it is impossible to fix
 - "Quarantine" for more reprocessing


Rejected
--------

The ``rejected`` state is available at any time. If an image is determined to be impossible to fix--perhaps it is too difficult to confirm that PHI has been removed, or if so much data would be removed to de-identify the image that the image data would be useless for research purposes--then the image can be sent to the ``rejected`` state by clicking on the ``rejected`` button. From the ``rejected`` state the image can always be sent to the ``quarantine`` state.

TODO: should we add a reason textbox so that users can indicate why an image was rejected?

Original
--------

An image is copied into the ``original`` state before it will be redacted and go into the ``processed`` state, so that a pre-redaction copy of the image is stored with the full provenance record of what steps the image went through up until the time of processing.


Finished
--------

When an image has been de-identified and is cleared for release, it will be in the `finished` state. Export will copy finished files to the export location using NCI's specified folder structure.

TODO: how to export?
TODO: From the ``finished`` state the user can export images by clicking on the ``export`` button, which will copy images from the ``finished`` folder in DSA to the ``export`` folder on the host filesystem.

Quarantine
----------

The ``quarantine`` state is for holding images that may hold PHI and should be inspected, and can be reached from any other state. It would generally be used if an image has been redacted already but more redaction is necessary. This state provides controls to allow the user to indicate PHI that should be redacted, staging that PHI for processing.

TODO: can images be quarantined from any state?
