Customizing WSI DeID
====================

There are several ways to customize the installation of WSI DeID to change its behavior to better match your desired workflow and use case.

See the files ``devops/wsi_deid/docker-compose.example.local.yml`` and ``devops/wsi_deid/girder.local.conf`` for comments about many of these options.  Broadly, the options in ``devops/wsi_deid/docker-compose.example.local.yml`` change the deployment environment, such as directories that are used and available memory.  The options in ``devops/wsi_deid/girder.local.conf`` change the run-time behavior, such as how label and macro images are redacted.

When modifying ``devops/wsi_deid/girder.local.conf``, you'll also need to enable using the custom file by uncommenting a few lines as described in ``devops/wsi_deid/docker-compose.example.local.yml``.

Settings in girder.local.conf
-----------------------------

The WSI DeID specific settings are in a section headed by ``[wsi_deid]``.

Redacting the top/left of the macro image
+++++++++++++++++++++++++++++++++++++++++

When the ``redact_macro_square`` setting is set to ``True``, the upper left square of all macro images will automatically be blacked out.  This region often contains the label on the slide, and sometimes that can contain PHI that is visible with contrast or other image adjustment.

Redaction Categories
++++++++++++++++++++

By default, when metadata or images are redacted, the user must pick the type of PHI/PII that is present and the reason for the redaction.  If the ``require_redact_category`` is set to ``False``, then, instead of requiring a reason, the user interface will show a ``REDACT`` button that toggles redaction on and off for the metadata or image.  The export file will contain ``No Reason Collected`` in these cases.

Redaction categories can be configured by changing the ``phi_pii_types`` settings.

Reasons for Rejection
+++++++++++++++++++++

Rejecting images can be configured to require a reason for rejection. This is controlled by the setting ``require_reject_reason``. Reasons for rejection can be configured via the ``reject_reasons`` setting.

Redacting the Label Image
+++++++++++++++++++++++++

The label image can be redacted by default if the ``always_redact_label`` value is set to ``True``.  If the label image is redacted, it is replaced with a black square with the output filename printed in it.  The label image is not redacted, the output filename is added to the top of the image.

Label Image Title
+++++++++++++++++

Adding the filename as the title of the label image is option.  If the ``add_title_to_label`` is set to ``False``, it will not be added.  If no title is added and the label image is redacted, the image is removed.

Disabling the Redaction Control
+++++++++++++++++++++++++++++++

Redaction can be disabled for certain metadata fields. This can be used for fields that are helpful to users reviewing images, but will never contain actual PHI/PII. This can be configured on a per-format basis. The following settings control this functionality.

* ``no_redact_control_keys``
* ``no_redact_control_keys_format_aperio``
* ``no_redact_control_keys_format_hamamatsu``
* ``no_redact_control_keys_format_philips``

In order to disable redaction controls for certain metadata fields, you can add ``key: value`` pairs to the dictionaries in ``girder.local.conf``. Both the key and value need to be regular expressions. The ``key`` is a regular expression that will match your target metadata. The associated ``value`` should be a regular expression that matches the expected metadata value. For example, if your metadata should always contain an integer value, you could use the regular expression ``"\\d+"``. If you view an image and the metadata value does not match the expected expression, then redaction will be available for that metadata item.

Note that fields specified in ``no_redact_control_keys`` will have redaction disabled on all image formats. If you wish to disable redaction of a metadata field on, for example, Aperio images only, you can add that metadata key and expected value to the ``no_redact_control_keys_format_aperio`` dictionary.

Hiding Metadata Fields
++++++++++++++++++++++

Similar to configuration for disabling redaction, if you wish to hide certain metadata fields because they will never contain PHI/PII and are not useful to reviewers, you can specify those metadata fields and their expected values, as regular expressions, in the following dictionaries in ``girder.local.conf``:

* ``hide_metadata_keys``
* ``hide_metadata_keys_format_aperio``
* ``hide_metadata_keys_format_hamamatsu``
* ``hide_metadata_keys_format_philips``

If these metadata items contain unexpected values (e.g., text where a number was expected), they will be visible and available for redaction.

Editing Metadata Values
+++++++++++++++++++++++

Normally, when a metadata field is redacted, its value becomes blank. In ``girder.local.conf``, you can set ``edit_metadata`` to ``True`` to enable editing metadata as part of the redaction process. If editing metadata is enabled, users will have the opportunity to set the value of a redacted metadata field to any value.

Bulk Redation and Review of Metadata
++++++++++++++++++++++++++++++++++++

When viewing a folder of images, you can optionally see all of the metadata that could be redacted, and, in the appropriate folders, perform bulk actions for modifying the metadata, and redacting or approving multiple items.  To do this, adjust the metadata as on an individual item's page, then check the items to process and pick the appropriate ``Redact Checked`` or ``Approve Checked`` button.  This can be disabled ``girder.local.conf``, by setting ``show_metadata_in_lists`` to False.

Note that some image redaction options are not available in the folder list redaction page.

Next Image Control
++++++++++++++++++

By default, a Next Image control is shown on the left menu bar below Collections and Users.  This is optional and can be removed by setting ``show_next_item`` to ``False`` in the configuration.

Next Folder Control
+++++++++++++++++++

By default, a Next Folder control is shown on the left menu bar below Collections and Users.  This is optional and can be removed by setting ``show_folder_item`` to ``False`` in the configuration.

Import and Export Controls
++++++++++++++++++++++++++

By default, new data can be imported into the ``AvailableToProcess`` folder and exported from the ``Approved`` folder via specific controls.  Imports require that a manifest spreadsheet file is next to the image files in the import directory.  Images can also be moved or imported into the ``AvailableToProcess`` folder using ordinary item controls in Girder.  If the import and export buttons are not going to be used, they can be hidden by setting the ``show_import_button`` and ``show_export_button`` values to False in the configuration.

Reimporting Moved Images
++++++++++++++++++++++++

By default, if an image has been imported before, it will not be reimported no matter where it is located in the system.  If you are creating folders besides those used in the basic workflow and want to reimport a file that was moved to one of these non-workflow folders, set the ``reimport_if_moved`` configuration value to True.

Customizing Import and Export Reports
+++++++++++++++++++++++++++++++++++++

If you modify your import schema, or would otherwise like to change which import data is included in import and export reports, you can specify which upload metadata fields to include in these reports by modifying the ``upload_metadata_for_export_report`` list in ``girder.local.conf``. By default, this is set to a subset of the fields in the default import schema.

Primary Folder and Image Fields
+++++++++++++++++++++++++++++++

By default, images are filed in a folder based on the ``TokenID`` value and named based on the ``ImageID`` value from the import excel file.  Further, ``ImageID`` is required to be the ``TokenID`` combined with the ``Proc_Seq`` and ``Slide_ID`` fields.  These can be changed.

If the ``validate_image_id_field`` setting is set to ``False``, there is no requirement outside of the schema file on the ``ImageID`` field.

Instead of using ``TokenID`` and ``ImageID``, these fields can be specified using the ``folder_name_field`` and ``image_name_field`` fields respectively.

The values in the ``image_name_field`` need to be unique, or only the first row with a specified value will be used.

Import Schema Modification
--------------------------

Import excel files can be customized, allowing for additional metadata to be captured during the import process. The expected schema for import files is described in ``wsi_deid/schema/importManifestScheme.json``. An example of a modified schema can be found in ``importManifestSchema.example.json``. In this example schema, the fields  ``Tumor_Rec_Number``, ``Histology_Code``, and ``Behavior_Code`` have been added. Each of these new fields uses a regular expression for validation. Enums (a set of values) can be used for validation instead of pattern matching (see the property ``Proc_Type`` for an example).

Currently, import logic requires ``TokenID``, ``Proc_Seq``, ``Slide_ID``, and ``InputFileName`` in order to properly find and rename images in the import directory. These properties in the schema should not be modified at this time.

See ``docker-compose.example.local.yml`` for instructions on using a custom schema for imports.

Using a Schema with no ``InputFileName`` Field
++++++++++++++++++++++++++++++++++++++++++++++

If you would like to use Optical Character Recognition (OCR) to match images in your import directory with rows on your upload excel/csv file, you need to make the following changes to your schema:

* Ensure your schema does not have a field ``InputFileName``, and there is no corresponding column on your upload file
* Ensure your schema contains a column for target text, and that the column is specified in ``girder.local.conf``. The property to set is ``import_text_association_column``.

The target text column should contain label text of WSIs in the import directory. During the ingest process, all images in your specified import directory will be ingested into the ``Unfiled`` folder in the ``WSI DeID`` collection. Then, those images will be associated with data found on the upload file. Progress can be tracked as a girder job. If no match can be determined, images will remain in the ``Unfiled`` folder. Images with a match will be transferred to the ``AvailableToProcess`` folder.

If ``InputFileName`` is added to the list of export fields in the ``upload_metadata_for_export_report`` settings, then the original file name will be included in the export report.

Creating New TokenIDs for Refiling Images
+++++++++++++++++++++++++++++++++++++++++

When using the bulk refile controls to move images from the ``Unfiled`` directory to ``AvailableToProcess``, the system can automatically generates new TokenIDs. The new TokenIDs are alphanumeric, and their pattern can be specified by setting the ``new_token_pattern`` property.

The pattern should be a string comprised of alphanumeric characters, "#", and "@". When generating a new TokenID, instances of "#" will be replaced with a random digit 0-9 and instances of "@" will be replaced with a letter A-Z.

For example, if the specified pattern is ``0123#@@1###``, a randomly generated TokenID might look like ``01238EJ1449``.

An Example to Allow All Import Files
++++++++++++++++++++++++++++++++++++

You can use a schema and config file to allow all files to be imported.  If there is an excel file with some minimum standards, files will be added to the ``AvailableToProcess`` folder.  If not, they will still be added to the ``Unfiled`` folder.

For example, using the sample files in the ``devops/wsi_deid`` folder, ``girder.local.example.allowall.conf`` is a configuration that changes the default folder and image column names, doesn't enforce naming constraints, and has some other UI options changed from the default.  The ``importManifestSchema.example.allowall.json`` file uses a very lax schema to not require an input file name.  The columns that are present have fairly minimal requirements.

A ``docker-compose.local.yml`` could then be specified such as::

    ---
    version: '3'
    services:
      girder:
        # Use the latest published or locally built docker image
        image: dsarchive/wsi_deid
        volumes:
          - c:\NCI_WSI:/import
          - c:\DeID_WSI:/export
          - ./importManifestSchema.example.allowall.json:/usr/local/lib/python3.9/dist-packages/wsi_deid/schema/importManifestSchema.json
          - ./girder.local.example.allowall.conf:/conf/girder.local.conf

Now, running::

    docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d

will start the system with these permissive import options.  If you modify the schema in ``importManifestSchema.example.allowall.json`` or the config file in ``girder.local.example.allowall.conf``, you can restart the system via::

    docker-compose -f docker-compose.yml -f docker-compose.local.yml restart

to run the system with the modified schema and configuration.

Original Pilot Settings
-----------------------

To have the same settings as the original pilot, use the ``docker-compose.pilot.yml`` file instead of ``docker-compose.yml``.
