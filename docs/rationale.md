# Digital Slide Archive Whole Slide Image DeIdentifier

## Software Rationale

The Surveillance Research Program (SRP) at the National Cancer Institute (NCI), which funds and operates the Surveillance, Epidemiology, and End Results (SEER) cancer registry system, is interested in collecting whole slide images (WSIs) of microscopic slides generated as part of cancer diagnosis and surgical treatment.

SEER registries, which maintain personally identifiable information (PII) and protected health information (PHI) for long-term follow up of cancer patients, will serve as honest brokers for obtaining digital WSIs of clinical microscopic slides.

In the future, the end goal will be to link these WSIs to data collected by SEER and offer them as a data product.  In order for WSIs to be shared, they need to be deidentified and the files renamed.

## Tool Developed

Partnering with Dr. David Gutman from Emory University and Kitware, Inc., SRP has developed the WSI DeID software that deidentifies WSI files, including component images and metadata.

The WSI DeID tool is an open-source software that can be deployed in either a Windows or Linux environment.

## Assessment of Software Validation

Between August 2020 and August 2021, NCI/SRP is conducting the SEER-Linked Pediatric Cancer Whole Slide Imaging Pilot (Pilot) to test the validity of this WSI deidentification software. This Pilot entails collecting WSIs and associated metadata from pediatric cancer cases via participating cancer registries.
