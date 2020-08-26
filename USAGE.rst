=================================
NCI SEER Pediatic WSI Pilot Usage
=================================

See README.rst for installation.

Importing Data
==============

TODO Post-Beta: clean this up when the process is worked out

- Add image files and the metadata excel file to the import directory on the local filesystem
- Run the import process
- TODO Post-Beta: describe structure for file/folder layout and csv file, which should go into import folder for data ingest
- TODO Post-Beta: describe the file renaming
- The imported files will now appear in the DSA in the ``SEER`` collection, in the ``Imported`` folder


Exporting Data
==============

When images are in the ``SEER`` collection, in the ``Finished`` folder, they can be exported. 

In the Finished folder, two buttons appear at the top: ``Export Recent`` and ``Export All``. Clicking either copies files from the ``Finished`` folder to the mounted export folder, that is, to the local filesystem folder that was mounted as the export path in the docker-compose configuration. The subfolder structure within the ``Finished`` folder is maintained as part of the export. If a file already exists in the export folder, then that file will be skipped during the export process so as to not overwrite the existing file in the export directory. 

Recent exports are any items in the Finished folder that have not been exported before. After each export, items are tagged with metadata indicating that they have been exported.

After export, a message is shown indicating how many files were exported, how many were already present (based on having the same name) and the same size, and how many were already present and differed in size.


Redaction
=========

Many of the workflow states provide controls to allow the user to indicate PHI that should be redacted, staging that PHI for processing.

The user can inspect the image and metadata for PHI, can mark individual metadata fields for redaction from the ``imported`` or ``quarantine`` state, and can indicate if any of the non-primary images should be redacted. When all PHI has been staged for redaction, the user can click the ``Process`` button, which will make a copy of the existing image and place that copy in the ``original`` state, and will move the image to the ``processed`` state. As part of moving the data to the ``processed`` state, the metadata fields and associated images marked for redaction will be deleted.

All of the files the DSA handles currently are variants of TIFF. When a field is redacted in such a way as to change it (e.g., titles and dates), the original value is completely replaced with the new value. When a field or image is redacted completely (any other field other than titles and dates), it is removed. Label images that are redacted are replaced with a black image that contains text of the item's new name (this will be the ImageID).


Workflow States and Transitions
===============================

There are several states an image can be in, including:

- imported
- quarantine
- processed
- rejected
- original
- finished

These states correspond to named folders, i.e., an image will be in the ``imported`` state at the time it lives in the ``imported`` folder, as long as users move images between states using the DSA UI tools. By using other Girder admin tools, it is possible to break the correspondence between the state and the folder name, but that should be an exceptional and unusual case.

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


Original
--------

An image is copied into the ``original`` state before it will be redacted and go into the ``processed`` state, so that a pre-redaction copy of the image is stored with the full provenance record of what steps the image went through up until the time of processing.


Finished
--------

When an image has been de-identified and is cleared for release, it will be in the `finished` state. Export will copy finished files to the export location using NCI's specified folder structure.

TODO Post-Beta: (implement this and clarify how it works in these docs) From the ``finished`` state the user can export images by clicking on the ``export`` button, which will copy images from the ``finished`` folder in DSA to the ``export`` folder on the host filesystem.

Quarantine
----------

The ``quarantine`` state can be reached from any other state, and is for holding images that may hold PHI and thus should be inspected and potentially reprocessed. It would generally be used if an image has been redacted already but more redaction is necessary. This state provides controls to allow the user to mark the PHI that should be redacted, staging that PHI for processing.

Images be quarantined from any state.  If PHI or potential PHI is seen in an item that is somewhere other than the ``imported`` folder, it should be quarantined for reprocessing.
