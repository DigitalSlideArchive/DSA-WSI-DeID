# WSI DeID
---
## Whole-Slide Image DeIdentifier


This Whole Slide Imaging Deidentification tool, WSI DeID, was developed with support provided by the Childhood Cancer Data Initiative (CCDI) for the Surveillance Research Program (SRP) at the National Cancer Institute (NCI), which funds and operates the Surveillance, Epidemiology, and End Results (SEER) cancer registry system.

This tool is based on core Digital Slide Archive (DSA) components and provides a workflow for the deidentification of digital pathology slide image files in Leica Aperio, Hamamatsu, Philips, OME TIFF, and DICOM formats. This deidentification is critical, so that digital slide files may be shared for research. The WSI DeID Tool enables users to view all the associated metadata in the WSI, use automated business rules to redact or replace specific whole slide image (WSI) metadata fields, review the changes as part of deidentification quality control verification, and export the deidentified WSI files in the original vendor format.

- **[Additional NCI background information on WSI DeID Tool](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/docs/rationale.md#digital-slide-archive-whole-slide-image-deidentifier)**: Additional background on the rationale and planned use of the WSI DeID Tool is found here.

- **[Usage Documentation](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/docs/USAGE.rst#wsi-deid-usage)**: This provides detailed instructions for navigating the WSI DeID Tool.


- **[WSI DeID Tool Introduction](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/README.rst#wsi-deid--)**: This provides an introduction to the tool and links to installation and usage instructions.

- **[IT instructions to modify import and export folder locations specific to user’s computer drive locations.](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/docs/INSTALL.rst#import-and-export-paths)**: For IT teams, instructions to customize the location of the WSI files where WSI DeID finds the import folder (original WSI files and Upload Excel file with deidentification replacement values) and the export folder (where the deidentified WSI files will be placed) are found here. These folders cannot be selected in the tool front-end itself, and must be done via configuration files, following these instructions.

- **[IT instructions to customize deidentification business rules to fit their WSI deidentification use cases.](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/docs/INSTALL.rst#redaction-business-rules)**: Business rules dictate automated redaction and/or replacement of potential identifiers. For IT teams, instructions to customize the deidentification business rules can be found here. Groups can use these instructions to adapt to their specific deidentification needs.
