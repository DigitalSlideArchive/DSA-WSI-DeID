API Usage
=========

The WSI DeID program is backed by a fully complete RESTful API.  As the WSI
DeID is built on top of Girder, the basic use is document in `Girder's
documentation <https://girder.readthedocs.io/en/latest/api-docs.html_>`_.
API calls can be made with any web request program or library, such as ``curl``, a web browser, etc.

Authentication
--------------

Many calls require a valid user with authorization to perform the specified
action.  If you are familiar with Python, you can use the ``girder-client``
package to abstract some of this.  See
<https://girder.readthedocs.io/en/latest/python-client.html>_ for details.

You can also create a Girder-Token that can be passed in request headers.  To
do this, log in to the web page, click your user name, and select "My account".
Select the "API Keys" and create a new API key with whatever permissions you
need for your API calls. Lastly, create a token for use in those API calls.
This can be done via ``curl`` like so::

   curl -X POST "https://<server>:<port>/api/v1/api_key/token?key=<api key>"

where ``server`` is the IP address or host name of the WSI DeID server,
``port`` is the port it is running on, and ``api key`` is the key you created
for your account.

The rest of these examples will use ``curl`` where it is expected that you pass
the returned token as part of the call.  For instance, to check the server
version, you could do::

    curl --header "Girder-Token: <token>" "https://<server>:<port>/api/v1/system/version"

Since this is in common to most requests, usually just the endpoint used is
discussed (e.g., ``GET system/version`` is a shorthand for the previous
requests, and assumes the Girder-Token header and the
``"https://<server>:<port>/api/v1/`` prefix to the URL.

Workflow Actions
----------------

Import
~~~~~~

The **Import** button has an equivalent API call of
``PUT wsi_deid/action/ingest``.  That is, using ``curl``::

    curl -X PUT --header "Girder-Token: <token>" "https://<server>:<port>/api/v1/wsi_deid/action/ingest"

Refiling a Single Unfiled Image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Images have internal 24-digit hexadecimal item IDs.  These IDs are used to work
on them.  If an image is in the Unfiled folder, it can be refiled via
``PUT wsi_deid/item/<id>/action/refile' --data-raw 'imageId=<image id>``.
The ``id`` is the 24-digit image ID.  The ``image id`` is the
value from one of the Excel or CSV manifest files OR a manually created value.
If specified by itself, it will be the name of the folder that the image is
filed under.  The data passed can also include ``token id``, where that is the
folder and then ``image id`` is the file name within the folder.  From curl,
the two values are specified like
``--data-raw imageId=PatientA_1&tokenId=PatientA``.

Refiling a Batch of Images
~~~~~~~~~~~~~~~~~~~~~~~~~~

Many actions can be done on a batch of images.  This requires knowing all of
the associated item IDs.  You can list all of the items in a folder by knowing
the folder ID.  There are endpoints for looking up IDs based on the paths of
them.  For example, unfiled images are in the Unfiled folder in WSI DeID
collection by default.  The ID of that folder can be obtained via
``GET resource/lookup  --data-raw 'path=%2Fcollection%2FWSI%20DeID%2FUnfiled'``.
Note that the ``curl`` parameter of ``--data-raw`` is just a value of
``path=/collection/WSI DeID/Unfiled`` that has been appropriately URI encoded.

This call will return the folder record which includes its id in the ``_id``
field.  This ID can then be used to list the first 250 items in the folder via
``GET item?folderId=<folder id>&limit=250``.  This will return a JSON list
that has an item ID in the ``_id`` of each entry.

To do a bulk refiling, the call is
``PUT wsi_deid/action/bulkRefile --data-raw '{"<first item id>":{"tokenId":"<first token id>,"imageId":""},"<second item id>":{"tokenId":"<second token id>","imageId":""},<more entries here>}'``

The data is a JSON object where the keys are the item ids and the values are the new token and image ids.

Redacting a Single Image
~~~~~~~~~~~~~~~~~~~~~~~~

To redact a single image, the actual redaction effects are set in the item's
metadata.  This can be queried with ``GET item/{id}`` and set with
``PUT item/{id}/metadata``.  The actual redaction is controlled via the
``redactList`` entry in the item metadata.  It is recommended to set these
values from the user interface and inspect the metadata to see the wide variety
of information that this can have.

The actual redaction is done via ``PUT wsi_deid/item/<item id>/action/process``

Redacting a Batch of Images
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To redact a list of images, use ``PUT wsi_deid/action/list/process --data-raw 'ids=<url encoded json list of image ids>``.

Approving Images
~~~~~~~~~~~~~~~~

Approval of a single image is done via
``PUT wsi_deid/item/<item id>/action/finish``.  For multiple images, it is
``PUT wsi_deid/action/list/finish --data-raw 'ids=<url encoded json list of image ids>``.

Export
~~~~~~

The equivalent of the **Export Recent** button is
``PUT wsi_deid/action/export``, of the **Export All** button is
``PUT wsi_deid/action/exportall``, and of the **Report** button is ``PUT wsi_deid/action/exportreport``.

Status
~~~~~~

You can get the current state of all items in the system via the
``GET wsi_deid/status`` endpoint, which returns a list of all items with the
current stage of processing and a list of each process folder with the list of
items beneath it,  The ``GET wsi_deid/item/{id}/status`` endpoint reports the
current processing folder for that item.
