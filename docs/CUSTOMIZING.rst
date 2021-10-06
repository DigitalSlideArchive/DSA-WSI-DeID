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

Disabling the Redaction Control
+++++++++++++++++++++++++++++++

Redaction can be disabled for certain metadata fields. This can be used for fields that are helpful to users reviewing images, but will never contain actual PHI/PII. This can be configured on a per-format basis. The following settings control this functionality.

* ``no_redact_control_keys``
* ``no_redact_control_keys_format_aperio``
* ``no_redact_control_keys_format_hamamatsu``
* ``no_redact_control_keys_format_philips``

In order to disable redaction controls for certain metadata fields, you can add `key: value` pairs to the dictionaries in `girder.local.conf`. Both the key and value need to be regular expressions. The `key` is a regular expression that will match your target metadata. The associated `value` should be a regular expression that matches the expected metadata value. For example, if your metadata should always contain an integer value, you could use the regular expression `"\\d+"`. If you view an image and the metadata value does not match the expected expression, then redaction will be available for that metadata item.

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

Normally, when a metadata field is redacted, its value becomes blank. In `girder.local.conf`, you can set `edit_metadata` to `True` to enable editing metadata as part of the redaction process. If editing metadata is enabled, users will have the opportunity to set the value of a redacted metadata field to any value.

Transferring Files to a Remote Server via SFTP
++++++++++++++++++++++++++++++++++++++++++++++

In addition to exporting approved files to a local directory, you can configure transfer of approved files to another machine via SFTP. The following settings control this functionality:

* ``sftp_host``: this is the address of the host machine to send approved files to.
* ``sftp_port``: this is the port on which the remote host is listening for SFTP connections. Default is 22.
* ``sftp_user``, ``sftp_password``: username and password of a user on the remote machine.
* ``sftp_desination_folder``: a directory on the remote machine where the approved WSIs will be sent.
* ``sftp_mode``: this setting explicitly enables this functionality. There are three choices.
   * ``0``: SFTP off, local export only. This is the default.
   * ``1``: SFTP only, no local export.
   * ``2``: SFTP and local export
