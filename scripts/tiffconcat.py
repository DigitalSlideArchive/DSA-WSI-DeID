#!/usr/bin/env python3

import argparse
import os
import pprint
import shutil
import struct

offsetTagTable = {
    0x111: 'StripOffsets',
    0x120: 'FreeOffsets',
    0x144: 'TileOffsets',
    0x14a: 'SubIFD',  # data is a list of offsets
    0x207: 'JPEGQTables',
    0x208: 'JPEGDCTables',
    0x209: 'JPEGACTables',
}
datatypeSize = {
    1: 1,  # unsigned byte
    2: 1,  # ASCII string; must be null-terminated
    3: 2,  # short
    4: 4,  # long
    5: 8,  # rational (two longs)
    6: 1,  # signed byte
    7: 1,  # undefined byte
    8: 2,  # signed short
    9: 4,  # signed long
    10: 8,  # signed rational (two longs)
    11: 4,  # single float
    12: 8,  # double float
    13: 4,  # IFD (unsigned long)
    16: 8,  # longlong
    17: 8,  # signed longlong
    18: 8,  # IFD8 (unsigned longlong)
}


def read_tiff(path):
    info = {
        'path': path,
        'size': os.path.getsize(path),
        'ifds': [],
        'offsets4': [],
        'offsets8': [],
    }
    with open(path, 'rb') as tiff:
        header = tiff.read(4)
        info['header'] = header
        if header not in (b'II\x2a\x00', b'MM\x00\x2a', b'II\x2b\x00', 'MM\x00\x2b'):
            raise Exception('Not a known tiff header for %s' % path)
        info['bigEndian'] = header[:2] == b'MM'
        endianMark = '>' if info['bigEndian'] else '<'
        info['bigtiff'] = b'\x2b' in header[2:4]
        if info['bigtiff']:
            info['offsets8'].append(tiff.tell() + 4)
            offsetsize, zero, nextifd = struct.unpack(endianMark + 'HHQ', tiff.read(12))
            if offsetsize != 8 or zero != 0:
                raise Exception('Unexpected offset size')
        else:
            info['offsets4'].append(tiff.tell())
            nextifd = struct.unpack(endianMark + 'L', tiff.read(4))[0]
        info['firstifd'] = nextifd
        while nextifd:
            nextifd = read_ifd(tiff, info, nextifd, info['ifds'])
    return info


def read_ifd(tiff, info, ifdOffset, ifdList):
    endianMark = '>' if info['bigEndian'] else '<'
    tiff.seek(ifdOffset)
    ifd = {'offset': ifdOffset, 'tags': []}
    if info['bigtiff']:
        ifd['entries'] = struct.unpack(endianMark + 'Q', tiff.read(8))[0]
    else:
        ifd['entries'] = struct.unpack(endianMark + 'H', tiff.read(2))[0]
    for entry in range(ifd['entries']):
        if info['bigtiff']:
            tag, datatype, count, data = struct.unpack(endianMark + 'HHQQ', tiff.read(20))
            datalen = 8
        else:
            tag, datatype, count, data = struct.unpack(endianMark + 'HHLL', tiff.read(12))
            datalen = 4
        taginfo = {
            'tag': tag,
            'type': datatype,
            'count': count,
            'datapos': tiff.tell() - datalen,
            'datalen': datalen,
            'typesize': datatypeSize[datatype]
        }
        if count * taginfo['typesize'] > datalen:
            taginfo['offset'] = data
            info['offsets8' if info['bigtiff'] else 'offsets4'].append(taginfo['datapos'])
        else:
            taginfo['data'] = data
        ifd['tags'].append(taginfo)
    ifd['nextifdRecord'] = tiff.tell()
    if info['bigtiff']:
        ifd['nextifd'] = struct.unpack(endianMark + 'Q', tiff.read(8))[0]
    else:
        ifd['nextifd'] = struct.unpack(endianMark + 'L', tiff.read(4))[0]
    for taginfo in ifd['tags']:
        if taginfo['tag'] in offsetTagTable:
            pos = taginfo.get('offset', taginfo['datapos'])
            for record in range(taginfo['count']):
                if taginfo['typesize'] not in (4, 8):
                    raise Exception('Surprizing type for an offset')
                info['offsets4' if taginfo['typesize'] == 4 else 'offsets8'].append(
                    pos + record * taginfo['typesize'])
            if offsetTagTable[taginfo['tag']] == 'SubIFD':
                ifd['subifds'] = []
                tiff.seek(pos)
                subifdOffsets = struct.unpack(
                    endianMark + ('Q' if info['bigtiff'] else 'L') * taginfo['count'],
                    tiff.read(taginfo['count'] * taginfo['typesize']))
                for subifdOffset in subifdOffsets:
                    subifdRecord = []
                    ifd['subfds'].push(subifdRecord)
                    nextifd = subifdOffset
                    while nextifd:
                        nextifd = read_ifd(tiff, info, nextifd, subifdRecord)
    ifdList.append(ifd)
    return ifd['nextifd']


def tiff_concat(args):  # noqa
    mainInfo = read_tiff(args.source)
    if args.verbose >= 3:
        pprint.pprint(mainInfo)
    toAdd = []
    for path in args.addtiff:
        nextInfo = read_tiff(path)
        if args.verbose >= 3:
            pprint.pprint(nextInfo)
        if nextInfo['bigEndian'] != mainInfo['bigEndian']:
            raise Exception('Endians do not match')
        if nextInfo['bigtiff'] != mainInfo['bigtiff']:
            raise Exception('bigtiff status does not match')
        toAdd.append(nextInfo)
    endianMark = '>' if mainInfo['bigEndian'] else '<'
    output = args.source
    if getattr(args, 'output'):
        if args.verbose >= 1:
            print('Copying to %s' % args.output)
        shutil.copy2(args.source, args.output)
        output = args.output
    for nextInfo in toAdd:
        mainSize = os.path.getsize(output)
        if args.verbose >= 1:
            print('Concatenating %s' % nextInfo['path'])
        with open(output, 'r+b') as tiff:
            tiff.seek(0, os.SEEK_END)
            with open(nextInfo['path'], 'rb') as concat:
                chunkSize = 65536
                while True:
                    chunk = concat.read(chunkSize)
                    if not len(chunk):
                        break
                    tiff.write(chunk)
            if args.verbose >= 2:
                print('Adjusting offsets')
            # Link IFDs
            tiff.seek(mainInfo['ifds'][-1]['nextifdRecord'])
            tiff.write(struct.pack(
                endianMark + ('Q' if mainInfo['bigtiff'] else 'L'),
                mainSize + nextInfo['firstifd']))
            for key, mark, datalen in [('offsets4', 'L', 4), ('offsets8', 'Q', 8)]:
                for offset in nextInfo[key]:
                    tiff.seek(mainSize + offset)
                    value = struct.unpack(endianMark + mark, tiff.read(datalen))[0]
                    value += mainSize
                    tiff.seek(mainSize + offset)
                    tiff.write(struct.pack(endianMark + mark, value))
        # Instead of rereading this, we could concatenate the IFD entries in
        # mainInfo, adjusting the offset of the last nextifdRecord
        mainInfo = read_tiff(output)
        if args.verbose >= 3:
            pprint.pprint(mainInfo)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Concatenate multiple tiff files.  The source file is '
        'modified unless an output file is specified.  All files must be the '
        'same endian and all either bigtiff or non-bigtiff.')
    parser.add_argument(
        'source', help='Source file.  This is modified unless an output file is specified.')
    parser.add_argument(
        'addtiff', nargs='+',
        help='Additional tiff files to concatenate to the source file.')
    parser.add_argument(
        '--output', '-o', help='Output file.  If not specified, the source file modified.')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    args = parser.parse_args()
    if args.verbose >= 2:
        print('Parsed arguments: %r' % args)
    tiff_concat(args)
