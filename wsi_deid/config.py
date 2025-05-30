import girder.utility.config

from .constants import PluginSettings

CONFIG_SECTION = 'wsi_deid'
NUMERIC_VALUES = (
    r'^\s*[+-]?(\d+([.]\d*)?([eE][+-]?\d+)?|[.]\d+([eE][+-]?\d+)?)(\s*,\s*[+-]?'
    r'(\d+([.]\d*)?([eE][+-]?\d+)?|[.]\d+([eE][+-]?\d+)?))*\s*$'
)

defaultConfig = {
    'redact_macro_square': False,
    'redact_macro_short_axis_percent': 0,
    'redact_macro_long_axis_percent': 0,
    'always_redact_label': False,
    'require_redact_category': True,
    'require_reject_reason': False,
    'edit_metadata': False,
    'add_title_to_label': True,
    'show_import_button': True,
    'show_export_button': True,
    'show_next_item': True,
    'show_metadata_in_lists': True,
    'show_next_folder': True,
    'name_template': '{tokenid}',
    'folder_template': '{tokenid}',
    'no_redact_control_keys': {
        r'^internal;aperio_version$': '',
        r'^internal;openslide;openslide\.(?!comment$)': '',
        r'^internal;openslide;tiff\.(XResolution|YResolution)$': NUMERIC_VALUES,
        r'^internal;openslide;tiff\.ResolutionUnit$': '',
    },
    'no_redact_control_keys_format_aperio': {
        r'^internal;openslide;aperio\.(AppMag|MPP|Exposure (Time|Scale))$': NUMERIC_VALUES,
    },
    'no_redact_control_keys_format_hamamatsu': {
        r'^internal;openslide;hamamatsu\.SourceLens$': NUMERIC_VALUES,
    },
    'no_redact_control_keys_format_philips': {},
    'no_redact_control_keys_format_ometiff': {
        r'^internal;omereduced;(ImageLength|ImageWidth)$': NUMERIC_VALUES,
        r'^internal;omereduced;(Series \d+ (AppMag|MPP))$': NUMERIC_VALUES,
    },
    'no_redact_control_keys_format_dicom': {
        r'^internal;openslide;dicom\.(Modality|PhotometricInterpretation)': r'',
        r'^internal;openslide;dicom\.(SeriesNumber)': NUMERIC_VALUES,  # noqa
    },
    'no_redact_control_keys_format_isyntax': {},
    'hide_metadata_keys': {
        r'^internal;openslide;openslide\.level\[': NUMERIC_VALUES,
    },
    'hide_metadata_keys_format_aperio': {
        r'^internal;openslide;(openslide\.comment|tiff\.ImageDescription)$': '',
        (
            r'^internal;openslide;aperio\.(Original(Height|Width)|Left|Top|Right|Bottom'
            r'|LineArea(X|Y)Offset|LineCameraSkew|Focus Offset|StripeWidth|DisplayColor)'
        ): NUMERIC_VALUES,
    },
    'hide_metadata_keys_format_hamamatsu': {
        (
            r'^internal;openslide;hamamatsu\.((AHEX|MHLN|YRNP|zCoarse|zFine)\['
            r'|(X|Y)OffsetFromSlideCentre|ccd.(width|height)|(focalplane|slant)\.(left|right)'
            r'(top|bottom)|stage.center)'
        ): NUMERIC_VALUES,
    },
    'hide_metadata_keys_format_philips': {},
    'hide_metadata_keys_format_ometiff': {
        r'^internal;omeinfo': '',
        r'^internal;omereduced;(BitsPerSample|SamplesPerPixel|NewSubfileType|NumberOfChannels|Instrument:Objective:NominalMagnification|Image:.*:Pixels:|TileByteCounts|TileOffsets|TileWidth|TileLength)': NUMERIC_VALUES,  # noqa
        r'^internal;omereduced;Series \d+ (DisplayColor|Exposure Scale|Exposure Time|Focus Offset|Left|Top|LineArea(X|Y)Offset|LineCameraSkew|OriginalHeight|OriginalWidth|StripeWidth)$': NUMERIC_VALUES,  # noqa
        r'^internal;omereduced;Image:\d+:Pixels:(BigEndian|Interleaved)': r'^(true|false)$',
        r'^internal;omereduced;Image:\d+:Pixels:.*(X|Y)Unit': r'^(mm|µm)$',
        r'^internal;omereduced;Image:\d+:Pixels:DimensionOrder': r'^(XYCZT|XYC|XY|XYT|XYCT|XYZT)$',
        r'^internal;omereduced;Image:\d+:Pixels:Type': r'^(uint8|uint16)$',
        r'^internal;omereduced;.*PhotometricInterpretation': r'^(RGB|RGBA)$',
        r'^internal;omereduced;Compression': r'^JPEG$',
        r'^internal;omereduced;PlanarConfiguration': r'^Chunky$',
        r'^internal;omereduced;schemaLocation': r'^http://www.openmicroscopy.org/Schemas/OME/.*xsd$',  # noqa
        r'^internal;omereduced;Image:\d+:Name': r'^(macro|label) image$',
    },
    'hide_metadata_keys_format_dicom': {
        r'^internal;openslide;dicom\.(BitsAllocated|BitsStored|Columns|HighBit|ImageOrientation.*|ImagedVolume.*|InstanceNumber|NumberOfFrames|NumberOfOpticalPaths|PixelRepresentation|PlanarConfiguration|Rows|SamplesPerPixel|TotalPixel.*)': NUMERIC_VALUES,  # noqa
        r'^internal;openslide;dicom\.(BurnedInAnnotation|ExtendedDepthOfField|SpecimenLabelInImage)': r'^(NO|YES)$',  # noqa
        r'^internal;openslide;dicom\.(FocusMethod)': r'^(AUTO|NONE)$',
        r'^internal;openslide;dicom\.(ContainerTypeCodeSequence.*|DimensionOrganization.*|ImageType.*|Implementation.*|LossyImage.*|OpticalPathSequence.*|PositionReferenceIndicator|SharedFunctional.*|SpecimenDescriptionSequence.*|Volumetric.*)': r'',  # noqa
        r'^internal;openslide;dicom\.(FrameOfReferenceUID|TransferSyntaxUID|MediaStorageSOPClassUID|MediaStorageSOPInstanceUID|SOPClassUID|SOPInstanceUID)': r'^[0-9]+(\.[0-9]+)+$',  # noqa
        r'^internal;openslide;dicom\..*': r'^(|Unknown)$',
        r'^internal;openslide;openslide.(associated.*|icc-size|level-count|mpp-x|mpp-y|quickhash-1|vendor)': NUMERIC_VALUES,  # noqa
        r'^internal;iccprofiles$': r'',
    },
    'hide_metadata_keys_format_isyntax': {
        r'^internal;(xml;|wsi;|xml$|wsi$)': '',
        r'^internal;isyntax;(is_UFS|is_UFSb|is_UVS|is_philips|isyntax_file_version)$': '',
        r'^internal;isyntax;(num_images|scanner_rack_priority)$': NUMERIC_VALUES,
    },
    'upload_metadata_for_export_report': [
        'ImageID', 'Proc_Seq', 'Proc_Type', 'Slide_ID', 'Spec_Site', 'TokenID',
    ],
    'upload_metadata_add_to_images': None,
    'import_text_association_columns': [],
    'ocr_parse_values': [],
    'folder_name_field': 'TokenID',
    'image_name_field': 'ImageID',
    'validate_image_id_field': True,
    'reject_reasons': [{
        'category': 'Cannot_Redact',
        'text': 'Cannot redact PHI',
        'key': 'Cannot_Redact',
    }, {
        'category': 'Slide_Quality',
        'text': 'Slide Quality',
        'types': [
            {'key': 'Chatter_Tears', 'text': 'Chatter/tears in tissue'},
            {'key': 'Folded_Tissue', 'text': 'Folded tissue'},
            {'key': 'Overstaining', 'text': 'Overstaining'},
            {'key': 'Cover_Slip', 'text': 'Cover slip issues'},
            {'key': 'Debris', 'text': 'Debris or dust'},
            {'key': 'Air_Bubbles', 'text': 'Air bubbles'},
            {'key': 'Pathologist_Markings', 'text': "Pathologist's Markings"},
            {'key': 'Other_Slide_Quality', 'text': 'Other'},
        ],
    }, {
        'category': 'Image_Quality',
        'text': 'Image Quality',
        'types': [
            {'key': 'Out_Of_Focus', 'text': 'Out of focus'},
            {'key': 'Low_Resolution', 'text': 'Low resolution'},
            {'key': 'Other_Image_Quality', 'text': 'Other'},
        ],
    }],
    'phi_pii_types': [
        {
            'category': 'Personal_Info',
            'text': 'Personal Information',
            'types': [
                {'key': 'Patient_Name', 'text': 'Patient Name'},
                {'key': 'Patient_DOB', 'text': 'Date of Birth '},
                {'key': 'SSN', 'text': 'Social Security Number'},
                {'key': 'Other_Personal', 'text': 'Other Personal'},
            ],
        },
        {
            'category': 'Demographics',
            'key': 'Demographics',
            'text': 'Demographics',
        },
        {
            'category': 'Facility_Physician',
            'key': 'Facility_Physician',
            'text': 'Facility/Physician Information',
        },
        {
            'category': 'Other_PHIPII',
            'key': 'Other_PHIPII',
            'text': 'Other PHI/PII',
        },
    ],
    'reimport_if_moved': False,
    'new_token_pattern': '####@@####',
}


configSchemas = {
    'hide_metadata_keys': {
        '$schema': 'http://json-schema.org/schema#',
        'patternProperties': {
            '^.*$':
            {'type': 'string'},
        },
        'additionalProperties': False,
    },
    'import_text_association_columns': {
        '$schema': 'http://json-schema.org/schema#',
        'type': 'array',
        'items': {'type': 'string'}},
    'ocr_parse_values': {
        '$schema': 'http://json-schema.org/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'key': {'type': 'string'},
                'pattern': {'type': 'string'},
                'regex': {'type': 'string'},
                'confidence': {'type': 'number'},
            },
            'required': ['key'],
            'oneOf': [{'required': ['pattern']}, {'required': ['regex']}],
        },
    },
    'no_redact_control_keys': {
        '$schema': 'http://json-schema.org/schema#',
        'patternProperties': {
            '^.*$':
            {'type': 'string'},
        },
        'additionalProperties': False,
    },
    'phi_pii_types': {
        '$schema': 'http://json-schema.org/schema#',
        'type': 'array',
        'items': {'type': 'object', 'properties': {
            'category': {'type': 'string'},
            'text': {'type': 'string'},
            'types': {'type': 'array',
                      'items': {'type': 'object', 'properties': {
                          'key': {'type': 'string'},
                          'text': {'type': 'string'}},
                          'required': ['key', 'text']}},
            'key': {'type': 'string'}},
            'anyOf': [
            {'required': ['category', 'text', 'key']},
            {'required': ['category', 'text', 'types']},
        ]}},
    'reject_reasons': {
        '$schema': 'http://json-schema.org/schema#',
        'type': 'array',
        'items': {'type': 'object', 'properties': {
            'category': {'type': 'string'},
            'text': {'type': 'string'},
            'types': {'type': 'array',
                      'items': {'type': 'object', 'properties': {
                          'key': {'type': 'string'},
                          'text': {'type': 'string'}},
                          'required': ['key', 'text']}},
            'key': {'type': 'string'}},
            'anyOf': [
            {'required': ['category', 'text', 'key']},
            {'required': ['category', 'text', 'types']},
        ]}},
    'upload_metadata_add_to_images': {
        '$schema': 'http://json-schema.org/schema#',
        'anyOf': [
            {'type': 'null'},
            {'type': 'array', 'items': {'type': 'string'}}]},
    'upload_metadata_for_export_report': {
        '$schema': 'http://json-schema.org/schema#',
        'anyOf': [
            {'type': 'null'},
            {'type': 'array', 'items': {'type': 'string'}}]},
}


def getConfig(key=None, fallback=None):
    configDict = girder.utility.config.getConfig().get(CONFIG_SECTION) or {}
    configDict = configDict.copy()
    try:
        from girder.models.setting import Setting

        for subkey in defaultConfig:
            try:
                val = Setting().get(PluginSettings.WSI_DEID_BASE + subkey)
                if val is not None:
                    configDict[subkey] = val
            except Exception:
                pass
    except Exception:
        pass
    if key is None:
        config = defaultConfig.copy()
        config.update(configDict)
        return config
    if key in configDict:
        return configDict[key]
    if key in defaultConfig:
        return defaultConfig[key]
    return fallback
