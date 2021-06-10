Customizing WSI DeID
====================

There are several ways to customize the installation of WSI DeID to change its behavior to better match your desired workflow and use case.

See the files ``devops/wsi_deid/docker-compose.example.local.yml`` and ``devops/wsi_deid/girder.local.conf`` for comments about many of these options.  Broadly, the options in ``devops/wsi_deid/docker-compose.example.local.yml`` change the deployment environment, such as directories that are used and available memory.  The options in ``devops/wsi_deid/girder.local.conf`` change the run-time behavior, such as how label and macro images are redacted.

When modifying ``devops/wsi_deid/girder.local.conf``, you'll also need to enable using the custom file by uncommenting a few lines as described in ``devops/wsi_deid/docker-compose.example.local.yml``.

Settings in girder.local.cfg
----------------------------

The WSI DeID specific settings are in a section headed by ``[wsi_deid]``.

Redacting the top/left of the macro image
+++++++++++++++++++++++++++++++++++++++++

When the ``redact_macro_square`` setting is set to ``True``, the upper left square of all macro images will automatically be blacked out.  This region often contains the label on the slide, and sometimes that can contain PHI that is visible with contrast or other image adjustment.

Redaction Catgories
+++++++++++++++++++

By default, when metadata or images are redacted, the user must pick the typoe of PHI/PII that is present and the reason for the redaction.  If the ``require_redact_category`` is set to ``False``, then, instead of requiring a reason, the user interface will show a ``REDACT`` button that toggles redaction on and off for the metadata or image.  The export file will contain ``No Reason Collected`` in these cases.


