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

Next Image Control
++++++++++++++++++

By default, a Next Image control is shown on the left menu bar below Collections and Users.  This is optional and can be removed by setting ``show_next_item`` to ``False`` in the configuration.

Import and Export Controls
++++++++++++++++++++++++++

By default, new data can be imported into the ``AvailableToProcess`` folder and exported from the ``Approved`` folder via specific controls.  Imports require that a manifest spreadsheet file is next to the image files in the import directory.  Images can also be moved or imported into the ``AvailableToProcess`` folder using ordinary item controls in Girder.  If the import and export buttons are not going to be used, they can be hidden by setting the ``show_import_button`` and ``show_export_button`` values to False in the configuration.

Import Schema Modification
--------------------------

Import excel files can be customized, allowing for additional metadata to be captured during the import process. The expected schema for import files is described in ``wsi_deid/schema/importManifestScheme.json``. An example of a modified schema can be found in ``importManifestSchema.example.json``. In this example schema, the fields  ``Tumor_Rec_Number``, ``Histology_Code``, and ``Behavior_Code`` have been added. Each of these new fields uses a regular expression for validation. Enums (a set of values) can be used for validation instead of pattern matching (see the property ``Proc_Type`` for an example).

Currently, import logic requires ``TokenID``, ``Proc_Seq``, ``Slide_ID``, and ``InputFileName`` in order to properly find and rename images in the import directory. These properties in the schema should not be modified at this time.

See ``docker-compose.example.local.yml`` for instructions on using a custom schema for imports.
