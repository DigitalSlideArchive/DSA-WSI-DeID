# Change Log

## Unreleased

### Features
- Allow redacting an area from a WSI ([#224](../../pull/224))
- Add an option to allow editing redacted metadata ([#221](../../pull/221))
- Add options to determine which metadata is visible and redactable ([#219](../../pull/219))
- Add options for SFTP export ([#223](../../pull/223))

### Improvements
- Added more logging during export ([#222](../../pull/222))

## Version 2.2.1

### Improvements
- Make redacting a square on the macro an option ([#198](../../pull/198))

### Bug fixes
- Require newer version of HistomicsUI plugin ([#197](../../pull/197))

### Build Improvements
- Use trivy to scan docker image ([#199](../../pull/199))

## Version 2.2.0

### Features
- Blank top/left square of the macro image ([#184](../../pull/184))
- Add a setting so that redaction reasons are not required ([#185](../../pull/185))
- Add an option to always redact the label image ([#186](../../pull/186))
- Add a next and previous button to images ([#189](../../pull/189))

### Improvements
- Remove FUSE from the Dockerfile ([#183](../../pull/183))
- Report memory and disk space on start ([#182](../../pull/182))
- Improve macro image detection ([#191](../../pull/191))
- Better export progress ([#187](../../pull/187))
- Show folder and item counts ([#188](../../pull/188))
- Add more configuration options ([#193](../../pull/193))

### Bug Fixes
- Delay importing tile sources to ensure correct config ([#173](../../pull/173))

## Version 2.1.2

### Improvements
- Sped up some file transfers and redaction speed ([#169](../../pull/169))

## Version 2.1.1

### Changes
- Fixed the hyphen in "C999-Undetermined specimen site" ([#167](../../pull/167))

## Version 2.1.0

### Changes
- Added "C999-Undetermined specimen site" Spec_site code ([#166](../../pull/166))

## Version 2.0.0

### Changes
- Updated links in the homepage ([#153](../../pull/153))

## Version 1.3.2

### Bug Fixes
- Files starting with ~$ are properly ignored during import ([#151](../../pull/151))

## Version 1.3.1

### Changes
- The schema now restricts Proc_ID to 01-99 and Slide_ID to 01-20 ([#150](../../pull/150))
- Blank lines are now allowed in DeID Upload files ([#150](../../pull/150))
- Files starting with ~$ are ignored during import ([#150](../../pull/150))

### Bug Fixes
- The Export Jobs Folder wasn't being created ([#150](../../pull/150))

## Version 1.3.0

### Features
- Validate rows of the DeID Import file via a jsonschema ([#149](../../pull/149))

### Changes
- Reports are now in subfolders and have some formatting changes ([#149](../../pull/149))

## Version 1.2.8

### Changes
- Changed the case of the default deployed collection name ([#146](../../pull/146))
- Don't percolate server error messages to client error messages ([#147](../../pull/147))

## Version 1.2.7

### Changes
- Updated import and export status messages ([#142](../../pull/142))
- ImageIDs must now be unique in the system ([#142](../../pull/142))

## Version 1.2.6

### Changes
- Updated import and export status messages ([#136](../../pull/136))

## Version 1.2.5

### Improvements
- Handle more associated images for Aperio and Hamamatsu files ([#135](../../pull/135))

### Changes
- Updated the home page ([#133](../../pull/133), [#134](../../pull/134))

## Version 1.2.4

### Bug Fixes
- Fix a potential plugin load order issue ([#132](../../pull/132))

## Version 1.2.3

### Features
- Also show the Reject control in the Image Viewer header ([#129](../../pull/129))
- Show metadata that will be added ([#131](../../pull/131))

### Improvements
- Scroll to the top of the viewport when switching to the next item ([#128](../../pull/128))
- Have two "other" categories for PHI ([#128](../../pull/128), [#131](../../pull/131))
- Ensure import filenames are ImageID-based ([#130](../../pull/130))

### Changes
- Append rather than overwrite the tiff.Software field ([#128](../../pull/128))

## Version 1.2.2

### Changes
- Modify the export report format ([#126](../../pull/126))

## Version 1.2.1

### Improvements
- Start with Girder meta section collapsed ([#125](../../pull/125))

### Changes
- Change redaction reasons and export report format ([#124](../../pull/124))

## Version 1.2.0

### Features
- Specify a reason when redacting metadata and images ([#120](../../pull/120))

### Improvements
- Indicate when images will be redacted ([#122](../../pull/122))

### Changes
- Renamed to WSI DeId / DSA-WSI-DeID ([#112](../../pull/112))
- Updated homepage ([#113](../../pull/113))
- Changed export report format ([#123](../../pull/123))

### Bug Fixes
- Make output compatible with Aperio's ImageScope ([#119](../../pull/119))

## Version 1.1.1

### Bug Fixes
- Generating an import report failed when a file was missing ([#109](../../pull/109))

## Version 1.1.0

### Features
- Generate and save import and export reports in a Reports folder ([#106](../../pull/106), [#105](../../pull/105))

### Improvements
- Improved message when there is nothing to import or export ([#107](../../pull/107))
- Handle changes to DeID Upload files ([#103](../../pull/103))

### Changes
- Use tifftools from the packaged version ([#99](../../pull/99))

## Version 1.0.0

Release used in Beta-1 tests.

