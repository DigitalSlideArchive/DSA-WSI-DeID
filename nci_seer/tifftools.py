#!/usr/bin/env python3

import argparse
import os
import struct

tiffDatatypes = {
    1: {'pack': 'B', 'name': 'BYTE', 'size': 1, 'desc': 'UINT8'},
    2: {'pack': None, 'name': 'ASCII', 'size': 1, 'desc': 'null-terminated string'},
    3: {'pack': 'H', 'name': 'SHORT', 'size': 2, 'desc': 'UINT16'},
    4: {'pack': 'L', 'name': 'LONG', 'size': 4, 'desc': 'UINT32'},
    5: {'pack': 'LL', 'name': 'RATIONAL', 'size': 8, 'desc': 'two UINT32'},
    6: {'pack': 'b', 'name': 'SBYTE', 'size': 1, 'desc': 'INT8'},
    7: {'pack': None, 'name': 'UNDEFINED', 'size': 1, 'desc': 'arbitrary binary'},
    8: {'pack': 'h', 'name': 'SSHORT', 'size': 2, 'desc': 'INT16'},
    9: {'pack': 'l', 'name': 'SLONG', 'size': 4, 'desc': 'INT32'},
    10: {'pack': 'll', 'name': 'SRATIONAL', 'size': 8, 'desc': 'two INT32'},
    11: {'pack': 'f', 'name': 'FLOAT', 'size': 4, 'desc': 'float'},
    12: {'pack': 'd', 'name': 'DOUBLE', 'size': 8, 'desc': 'double'},
    13: {'pack': 'L', 'name': 'IFD', 'size': 4, 'desc': 'UINT32'},
    16: {'pack': 'Q', 'name': 'LONG8', 'size': 8, 'desc': 'UINT64'},
    17: {'pack': 'q', 'name': 'SLONG8', 'size': 8, 'desc': 'INT64'},
    18: {'pack': 'Q', 'name': 'IFD8', 'size': 8, 'desc': 'UINT64'},
}

SUBIFD_TAG = 0x14A
offsetTagTable = {
    0x111: 'StripOffsets',
    0x120: 'FreeOffsets',
    0x144: 'TileOffsets',
    0x14A: 'SubIFD',  # data is a list of offsets
    0x207: 'JPEGQTables',
    0x208: 'JPEGDCTables',
    0x209: 'JPEGACTables',
}
offsetTagByteCounts = {
    0x111: 0x117,  # StripByteCounts
    0x120: 0x121,  # FreeByteCounts
    0x144: 0x145,  # TileByteCounts
}
offsetTagLengths = {
    0x207: 64,
    0x208: 16 + 17,
    0x209: 16 + 256,
}

COPY_CHUNKSIZE = 1024 ** 2


# Eventually, it would be good to have associated enums, flags, expected
# datatypes, expected counts, etc.  Perhaps change names to CamelCase.
TiffTags = {
    254: {'name': 'SUBFILETYPE'},
    255: {'name': 'OSUBFILETYPE'},
    256: {'name': 'IMAGEWIDTH'},
    257: {'name': 'IMAGELENGTH'},
    258: {'name': 'BITSPERSAMPLE'},
    259: {'name': 'COMPRESSION'},
    262: {'name': 'PHOTOMETRIC'},
    263: {'name': 'THRESHHOLDING'},
    264: {'name': 'CELLWIDTH'},
    265: {'name': 'CELLLENGTH'},
    266: {'name': 'FILLORDER'},
    269: {'name': 'DOCUMENTNAME'},
    270: {'name': 'IMAGEDESCRIPTION'},
    271: {'name': 'MAKE'},
    272: {'name': 'MODEL'},
    273: {'name': 'STRIPOFFSETS'},
    274: {'name': 'ORIENTATION'},
    277: {'name': 'SAMPLESPERPIXEL'},
    278: {'name': 'ROWSPERSTRIP'},
    279: {'name': 'STRIPBYTECOUNTS'},
    280: {'name': 'MINSAMPLEVALUE'},
    281: {'name': 'MAXSAMPLEVALUE'},
    282: {'name': 'XRESOLUTION'},
    283: {'name': 'YRESOLUTION'},
    284: {'name': 'PLANARCONFIG'},
    285: {'name': 'PAGENAME'},
    286: {'name': 'XPOSITION'},
    287: {'name': 'YPOSITION'},
    288: {'name': 'FREEOFFSETS'},
    289: {'name': 'FREEBYTECOUNTS'},
    290: {'name': 'GRAYRESPONSEUNIT'},
    291: {'name': 'GRAYRESPONSECURVE'},
    292: {'name': 'T4OPTIONS'},
    293: {'name': 'T6OPTIONS'},
    296: {'name': 'RESOLUTIONUNIT'},
    297: {'name': 'PAGENUMBER'},
    300: {'name': 'COLORRESPONSEUNIT'},
    301: {'name': 'TRANSFERFUNCTION'},
    305: {'name': 'SOFTWARE'},
    306: {'name': 'DATETIME'},
    315: {'name': 'ARTIST'},
    316: {'name': 'HOSTCOMPUTER'},
    317: {'name': 'PREDICTOR'},
    318: {'name': 'WHITEPOINT'},
    319: {'name': 'PRIMARYCHROMATICITIES'},
    320: {'name': 'COLORMAP'},
    321: {'name': 'HALFTONEHINTS'},
    322: {'name': 'TILEWIDTH'},
    323: {'name': 'TILELENGTH'},
    324: {'name': 'TILEOFFSETS'},
    325: {'name': 'TILEBYTECOUNTS'},
    326: {'name': 'BADFAXLINES'},
    327: {'name': 'CLEANFAXDATA'},
    328: {'name': 'CONSECUTIVEBADFAXLINES'},
    330: {'name': 'SUBIFD'},
    332: {'name': 'INKSET'},
    333: {'name': 'INKNAMES'},
    334: {'name': 'NUMBEROFINKS'},
    336: {'name': 'DOTRANGE'},
    337: {'name': 'TARGETPRINTER'},
    338: {'name': 'EXTRASAMPLES'},
    339: {'name': 'SAMPLEFORMAT'},
    340: {'name': 'SMINSAMPLEVALUE'},
    341: {'name': 'SMAXSAMPLEVALUE'},
    343: {'name': 'CLIPPATH'},
    344: {'name': 'XCLIPPATHUNITS'},
    345: {'name': 'YCLIPPATHUNITS'},
    346: {'name': 'INDEXED'},
    347: {'name': 'JPEGTABLES'},
    351: {'name': 'OPIPROXY'},
    400: {'name': 'GLOBALPARAMETERSIFD'},
    401: {'name': 'PROFILETYPE'},
    402: {'name': 'FAXPROFILE'},
    403: {'name': 'CODINGMETHODS'},
    404: {'name': 'VERSIONYEAR'},
    405: {'name': 'MODENUMBER'},
    433: {'name': 'DECODE'},
    434: {'name': 'IMAGEBASECOLOR'},
    435: {'name': 'T82OPTIONS'},
    512: {'name': 'JPEGPROC'},
    513: {'name': 'JPEGIFOFFSET'},
    514: {'name': 'JPEGIFBYTECOUNT'},
    515: {'name': 'JPEGRESTARTINTERVAL'},
    517: {'name': 'JPEGLOSSLESSPREDICTORS'},
    518: {'name': 'JPEGPOINTTRANSFORM'},
    519: {'name': 'JPEGQTABLES'},
    520: {'name': 'JPEGDCTABLES'},
    521: {'name': 'JPEGACTABLES'},
    529: {'name': 'YCBCRCOEFFICIENTS'},
    530: {'name': 'YCBCRSUBSAMPLING'},
    531: {'name': 'YCBCRPOSITIONING'},
    532: {'name': 'REFERENCEBLACKWHITE'},
    559: {'name': 'STRIPROWCOUNTS'},
    700: {'name': 'XMLPACKET'},
    32781: {'name': 'OPIIMAGEID'},
    32953: {'name': 'REFPTS'},
    32954: {'name': 'REGIONTACKPOINT'},
    32955: {'name': 'REGIONWARPCORNERS'},
    32956: {'name': 'REGIONAFFINE'},
    32995: {'name': 'MATTEING'},
    32996: {'name': 'DATATYPE'},
    32997: {'name': 'IMAGEDEPTH'},
    32998: {'name': 'TILEDEPTH'},
    33300: {'name': 'PIXAR_IMAGEFULLWIDTH'},
    33301: {'name': 'PIXAR_IMAGEFULLLENGTH'},
    33302: {'name': 'PIXAR_TEXTUREFORMAT'},
    33303: {'name': 'PIXAR_WRAPMODES'},
    33304: {'name': 'PIXAR_FOVCOT'},
    33305: {'name': 'PIXAR_MATRIX_WORLDTOSCREEN'},
    33306: {'name': 'PIXAR_MATRIX_WORLDTOCAMERA'},
    33405: {'name': 'WRITERSERIALNUMBER'},
    33421: {'name': 'CFAREPEATPATTERNDIM'},
    33422: {'name': 'CFAPATTERN'},
    33432: {'name': 'COPYRIGHT'},
    33723: {'name': 'RICHTIFFIPTC'},
    34016: {'name': 'IT8SITE'},
    34017: {'name': 'IT8COLORSEQUENCE'},
    34018: {'name': 'IT8HEADER'},
    34019: {'name': 'IT8RASTERPADDING'},
    34020: {'name': 'IT8BITSPERRUNLENGTH'},
    34021: {'name': 'IT8BITSPEREXTENDEDRUNLENGTH'},
    34022: {'name': 'IT8COLORTABLE'},
    34023: {'name': 'IT8IMAGECOLORINDICATOR'},
    34024: {'name': 'IT8BKGCOLORINDICATOR'},
    34025: {'name': 'IT8IMAGECOLORVALUE'},
    34026: {'name': 'IT8BKGCOLORVALUE'},
    34027: {'name': 'IT8PIXELINTENSITYRANGE'},
    34028: {'name': 'IT8TRANSPARENCYINDICATOR'},
    34029: {'name': 'IT8COLORCHARACTERIZATION'},
    34030: {'name': 'IT8HCUSAGE'},
    34031: {'name': 'IT8TRAPINDICATOR'},
    34032: {'name': 'IT8CMYKEQUIVALENT'},
    34232: {'name': 'FRAMECOUNT'},
    34377: {'name': 'PHOTOSHOP'},
    34665: {'name': 'EXIFIFD'},
    34675: {'name': 'ICCPROFILE'},
    34732: {'name': 'IMAGELAYER'},
    34750: {'name': 'JBIGOPTIONS'},
    34853: {'name': 'GPSIFD'},
    34908: {'name': 'FAXRECVPARAMS'},
    34909: {'name': 'FAXSUBADDRESS'},
    34910: {'name': 'FAXRECVTIME'},
    34911: {'name': 'FAXDCS'},
    34929: {'name': 'FEDEX_EDR'},
    37439: {'name': 'STONITS'},
    40965: {'name': 'INTEROPERABILITYIFD'},
    50674: {'name': 'LERC_PARAMETERS'},
    50706: {'name': 'DNGVERSION'},
    50707: {'name': 'DNGBACKWARDVERSION'},
    50708: {'name': 'UNIQUECAMERAMODEL'},
    50709: {'name': 'LOCALIZEDCAMERAMODEL'},
    50710: {'name': 'CFAPLANECOLOR'},
    50711: {'name': 'CFALAYOUT'},
    50712: {'name': 'LINEARIZATIONTABLE'},
    50713: {'name': 'BLACKLEVELREPEATDIM'},
    50714: {'name': 'BLACKLEVEL'},
    50715: {'name': 'BLACKLEVELDELTAH'},
    50716: {'name': 'BLACKLEVELDELTAV'},
    50717: {'name': 'WHITELEVEL'},
    50718: {'name': 'DEFAULTSCALE'},
    50719: {'name': 'DEFAULTCROPORIGIN'},
    50720: {'name': 'DEFAULTCROPSIZE'},
    50721: {'name': 'COLORMATRIX1'},
    50722: {'name': 'COLORMATRIX2'},
    50723: {'name': 'CAMERACALIBRATION1'},
    50724: {'name': 'CAMERACALIBRATION2'},
    50725: {'name': 'REDUCTIONMATRIX1'},
    50726: {'name': 'REDUCTIONMATRIX2'},
    50727: {'name': 'ANALOGBALANCE'},
    50728: {'name': 'ASSHOTNEUTRAL'},
    50729: {'name': 'ASSHOTWHITEXY'},
    50730: {'name': 'BASELINEEXPOSURE'},
    50731: {'name': 'BASELINENOISE'},
    50732: {'name': 'BASELINESHARPNESS'},
    50733: {'name': 'BAYERGREENSPLIT'},
    50734: {'name': 'LINEARRESPONSELIMIT'},
    50735: {'name': 'CAMERASERIALNUMBER'},
    50736: {'name': 'LENSINFO'},
    50737: {'name': 'CHROMABLURRADIUS'},
    50738: {'name': 'ANTIALIASSTRENGTH'},
    50739: {'name': 'SHADOWSCALE'},
    50740: {'name': 'DNGPRIVATEDATA'},
    50741: {'name': 'MAKERNOTESAFETY'},
    50778: {'name': 'CALIBRATIONILLUMINANT1'},
    50779: {'name': 'CALIBRATIONILLUMINANT2'},
    50780: {'name': 'BESTQUALITYSCALE'},
    50781: {'name': 'RAWDATAUNIQUEID'},
    50827: {'name': 'ORIGINALRAWFILENAME'},
    50828: {'name': 'ORIGINALRAWFILEDATA'},
    50829: {'name': 'ACTIVEAREA'},
    50830: {'name': 'MASKEDAREAS'},
    50831: {'name': 'ASSHOTICCPROFILE'},
    50832: {'name': 'ASSHOTPREPROFILEMATRIX'},
    50833: {'name': 'CURRENTICCPROFILE'},
    50834: {'name': 'CURRENTPREPROFILEMATRIX'},
    65535: {'name': 'DCSHUESHIFTVALUES'},
    65536: {'name': 'FAXMODE'},
    65537: {'name': 'JPEGQUALITY'},
    65538: {'name': 'JPEGCOLORMODE'},
    65539: {'name': 'JPEGTABLESMODE'},
    65540: {'name': 'FAXFILLFUNC'},
    65549: {'name': 'PIXARLOGDATAFMT'},
    65550: {'name': 'DCSIMAGERTYPE'},
    65551: {'name': 'DCSINTERPMODE'},
    65552: {'name': 'DCSBALANCEARRAY'},
    65553: {'name': 'DCSCORRECTMATRIX'},
    65554: {'name': 'DCSGAMMA'},
    65555: {'name': 'DCSTOESHOULDERPTS'},
    65556: {'name': 'DCSCALIBRATIONFD'},
    65557: {'name': 'ZIPQUALITY'},
    65558: {'name': 'PIXARLOGQUALITY'},
    65559: {'name': 'DCSCLIPRECTANGLE'},
    65560: {'name': 'SGILOGDATAFMT'},
    65561: {'name': 'SGILOGENCODE'},
    65562: {'name': 'LZMAPRESET'},
    65563: {'name': 'PERSAMPLE'},
    65564: {'name': 'ZSTD_LEVEL'},
    65565: {'name': 'LERC_VERSION'},
    65566: {'name': 'LERC_ADD_COMPRESSION'},
    65567: {'name': 'LERC_MAXZERROR'},
    65568: {'name': 'WEBP_LEVEL'},
    65569: {'name': 'WEBP_LOSSLESS'},
    # EXIF Tags
    33434: {'name': 'EXPOSURETIME', 'source': 'exif'},
    33437: {'name': 'FNUMBER', 'source': 'exif'},
    34850: {'name': 'EXPOSUREPROGRAM', 'source': 'exif'},
    34852: {'name': 'SPECTRALSENSITIVITY', 'source': 'exif'},
    34855: {'name': 'ISOSPEEDRATINGS', 'source': 'exif'},
    34856: {'name': 'OECF', 'source': 'exif'},
    36864: {'name': 'EXIFVERSION', 'source': 'exif'},
    36867: {'name': 'DATETIMEORIGINAL', 'source': 'exif'},
    36868: {'name': 'DATETIMEDIGITIZED', 'source': 'exif'},
    37121: {'name': 'COMPONENTSCONFIGURATION', 'source': 'exif'},
    37122: {'name': 'COMPRESSEDBITSPERPIXEL', 'source': 'exif'},
    37377: {'name': 'SHUTTERSPEEDVALUE', 'source': 'exif'},
    37378: {'name': 'APERTUREVALUE', 'source': 'exif'},
    37379: {'name': 'BRIGHTNESSVALUE', 'source': 'exif'},
    37380: {'name': 'EXPOSUREBIASVALUE', 'source': 'exif'},
    37381: {'name': 'MAXAPERTUREVALUE', 'source': 'exif'},
    37382: {'name': 'SUBJECTDISTANCE', 'source': 'exif'},
    37383: {'name': 'METERINGMODE', 'source': 'exif'},
    37384: {'name': 'LIGHTSOURCE', 'source': 'exif'},
    37385: {'name': 'FLASH', 'source': 'exif'},
    37386: {'name': 'FOCALLENGTH', 'source': 'exif'},
    37396: {'name': 'SUBJECTAREA', 'source': 'exif'},
    37500: {'name': 'MAKERNOTE', 'source': 'exif'},
    37510: {'name': 'USERCOMMENT', 'source': 'exif'},
    37520: {'name': 'SUBSECTIME', 'source': 'exif'},
    37521: {'name': 'SUBSECTIMEORIGINAL', 'source': 'exif'},
    37522: {'name': 'SUBSECTIMEDIGITIZED', 'source': 'exif'},
    40960: {'name': 'FLASHPIXVERSION', 'source': 'exif'},
    40961: {'name': 'COLORSPACE', 'source': 'exif'},
    40962: {'name': 'PIXELXDIMENSION', 'source': 'exif'},
    40963: {'name': 'PIXELYDIMENSION', 'source': 'exif'},
    40964: {'name': 'RELATEDSOUNDFILE', 'source': 'exif'},
    41483: {'name': 'FLASHENERGY', 'source': 'exif'},
    41484: {'name': 'SPATIALFREQUENCYRESPONSE', 'source': 'exif'},
    41486: {'name': 'FOCALPLANEXRESOLUTION', 'source': 'exif'},
    41487: {'name': 'FOCALPLANEYRESOLUTION', 'source': 'exif'},
    41488: {'name': 'FOCALPLANERESOLUTIONUNIT', 'source': 'exif'},
    41492: {'name': 'SUBJECTLOCATION', 'source': 'exif'},
    41493: {'name': 'EXPOSUREINDEX', 'source': 'exif'},
    41495: {'name': 'SENSINGMETHOD', 'source': 'exif'},
    41728: {'name': 'FILESOURCE', 'source': 'exif'},
    41729: {'name': 'SCENETYPE', 'source': 'exif'},
    41730: {'name': 'CFAPATTERN', 'source': 'exif'},
    41985: {'name': 'CUSTOMRENDERED', 'source': 'exif'},
    41986: {'name': 'EXPOSUREMODE', 'source': 'exif'},
    41987: {'name': 'WHITEBALANCE', 'source': 'exif'},
    41988: {'name': 'DIGITALZOOMRATIO', 'source': 'exif'},
    41989: {'name': 'FOCALLENGTHIN35MMFILM', 'source': 'exif'},
    41990: {'name': 'SCENECAPTURETYPE', 'source': 'exif'},
    41991: {'name': 'GAINCONTROL', 'source': 'exif'},
    41992: {'name': 'CONTRAST', 'source': 'exif'},
    41993: {'name': 'SATURATION', 'source': 'exif'},
    41994: {'name': 'SHARPNESS', 'source': 'exif'},
    41995: {'name': 'DEVICESETTINGDESCRIPTION', 'source': 'exif'},
    41996: {'name': 'SUBJECTDISTANCERANGE', 'source': 'exif'},
    42016: {'name': 'IMAGEUNIQUEID', 'source': 'exif'},
    # Hamamatsu tags
    65420: {'name': 'NDPI_FORMAT_FLAG', 'source': 'hamamatsu'},
    65421: {'name': 'NDPI_SOURCELENS', 'source': 'hamamatsu'},
    65422: {'name': 'NDPI_XOFFSET', 'source': 'hamamatsu'},
    65423: {'name': 'NDPI_YOFFSET', 'source': 'hamamatsu'},
    65424: {'name': 'NDPI_FOCAL_PLANE', 'source': 'hamamatsu'},
    65426: {'name': 'NDPI_MCU_STARTS', 'source': 'hamamatsu'},
    65427: {'name': 'NDPI_REFERENCE', 'source': 'hamamatsu'},
    65442: {'name': 'NDPI_NDPSN', 'source': 'hamamatsu'},  # not offical name
    65449: {'name': 'NDPI_PROPERTY_MAP', 'source': 'hamamatsu'},
}


def read_tiff(path):
    """
    Read the non-imaging data from a TIFF and return a Python structure with
    the results.
    """
    info = {
        'path': path,
        'size': os.path.getsize(path),
        'ifds': [],
    }
    with open(path, 'rb') as tiff:
        header = tiff.read(4)
        info['header'] = header
        if header not in (b'II\x2a\x00', b'MM\x00\x2a', b'II\x2b\x00', 'MM\x00\x2b'):
            raise Exception('Not a known tiff header for %s' % path)
        info['bigEndian'] = header[:2] == b'MM'
        info['endianPack'] = bom = '>' if info['bigEndian'] else '<'
        info['bigtiff'] = b'\x2b' in header[2:4]
        if info['bigtiff']:
            offsetsize, zero, nextifd = struct.unpack(bom + 'HHQ', tiff.read(12))
            if offsetsize != 8 or zero != 0:
                raise Exception('Unexpected offset size')
        else:
            nextifd = struct.unpack(bom + 'L', tiff.read(4))[0]
        info['firstifd'] = nextifd
        while nextifd:
            nextifd = read_ifd(tiff, info, nextifd, info['ifds'])
    return info


def read_ifd(tiff, info, ifdOffset, ifdList):
    """
    Read an IFD and any subIFDs.

    :param tiff: the open tiff file object.
    :param info: the total result structure.  Used to track offset locations
        and contains big endian and bigtiff flags.
    :param ifdOffset: byte location in file of this ifd.
    :param ifdList: a list that this ifd will be appended to.
    """
    bom = info['endianPack']
    tiff.seek(ifdOffset)
    # Store the main path here.  This facilitates merging files.
    ifd = {
        'offset': ifdOffset,
        'tags': {},
        'path': info['path'],
        'bigEndian': info['bigEndian'],
        'bigtiff': info['bigtiff'],
    }
    if info['bigtiff']:
        ifd['entries'] = struct.unpack(bom + 'Q', tiff.read(8))[0]
    else:
        ifd['entries'] = struct.unpack(bom + 'H', tiff.read(2))[0]
    for _entry in range(ifd['entries']):
        if info['bigtiff']:
            tag, datatype, count, data = struct.unpack(bom + 'HHQQ', tiff.read(20))
            datalen = 8
        else:
            tag, datatype, count, data = struct.unpack(bom + 'HHLL', tiff.read(12))
            datalen = 4
        taginfo = {
            'type': datatype,
            'count': count,
            'datapos': tiff.tell() - datalen,
        }
        if count * tiffDatatypes[taginfo['type']]['size'] > datalen:
            taginfo['offset'] = data
        if tag in ifd['tags']:
            print('duplicate tag %d in %s: data at %d and %d' % (
                tag, ifd['path'], ifd['tags'][tag]['datapos'], taginfo['datapos']))
        ifd['tags'][tag] = taginfo
    ifd['nextifdRecord'] = tiff.tell()
    if info['bigtiff']:
        ifd['nextifd'] = struct.unpack(bom + 'Q', tiff.read(8))[0]
    else:
        ifd['nextifd'] = struct.unpack(bom + 'L', tiff.read(4))[0]
    read_ifd_tag_data(tiff, info, ifd)
    ifdList.append(ifd)
    return ifd['nextifd']


def read_ifd_tag_data(tiff, info, ifd):
    """
    Read data from tags; read subifds.

    :param tiff: the open tiff file object.
    :param info: the total result structure.  Used to track offset locations
        and contains big endian and bigtiff flags.
    :param ifd: the ifd record to get data for.
    """
    bom = info['endianPack']
    for tag, taginfo in ifd['tags'].items():
        typesize = tiffDatatypes[taginfo['type']]['size']
        pos = taginfo.get('offset', taginfo['datapos'])
        tiff.seek(pos)
        rawdata = tiff.read(taginfo['count'] * typesize)
        if tiffDatatypes[taginfo['type']]['pack']:
            taginfo['data'] = list(struct.unpack(
                bom + tiffDatatypes[taginfo['type']]['pack'] * taginfo['count'], rawdata))
        elif tiffDatatypes[taginfo['type']]['name'] == 'ASCII':
            taginfo['data'] = rawdata.rstrip(b'\x00').decode()
        else:
            taginfo['data'] = rawdata
        if tag in offsetTagTable:
            if tag == SUBIFD_TAG:
                ifd['subifds'] = []
                tiff.seek(pos)
                subifdOffsets = struct.unpack(
                    bom + ('Q' if info['bigtiff'] else 'L') * taginfo['count'],
                    tiff.read(taginfo['count'] * typesize))
                for subifdOffset in subifdOffsets:
                    subifdRecord = []
                    ifd['subfds'].push(subifdRecord)
                    nextifd = subifdOffset
                    while nextifd:
                        nextifd = read_ifd(tiff, info, nextifd, subifdRecord)


def tiff_info(info):
    """
    Print the tiff information.

    :param info: info as extracted from a tiff file.
    """
    # TODO refactor this to print things nicely.  We need a table of tag names
    # and associated enums or flags.  Long data series should be truncated on
    # request.
    import yaml

    print(yaml.dump(info))


def tiff_write(ifds, path, bigEndian=None, bigtiff=None, allowExisting=False):
    """
    Write a tiff file based on data in a list of ifds.

    :param ifds: either a list of ifds, a single ifd record, or a read_tiff
        info record.
    :param path: output path.
    :param bigEndian: True for big endian, False for little endian, None for
        use the endian set in the first ifd.
    :param bigtiff: True for bigtiff, False for small tiff, None for use the
        bigtiff value in the first ifd.  If the small tiff is started and the
        file exceeds 4Gb, it is rewritten as bigtiff.  Note that this doesn't
        just convert to bigtiff, but actually rewrites the file to avoid
        unaccounted bytes in the file.
    :param allowExisting: if False, raise an error if the path already exists.
    """
    if isinstance(ifds, dict):
        bigEndian = ifds.get('bigEndian') if bigEndian is None else bigEndian
        bigtiff = ifds.get('bigtiff') if bigtiff is None else bigtiff
        ifds = ifds.get('ifds', [ifds])
    bigEndian = ifds[0].get('bigEndian', False) if bigEndian is None else bigEndian
    bigtiff = ifds[0].get('bigtiff', False) if bigtiff is None else bigtiff
    if not allowExisting and os.path.exists(path):
        raise Exception('File already exists')
    rewriteBigtiff = False
    with open(path, 'wb') as dest:
        bom = '>' if bigEndian else '<'
        header = b'II' if not bigEndian else b'MM'
        if bigtiff:
            header += struct.pack(bom + 'HHHQ', 0x2B, 8, 0, 0)
            ifdPtr = len(header) - 8
        else:
            header += struct.pack(bom + 'HL', 0x2A, 0)
            ifdPtr = len(header) - 4
        dest.write(header)
        for ifd in ifds:
            ifdPtr = write_ifd(dest, bom, bigtiff, ifd, ifdPtr)
            if not bigtiff and dest.tell() >= 2**32:
                rewriteBigtiff = True
                break
    if rewriteBigtiff:
        os.unlink(path)
        tiff_write(ifds, path, bigEndian, True)


def write_ifd(dest, bom, bigtiff, ifd, ifdPtr):
    """
    Write an IFD to a TIFF file.  This copies iamge data from other tiff files.

    :param dest: the open file handle to write.
    :param bom: eithter '<' or '>' for using struct to encode values based on
        endian.
    :param bigtiff: True if this is a bigtiff.
    :param ifd: The ifd record.  This requires the tags dictionary and the
        path value.
    :param ifdPtr: a location to write the value of this ifd's start.
    :return: the ifdPtr for the next ifd that could be written.
    """
    ptrpack = 'Q' if bigtiff else 'L'
    tagdatalen = 8 if bigtiff else 4
    dest.seek(0, os.SEEK_END)
    ifdrecord = struct.pack(bom + ('Q' if bigtiff else 'H'), len(ifd['tags']))
    subifdPtr = None
    with open(ifd['path'], 'rb') as src:
        for tag, taginfo in sorted(ifd['tags'].items()):
            data = taginfo['data']
            if tag == SUBIFD_TAG:
                if not len(ifd.get('subifds', [])):
                    continue
                data = [0] * len(ifd['subifds'])
                taginfo = taginfo.copy()
                taginfo['type'] = 18 if bigtiff else 13
            count = len(data)
            if tag in offsetTagByteCounts:
                data = write_tag_data(
                    dest, src, data, ifd['tags'][offsetTagByteCounts[tag]]['data'])
            elif tag in offsetTagByteCounts:
                data = write_tag_data(
                    dest, src, data, [ifd['tags'][offsetTagLengths[tag]]] * count)
            if tiffDatatypes[taginfo['type']]['pack']:
                pack = tiffDatatypes[taginfo['type']]['pack']
                count //= len(pack)
                data = struct.pack(bom + pack * count, *data)
            elif tiffDatatypes[taginfo['type']]['name'] == 'ASCII':
                data = data.encode() + b'\x00'
                count = len(data)
            else:
                data = taginfo['data']
            tagrecord = struct.pack(bom + 'HH' + ptrpack, tag, taginfo['type'], count)
            if len(data) <= tagdatalen:
                if tag == SUBIFD_TAG:
                    subifdPtr = -(len(ifdrecord) + len(tagrecord))
                tagrecord += data + b'\x00' * (tagdatalen - len(data))
            else:
                if tag == SUBIFD_TAG:
                    subifdPtr = dest.tell()
                tagrecord += struct.pack(bom + ptrpack, dest.tell())
                dest.write(data)
            ifdrecord += tagrecord
    pos = dest.tell()
    dest.seek(ifdPtr)
    dest.write(struct.pack(bom + ptrpack, pos))
    dest.seek(0, os.SEEK_END)
    dest.write(ifdrecord)
    nextifdPtr = dest.tell()
    dest.write(struct.pack(bom + ptrpack, 0))
    if subifdPtr is not None:
        if subifdPtr < 0:
            subifdPtr = pos + (-subifdPtr)
        for subifd in ifd['subifds']:
            write_ifd(dest, bom, bigtiff, subifd, subifdPtr)
            subifdPtr += tagdatalen
    return nextifdPtr


def write_tag_data(dest, src, offsets, lengths):
    """
    Copy data from a source tiff to a destination tiff, return a list of
    offsets where data was written.

    :param dest: the destination file, opened to the location to write.
    :param src: the source file.
    :param offsets: an array of offsets where data will be copied from.
    :param lengths: an array of lengths to copy from each offset.
    :return: the offsets in the destination file corresponding to the data
        copied.
    """
    destOffsets = []
    if len(offsets) != len(lengths):
        raise Exception('Offsets and byte counts do not correspond.')
    for idx, offset in enumerate(offsets):
        src.seek(offset)
        destOffsets.append(dest.tell())
        length = lengths[idx]
        while length:
            data = src.read(min(length, COPY_CHUNKSIZE))
            dest.write(data)
            length -= len(data)
    return destOffsets


def name_to_datatype(name):
    """
    Convert a data name to a number.  Case doesn't matter.

    :param name: a string to convert.
    :returns: a datatype number or None if unknown.
    """
    upperName = name.upper().replace('-', '_').replace(' ', '_')
    for datatype, typeinfo in tiffDatatypes.items():
        if upperName == typeinfo['name']:
            return datatype
    return None


def name_to_tag(name):
    """
    Convert a tag name to a number.  Case doesn't matter.

    :param name: a string to convert.
    :returns: a tag number or None if unknown.
    """
    upperName = name.upper().replace('-', '_').replace(' ', '_')
    for tag, taginfo in TiffTags.items():
        if upperName == taginfo['name']:
            return tag
    return None


def tiff_concat(args):
    """
    Concatenate a set of tiff files.

    :param args: a namespace with:
        output: the output path
        sources: a list of input paths
    """
    ifds = []
    for path in args.source:
        nextInfo = read_tiff(path)
        if args.verbose >= 3:
            tiff_info(nextInfo)
        ifds.extend(nextInfo['ifds'])
    tiff_write(ifds, args.output, allowExisting=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Concatenate multiple tiff files.  This also strips all '
        'unused data from the resultant file.')
    parser.add_argument(
        'output', help='Output file.')
    parser.add_argument(
        'source', nargs='+', help='Source files to concatenate.')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    args = parser.parse_args()
    if args.verbose >= 2:
        print('Parsed arguments: %r' % args)
    tiff_concat(args)
