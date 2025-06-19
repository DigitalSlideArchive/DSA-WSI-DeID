#!/usr/bin/env python

import datetime
import os
import re

import girder_client
from slicer_cli_web import CLIArgumentParser


def ensureResourcePath(gc, path, public=False, model=None):
    """
    Ensure that a resource path exists in Girder.  If it does not exist,
    create it.

    :param gc: a girder client reference with permissions to create the
        resource.
    :param path: a girder resource path (e.g.,
        /collection/sample/folder1/folder2).
    :param public: True to mark any created folders or collections public.
    :param model: the model type of the final element of the path, if known.
        If None, this is assumed to be 'folder' unless the path it short
        enough it must be 'collection' or 'user'.
    :return: a girder document for the path.
    """
    try:
        resource = gc.get('resource/lookup', parameters={'path': path})
        return resource
    except Exception:
        pass
    pathparts = path.rstrip('/').split('/')
    if len(pathparts) == 3:
        if pathparts[1] == 'collection':
            return gc.createCollection(pathparts[2], '', public=public)
        else:
            msg = f'Cannot create a base {pathparts[1]} resource'
            raise Exception(msg)
    parentpath = os.path.dirname(path)
    parent = ensureResourcePath(gc, parentpath, public, 'folder' if model != 'file' else 'item')
    if model == 'file':
        msg = 'Cannot create a file resource'
        raise Exception(msg)
    elif model == 'item':
        return gc.createFolder(parent['_id'], pathparts[-1])
    else:
        return gc.createFolder(parent['_id'], pathparts[-1],
                               parentType=parent['_modelType'], public=public)


def select_image(args, gc, selected, image):
    """
    Here we could download the image, get a reduced resolution in a known
    format via getRegion, or do anything else needed to decide.  For our
    sample algorithm, we:
    (a) assume the parent folder is the case id
    (b) if there is a tumor record number in the deidUpload metadata it is a
    tumor.
    (c) our quality is strictly the image size (bigger is better)
    (d) our "satisfactory" metric is if the image is at least 20,000 pixels in
    each dimension.

    :param args: the selection algorithm arguments.
    :param gc: a girder client reference so we can query girder for more data.
    :param selected: a dictionary where we collect results and cache values.
    :param image: the girder image record that we are checking.
    """
    if image['folderId'] not in selected['folders']:
        selected['folders'][image['folderId']] = gc.getFolder(image['folderId'])
    case = selected['folders'][image['folderId']]['name']
    if case not in selected['cases']:
        selected['cases'][case] = {'images': 0, 'kept': 0, 'tumor': [], 'nontumor': []}
    caserec = selected['cases'][case]
    caserec['images'] += 1
    imageMeta = gc.get(f'item/{image["_id"]}/tiles')
    if args.satisfactory and (imageMeta['sizeX'] < 20000 or imageMeta['sizeY'] < 20000):
        return
    quality = imageMeta['sizeX'] * imageMeta['sizeY']
    tumor = image.get('meta', {}).get('deidUpload', {}).get('tumor_record_number')
    casekey = 'tumor' if tumor else 'nontumor'
    keep = args.tumor if tumor else args.nontumor
    # Add our image to the keep list
    caserec[casekey].append((quality, image))
    # sort them so that the highest quality is first
    caserec[casekey].sort(reverse=True)
    # trim to keep no more than requested
    caserec[casekey][keep:] = []
    caserec['kept'] = len(caserec['tumor']) + len(caserec['nontumor'])


def main(args):  # noqa
    gc = girder_client.GirderClient(apiUrl=args.girderApiUrl)
    gc.token = args.girderToken
    if not args.source:
        args.source = gc.get('wsi_deid/settings')['histomicsui.finished_folder']
    print(args.source)
    images = []
    for item in gc.listItem(args.source, text='_recurse_:'):
        if item.get('largeImage'):
            images.append(item)
    print(f'Selecting from {len(images)} image{"s" if len(images) != 1 else ""}')
    selected = {'folders': {}, 'cases': {}}
    for image in images:
        select_image(args, gc, selected, image)
    print('Selection choices')
    for case in sorted(selected['cases']):
        caserec = selected['cases'][case]
        if not caserec['kept']:
            continue
        print(f'  case {case} {caserec["kept"]}/{caserec["images"]}')
        for key in ['nontumor', 'tumor']:
            for quality, img in caserec.get(key, {}):
                print(f'    {key:8s} {quality:10d}  {img["name"]}')
    if args.destination:
        dest = args.destination
        try:
            dest = re.sub(
                r'\{date:([^}]*)\}',
                lambda match: datetime.datetime.now().strftime(match.group(1)),
                dest)
        except Exception:
            print('Failed to expand date.')
        destination = ensureResourcePath(gc, dest, public=True)
        for case in sorted(selected['cases']):
            caserec = selected['cases'][case]
            if not caserec['kept']:
                continue
            casefolder = gc.createFolder(
                destination['_id'], case, parentType=destination['_modelType'], public=True)
            for key in ['nontumor', 'tumor']:
                for _, img in caserec.get(key, {}):
                    print(f'Copying {case}/{img["name"]}')
                    gc.post(f'item/{img["_id"]}/copy', parameters={
                        'folderId': casefolder['_id']})


if __name__ == '__main__':
    main(CLIArgumentParser().parse_args())
