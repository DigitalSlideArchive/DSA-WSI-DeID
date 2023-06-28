==============
Error Messages
==============

See `README.rst <../README.rst>`_ for high level information about how to navigate the full documentation.


Possible Error Messages Encountered After Import
================================================

.. csv-table::
    :header-rows: 1
    :widths: 10, 25, 65

    ID#,DSA WSI DeID Error Message,How is the error message triggered?
    1,Import Completed,whenever an import run was attempted and completed regardless of the result or if any issues with the input WSI files or DeID Upload File
    2,"Import process completed, with errors","when the system is working, sees folders and WSI files, but something is off such as a file cannot be imported for some semantic issues"
    3,Nothing to import. Import Folder is empty,"when the import folder is empty, and an import run was attempted"
    4,Failed to import.,"will only be displayed if there is a condition that we did not anticipate (which means that I can't give an example of how to make it appear).  If this occurs, it probably means someone needs to check the logs and figure out what happened and how to improve things in a future version."
    5,(number) image(s) added.,number of WSI files that were successfully imported
    6,(number) image(s) with duplicate ImageID.  Check DeID Upload file.,will occur if a different input file to be imported has the same ImageID as an input file that is already staged in the AvailableToProcess folder in the DSA
    7,(number) image(s) missing from import folder. Check Upload File and WSI image filenames. ,when the input image file referenced in the Upload File is missing from the import folder (could also happen due to naming differences)
    8,"(number) image(s) in import folder, but not listed in the DeID Upload Excel.    ","when an input file is present in the import folder but not referenced in the DeID Upload file (could also happen due to naming differences)  (e.g. 10 WSI files, but not same 10 WSI files listed in the DEID Excel)"
    9,(number) image(s) already present.,"when the import was performed, and the identical data (input file) is already staged in the AvailableToProcess folder"
    10,(number) image(s) failed to import. Check if image file is in accepted WSI format.  ,when the image file is not compatible to the DSA and import of the file is not successful (e.g. .isyntax files)
    11,(number) of DeID Upload Excel file(s) parsed.,the number of excel files (DeID Upload Files) that was successfully read and used for referencing input image files in the import folder
    12,Import process completed with errors. No DeID Upload file present.,when the DeID Upload file is missing from the import folder
    13,(number) image(s) with invalid data in a DeID Upload File,when metadata associated with a WSI is incorrectly listed in the DeID Upload File
    14,(number) Excel file(s) could not be read.,"appears if you have a file whose name ends in xls or xlsx or csv and is NOT an Excel file, for instance by using a Word file that was renamed to end in "".xls""."
    15,Nothing to import. Import folder is empty.,If local import folder is empty
    16,Recent export task completed,"whenever an export run (via the ""Export Recent"" button) was attempted and processed regardless of the result"
    17,"Failed to export recent items.  Check export file location, if there is sufficient space, or other system issue.","when an export run (via the ""Export Recent"")  was not processed due to incorrect export path location, export file name or some server/computing issues"
    18,Export all task completed,"whenever an export run (via the ""Export All"" button) was attempted and processed regardless of the result"
    19,"Failed to export all items.  Check export file location, if there is sufficient space, or other system issue.","when export run (via the ""Export All"")  was not processed due to incorrect export path location, import file name or some server/computing issues"
    20,(number) image(s) exported.,"when processed WSI files in the ""Approved"" file is successfully exported to the local export folder"
    21,(number) image(s) with the same ImageID(s) but different WSI file size already present in Export Folder. Remove the corresponding image(s) from the export directory and select Export again.,"when export actions (via ""Export Recent"" or ""Export All"") were selected and there is a file with the SAME ImageID is already in the local export folder BUT the actual WSI contents between the files, exported vs. to-be-exported, are different. This is a way to tell users that a file with the same ImageID is already exported, however, the source WSI file or processed contents are not the same as the one with the same ImageID that is to be exported"
    22,(number) image(s) previously exported and already exist in export folder,"when export actions (via ""Export Recent"" or ""Export All"") were selected and there is already a file with the same ImageID in the local export folder"
    23,"(number) image(s) currently quarantined. Only files in ""Approved"" workflow stage are transferred to Export folder.","when export actions (via ""Export Recent"" or ""Export All"") were selected and there are WSI files in the ""Quarantine"" folder"
    24,"(number) image(s) with rejected status. Only files in ""Approved"" workflow stage are transferred to Export folder.","when export actions (via ""Export Recent"" or ""Export All"") were selected and there are WSI files in the ""Rejected"" folder"
    25,Nothing to export.  ,"when export actions (via ""Export Recent"" or ""Export All"") were selected but the ""Approved"" folder is empty"


Possible Messages In The Import Job Report
==========================================

.. csv-table::
    :header-rows: 1
    :widths: 10, 20, 15, 40, 15

    Status ID #,Software Status,Associated Type,Status/Failure Reason,Associated Error Message (ID #)
    1,Parsed,DeID Upload File,Parsed,"1, 2, 11"
    2,Bad Format,DeID Upload File,"Cannot Read (file name), it is not formatted properly",2
    3,Error in DeID Upload File,DeID Upload File,Invalid (field name) in (cell location),"2, 11"
    4,Not Excel,DeID Upload,"Cannot Read (file name), it is not an Excel file",2
    5,Imported,WSI,Imported,"1, 2, 5"
    6,Error in DeID Upload file,WSI,Invalid (field name) in (cell location),13
    7,Not in DeID Upload file,WSI,Not in DeID Upload file,"8, 12"
    8,Already imported,WSI,Already imported,9
    9,Failed to import,WSI,Image file is not an accepted WSI format,10
    10,File missing,WSI,File missing,7
    11,Duplicate ImageID,WSI,A different image with the same ImageID was previously imported,6
