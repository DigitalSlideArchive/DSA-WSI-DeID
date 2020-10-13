# WSI DeiD
---
## Whole-Slide Image DeIdentifier

This Whole Slide Imaging Deidentification tool, WSI DeID, was developed with support provided by the Childhood Cancer Data Initiative (CCDI) for the Surveillance Research Program (SRP) at the National Cancer Institute (NCI), which funds and operates the Surveillance, Epidemiology, and End Results (SEER) cancer registry system.

This tool is based on core Digital Slide Archive (DSA) components and provides a workflow for the deidentification of digital pathology slide image files from Leica Aperio, Hamamatsu, and Philips scanners, so that they may be shared for research. The WSI DeID Tool enables users to view all the associated metadata in the WSI, use automated business rules to redact or replace specific whole slide image (WSI) metadata fields, review the changes as part of deidentification quality control verification, and export the deidentified WSI files in the original vendor format.

- **[Additional NCI background information on WSI De-ID Tool](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/docs/rationale.md)**: Additional background on the rationale and planned use of the WSI DeID Tool is found here.

- **[Usage Documentation](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/USAGE.rst)**: This provides detailed instructions for navigating the WSI DeID Tool.


- **[WSI De-ID Tool Introduction and Installation](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/README.rst)**: This provides a technical introduction and installation instructions to the tool.

- **[IT instructions to modify import and export folder locations specific to user’s computer drive locations.](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/README.rst#import-and-export-paths)**: For IT teams, instructions to customize the location of the WSI files where WSI DeID finds the import folder (original WSI files and Upload Excel file with deidentification replacement values) and the export folder (where the deidentified WSI files will be placed) are found here. These folders cannot be selected in the tool front-end itself, and must be done via configuration files, following these instructions.

- **[IT instructions to customize deidentification business rules to fit their WSI deidentification use cases.](https://github.com/DigitalSlideArchive/DSA-WSI-DeID/blob/master/README.rst#redaction-business-rules)**: For IT teams, instructions to customize the deidentification business rules is found here. Groups can use these instructions to adapt to their specific deidentification rules.

