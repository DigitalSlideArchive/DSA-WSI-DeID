# Change Log

## Unreleased

### Features
- Allow redacting an area from a WSI (#224)
- Add an option to allow editing redacted metadata (#221)
- Add options to determine which metadata is visible and redactable (#219)

### Improvements
- Added more logging during export (#222)

## Version 2.2.1

### Improvements
- Make redacting a square on the macro an option (#198)

### Bug fixes
- Require newer version of HistomicsUI plugin (#197)

### Build Improvements
- Use trivy to scan docker image (#199)

## Version 2.2.0

### Features
- Blank top/left square of the macro image (#184)
- Add a setting so that redaction reasons are not required (#185)
- Add an option to always redact the label image (#186)
- Add a next and previous button to images (#189)

### Improvements
- Remove FUSE from the Dockerfile (#183)
- Report memory and disk space on start (#182)
- Improve macro image detection (#191)
- Better export progress (#187)
- Show folder and item counts (#188)
- Add more configuration options (#193)

### Bug Fixes
- Delay importing tile sources to ensure correct config (#173)

## Version 2.1.2

### Improvements
- Sped up some file transfers and redaction speed (#169)

## Version 2.1.1

### Changes
- Fixed the hyphen in "C999-Undetermined specimen site" (#167)

## Version 2.1.0

### Changes
- Added "C999-Undetermined specimen site" Spec_site code (#166)

## Version 2.0.0

### Changes
- Updated links in the homepage (#153)

## Version 1.3.2

### Bug Fixes
- Files starting with ~$ are properly ignored during import (#151)

## Version 1.3.1

### Changes
- The schema now restricts Proc_ID to 01-99 and Slide_ID to 01-20 (#150)
- Blank lines are now allowed in DeID Upload files (#150)
- Files starting with ~$ are ignored during import (#150)

### Bug Fixes
- The Export Jobs Folder wasn't being created (#150)

## Version 1.3.0

### Features
- Validate rows of the DeID Import file via a jsonschema (#149)

### Changes
- Reports are now in subfolders and have some formatting changes (#149)

## Version 1.2.8

### Changes
- Changed the case of the default deployed collection name (#146)
- Don't percolate server error messages to client error messages (#147)

## Version 1.2.7

### Changes
- Updated import and export status messages (#142)
- ImageIDs must now be unique in the system (#142)

## Version 1.2.6

### Changes
- Updated import and export status messages (#136)

## Version 1.2.5

### Improvements
- Handle more associated images for Aperio and Hamamatsu files (#135)

### Changes
- Updated the home page (#133, #134)

## Version 1.2.4

### Bug Fixes
- Fix a potential plugin load order issue (#132)

## Version 1.2.3

### Features
- Also show the Reject control in the Image Viewer header (#129)
- Show metadata that will be added (#131)

### Improvements
- Scroll to the top of the viewport when switching to the next item (#128)
- Have two "other" categories for PHI (#128, #131)
- Ensure import filenames are ImageID-based (#130)

### Changes
- Append rather than overwrite the tiff.Software field (#128)

## Version 1.2.2

### Changes
- Modify the export report format (#126)

## Version 1.2.1

### Improvements
- Start with Girder meta section collapsed (#125)

### Changes
- Change redaction reasons and export report format (#124)

## Version 1.2.0

### Features
- Specify a reason when redacting metadata and images (#120)

### Improvements
- Indicate when images will be redacted (#122)

### Changes
- Renamed to WSI DeId / DSA-WSI-DeID (#112)
- Updated homepage (#113)
- Changed export report format (#123)

### Bug Fixes
- Make output compatible with Aperio's ImageScope (#119)

## Version 1.1.1

### Bug Fixes
- Generating an import report failed when a file was missing (#109)

## Version 1.1.0

### Features
- Generate and save import and export reports in a Reports folder (#106, #105)

### Improvements
- Improved message when there is nothing to import or export (#107)
- Handle changes to DeID Upload files (#103)

### Changes
- Use tifftools from the packaged version (#99)

## Version 1.0.0

Release used in Beta-1 tests.

