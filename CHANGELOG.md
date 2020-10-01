# Change Log

## Unreleased

### Improvements
- Handle more associated images for Aperio and Hamamatsu files

### Changes
- Updated the home page (#133, #134)

## Version 1.2.4

### Bug Fixes
- Fix a potential plugin load order issue (#133, #134)

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

