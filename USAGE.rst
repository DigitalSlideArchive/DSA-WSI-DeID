==================
DSA WSI DeID Usage
==================

See README.rst for installation and debugging instructions.

This document describes how to use the DSA WSI DeID system with the major use case of de-identifying Whole Slide Images (WSIs).


Reporting Bugs
==============

If you have found a bug, open a `GitHub issue <https://github.com/DigitalSlideArchive/DSA-WSI-DeID/issues>`_ and describe the problem, the expected behavior, and your version of the software. The software version can be found on the front page of the web application and will be in the section that looks like ``WSI DeID Version: 1.1.1``. In this example the version string is ``1.1.1``, but you should expect a different version string for your WSI DeID instance.


User Management
===============

User Registration and Logins
----------------------------

When you first create an installation of the software, e.g. through ``docker-compose up``, you will need to create a user for that web application by clicking on ``Register``. After registration, you may use the user credentials you created to ``Login`` to the WSI DeID.

If you are logged into the WSI DeID, your username will appear in the upper right-hand corner of the screen, like for the user named ``test`` in the below screenshot.

.. image:: screenshots/test_user.png
   :height: 100
   :width: 200
   :alt: test user logged in
  

User Types and Permissions
--------------------------

**Admin User:** The first registered user of a WSI DeID system will be an ``admin`` user and have super-user privileges, meaning that the user can take any actions on the system. All subsequently created users will be regular, non-super-users, but will have the ability to use the redaction workflows.

**Anonymous User:** If no user is logged in, you are said to be browsing the WSI DeID as the ``anonymous`` user. The ``anonymous`` user may browse data in the WSI DeID but cannot take any actions that redact data or change the state of data. When you are browsing as the ``anonymous`` user you will see the option to ``Register or Log In`` as in the below screenshot.

.. image:: screenshots/register_or_login.png
   :height: 100
   :width: 200
   :alt: register or log in
   
   
Navigating the WSI DeID
=======================

Navigating by Folder
--------------------

From the home page, click on the ``Collections`` link on the left menu and then click on the ``WSI DeID`` collection link, which is shown in the below screenshot.

.. image:: screenshots/wsideid_collection_link.png
   :height: 100
   :width: 200
   :alt: WSI DeID collection link

After clicking on the ``WSI DeID`` collection link, you will be in the ``WSI DeID`` collection and should see the ``WSI DeID`` specific folders corresponding to workflow states described in the ``Workflow States and Transitions`` section below and as shown in the below screenshot.
  
.. image:: screenshots/wsideid_collection_folders.png
   :height: 100
   :width: 200
   :alt: WSI DeID collection folders
   
From this folder listing, you can navigate to any folder you wish by clicking on the folder name link. For example, if you want to import data, go to the ``AvailableToProcess`` folder, or if you want to export data, go to the ``Approved`` folder.

Next Item Action
----------------

Clicking on the ``Next Item`` link on the left menu will bring you to view the first image in the ``AvailableToProcess`` folder, or else the first image in the ``Quarantined`` folder if there are no images in the ``AvailableToProcess`` folder.

Folder Versus Item Views
------------------------

The WSI DeID is based on Girder, which is structured as Folders and Items. **Folders** are similar to a directory on your local computer's filesystem; whereas, **Items** are a container for one or more files, such as would be on your local computer's filesystem. For the purposes of the WSI DeID documentation, an image is an item and  may be used interchangeably. A whole slide image file may contain multiple images, such as in the case where there is a primary image and Associated Images such as a label or macro image.

A folder in Girder may contain items, and an item always has to be in a folder. When looking at the WSI DeID, if you are in a folder, you will see the folder icon on the upper right of the screen, as shown in the screenshot below taken from an ``AvailableToProcess`` folder. In this case, the folder has zero children folders and ten items within the folder, which is why there is an icon of a folder with a ``0`` and an icon of a document with a ``10`` in the screenshot.

.. image:: screenshots/image_folder_view.png
   :height: 100
   :width: 200
   :alt: image folder view
   
To see an item view of an image, click on the image/item's row in the folder view. You will then go to the item view, which looks like the below screenshot, of an item named ``01-A.svs`` that is located in the ``AvailableToProcess`` folder. In the info panel you can see some metadata such as the image size and WSI DeID creation date. The item view will present you with subsections for a panning/zooming ``Image Viewer``, a listing of ``Large Image Metadata``, the set of ``Associated Images``, and image/item specific ``WSI DeID Workflow`` actions.

.. image:: screenshots/image_item_view.png
   :height: 100
   :width: 200
   :alt: image item view

Below is a screenshot of the action buttons available in the ``WSI DeID Workflow`` section of the ``AvailableToProcess`` folder. Different folders will present different combinations of buttons, depending on the particular transitions out of that workflow state.
  
 .. image:: screenshots/wsideid_workflow_buttons.png
   :height: 100
   :width: 200
   :alt: WSI DeID workflow buttons

Importing Data
==============

The import process assumes that the system has been configured with a mounted import directory, that is, the local filesystem folder that was mounted as the import path in the docker-compose configuration.

Imported Files and Folders
--------------------------

Files are automatically copied from the local import directory to the ``AvailableToProcess`` folder in the ``WSI DeID`` collection in the WSI DeID. Files can have any folder structure; the folder structure is not significant in the import process. Excel files (identified by ending in .xls or .xlsx) and image files (anything else except for ignored files) will be imported. To facilitate bulk uploads, we ignore files ending in .txt, .xml, .zip from the import process -- this list can be easily changed.

Import Process
--------------

From the ``AvailableToProcess`` folder (or any sub folder) in the WSI DeID, click on the ``Import`` button, as shown in the below screenshot.

.. image:: screenshots/import_button.png
   :height: 100
   :width: 200
   :alt: import button

A background process starts that scans through the mounted import directory, and does the following:

- Each Excel file is parsed for a header row that has TokenID, ImageID, and ScannedFileName.
- If there are any Excel files that do not have a header row, an error is generated and appears on the screen, and files are not imported.
- If the same ScannedFileName is listed in multiple Excel files, the newest file is used by preference.
- The ScannedFileName is expected to be just the file name (e.g., no folder path).

After the image names and information in the metadata file are reconciled, the WSI DeID will classify images as one of the following:

- ``present``: The image is listed in an Excel file and is already in the WSI DeID based on file path and matching file size. No action is performed.
- ``added``: The image is listed in an Excel file and is not in the WSI DeID. It is added in the ``AvailableToProcess`` directory in a folder named TokenID with a filename ImageID.<extension>.
- ``replaced``: The image is listed in an Excel file, is in the WSI DeID, but has a different file size from the image in the WSI DeID. The existing file is removed from the WSI DeID and re-added.
- ``missing``: The image is listed in an Excel file but is not in the import directory. No action is performed.
- ``unlisted``: The image is not listed in an Excel file but is in the import directory. No action is performed.
- ``failed``: The listed file cannot be read as an image file.

After all images and Excel metadata files have been processed, a message is displayed summarizing what images were in each of the five states above (e.g., "Import complete. 19 files added. 1 file missing from import folder"), and then UI is then refreshed.

Below is a screenshot of a message presented to the user after an import.

.. image:: screenshots/import_message.png
   :height: 100
   :width: 200
   :alt: import message

Exporting Data
==============

When images are in the ``WSI DeID`` collection, in the ``Approved`` folder, they can be exported out of the DSA WSI DeID for transfer. 

In the ``Approved`` folder, two buttons appear at the top: ``Export Recent`` and ``Export All``, as shown in the screenshot below. Clicking either copies files from the ``Approved`` folder to the mounted export folder, that is, to the local filesystem folder that was mounted as the export path in the docker-compose configuration. The subfolder structure within the ``Approved`` folder is maintained as part of the export. If a file already exists in the export folder, then that file will be skipped during the export process so as to not overwrite the existing file in the export directory. 

.. image:: screenshots/export_buttons.png
   :height: 100
   :width: 200
   :alt: export buttons

Recent exports are any items in the ``Approved`` folder that have not been exported before. After each export, items are tagged with metadata indicating that they have been exported.

After export, a message is shown indicating how many files were exported, how many were already present (based on having the same file name) and the same file size, and how many were already present and differed in file size.


Redaction
=========

Many of the workflow states provide controls to allow the user to indicate PHI/PII that should be redacted, staging that PHI for processing.

The user can inspect the image and metadata for PHI/PII, can mark individual metadata fields for redaction from the ``available to process`` or ``quarantined`` state, and can indicate if any of the associated images should be redacted. When all PHI/PII has been staged for redaction, the user can click the ``Redact Image`` button, which will make a copy of the existing image and place that copy in the ``original`` state, and will move the image to the ``redacted`` state. As part of moving the data to the ``redacted`` state, the metadata fields and associated images marked for redaction will be deleted.

All of the files the WSI DeID handles currently are variants of TIFF. When a field is redacted so that it is changed, the original value in that redacted data field is completely replaced with the new value. This replacement will be done by the system automatically for certain fields including titles and dates that are specific to each scanner manufacturer upon ingest. When a field or image is redacted completely, it is removed.

Below is a screenshot of image PHI/PII redaction controls for metadata. The ``aperio.Date`` field has been pre-redacted to ``01/01/18`` and the ``aperio.Filename`` field has been pre-redacted to the ImageID name taken from the import metadata spreadsheet. The ``aperio.AppMag`` field has been staged for redaction.

.. image:: screenshots/redact_metadata.png
   :height: 100
   :width: 200
   :alt: redact metadata controls
   
Below is a screenshot of image PHI/PII redaction controls for Associated Images, with the ``Thumbnail`` image staged for redaction.

.. image:: screenshots/redact_images.png
   :height: 100
   :width: 200
   :alt: redact images controls

Label images that are redacted are replaced with a black image that contains text of the item's new name (for the purposes of the WSI Pilot this new name will be the ImageID), such as in the screenshot below.
   
.. image:: screenshots/redacted_label_image.png
   :height: 100
   :width: 200
   :alt: redacted label image
   

Example Walkthrough
===================

There are multiple paths through the system. To view the details of each state and the transitions between them see the ``Workflow States and Transitions`` section below. This section will describe one simple path through the system as an example to pull the pieces together.

Start out by saving images and the DeID Upload File (an Excel file) in the import directory on the local filesystem, then run the ``Import`` command in the WSI DeID, from the ``AvailableToProcess`` folder in the ``WSI DeID`` collection. The images will now appear in the ``AvailableToProcess`` folder in the WSI DeID.

Click on an individual image (an item view of the image) to view the redaction controls. Click on the ``Redact`` controls for any pieces of textual metadata and any of the associated images that should be redacted. Then click the ``Redact Image`` button at the bottom of the page.

At this point, a copy of the original image without any redaction will appear in the ``Original`` folder, so that a pre-redaction record is kept. The redacted image will be moved to the ``Redacted`` folder, and any pieces of metadata that were redacted will now be deleted. Any associated images that were redacted will also be deleted.

Click on the ``Approve`` button at the bottom of the page, and the image will be moved to the ``Approved`` folder. Click on the folder view of the ``Approved`` folder, and then click ``Export Recent`` to export this redacted image, which will then be copied to the export directory on the local filesystem.


Workflow States and Transitions
===============================

There are six states an image file can be in within the DSA WSI DeID Tool, including:

- available to process
- quarantined
- redacted
- rejected
- original
- approved

The workflow states and transitions are depicted in the overall workflow diagram below.

.. image:: screenshots/workflow_diagram.png
   :height: 100
   :width: 200
   :alt: workflow diagram

These states correspond to named folders, i.e., an image will be in the ``available to process`` state at the time it lives in the ``AvailableToProcess`` folder, as long as users move images between states using the WSI DeID UI tools. By using other Girder admin tools, it is possible to break the correspondence between the state and the folder name, but that should be an exceptional and unusual case.

The reason that there are named states that are separate from named folders is so that workflow provenance can be tracked. An image may currently be in the ``quarantined`` state in the ``Quarantined`` folder, but the image's workflow history indicates that it had previously been in the ``available to process`` state before the ``quarantined`` state.

For the remainder of this discussion, assume that the name of the folder corresponds to the name of the current state of the image, e.g., when an image is in the ``available to process`` state it will also be in the ``AvailableToProcess`` folder.


Available To Process
--------------------

When an image is first imported into the WSI DeID from the host filesystem, it will be renamed according to the import process and will be in the ``available to process`` state.

Once an image is in the ``available to process`` state, the user can click:

- "Redact Image" to redact it
- "Quarantine" for more reprocessing
- "Reject" to mark that it is impossible to fix


Redacted
--------

Images in the ``redacted`` state have gone through the redaction process, but should be inspected to determine if they still contain PHI/PII or are fully cleared and ready for release.

Once an image is in the ``redacted`` state, the user can click:

- "Approve" to approve it, once it has been fully cleared for release. If this is pressed, then the image will move to the ``Approved`` folder and then the view will change to the next image to be processed, as if you had clicked on the ``Next Item`` action in the left menu. 
- "Reject" to mark that it is impossible to fix
- "Quarantine" for more reprocessing


Rejected
--------

The ``rejected`` state is available at any time. If an image is determined to be impossible to fix--perhaps it is too difficult to confirm that PHI has been removed, or if so much data would be removed to de-identify the image that the image data would be useless for research purposes--then the image can be sent to the ``rejected`` state by clicking on the ``rejected`` button. From the ``rejected`` state the image can always be sent to the ``quarantined`` state.


Original
--------

An image is copied into the ``original`` state before it will be redacted and will go into the ``redacted`` state, so that a pre-redaction copy of the image is stored with the full provenance record of what steps the image went through up until the time of processing.


Approved
--------

When an image has been de-identified and is cleared for release, it will be in the ``approved`` state. The export process will copy approved files to the export location using NCI's specified folder structure.

In the ``Approved`` folder, two buttons appear at the top: ``Export Recent`` and ``Export All``, that will allow the user to export images. See the ``Exporting Data`` section above for details.

Quarantined
-----------

The ``quarantined`` state can be reached from any other state and is for holding images that may hold PHI/PII. Files in the quarantined folder should be inspected and potentially reprocessed. It would generally be used if additional redaction is necessary for a file that has been redacted. This state provides controls to allow the user to mark the PHI/PII that should be redacted, staging that PHI/PII for processing.

Images can be quarantined from any state.  If PHI/PII is seen in an image or metadata field, that is somewhere other than the ``AvailableToProcess`` folder, it should be quarantined for reprocessing.

