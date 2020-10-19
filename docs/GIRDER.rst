====================
Background on Girder
====================

See `README.rst <../README.rst>`_ for high level information about how to navigate the full documentation.

Navigating in Girder
--------------------

You will see several links on the left hand side of the screen that will allow you to navigate. These links are:

* ``Collections`` - shows all of the top level collections. The only important collection for this project is ``WSI DeID``.
* ``Groups`` - shows the user groups. You can ignore this for the purposes of this project.
* ``Users`` - shows all of the users in the current system. As an admin user, you can reset a user's password by going to their user account and selecting Edit User from the Actions menu.
* ``Admin console`` - will only be visible to admin users. You should leave this section alone unless you know what you are doing.
* ``Next Item`` - will navigate any user to the next available image to be processed in the WSI DeID workflow.


User Types and Permissions
--------------------------

**Admin User:** The first registered user of a WSI DeID system will be an admin user and will have super-user privileges, meaning that the user can take any actions on the system. Admin users can change permissions of other users in the system, and can reset users passwords. The Admin user should be tied to an IT support staff member, and users of the system should create Non-Super Users.

**Non-Super Users:** All subsequently created users will be Non-Super Users, who will have the ability to use the redaction workflows.

**Anonymous User:** If no user is logged in, you are said to be browsing the WSI DeID as the ``anonymous`` user. The ``anonymous`` user may browse data in the WSI DeID but cannot take any actions that redact data or change the state of data. When you are browsing as the ``anonymous`` user you will see the option to ``Register or Log In`` as in the below screenshot.


Folder Versus Item Views
------------------------

The WSI DeID is based on Girder, which is structured as Folders and Items. **Folders** are similar to a directory on your local computer's filesystem; whereas, **Items** are a container for one or more files, such as would be on your local computer's filesystem. For the purposes of the WSI DeID documentation, an image is an item and  may be used interchangeably. A whole slide image file may contain multiple images, such as in the case where there is a primary image and Associated Images such as a label or macro image.

A folder in Girder may contain items, and an item always has to be in a folder.
