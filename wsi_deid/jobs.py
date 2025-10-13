import concurrent.futures
import os

from girder import logger
from girder.models.item import Item
from girder.models.user import User
from girder.utility.progress import noProgress
from girder_jobs.models.job import Job, JobStatus

from . import config, matching_api
from .constants import TokenOnlyPrefix
from .process import get_image_barcode, get_image_name, get_image_text, refile_image


def start_ocr_item_job(job):
    Job().updateJob(job, log=f'Job {job.get("title")} started\n', status=JobStatus.RUNNING)
    job_args = job.get('args', None)
    if job_args is None:
        Job().updateJob(
            job,
            log='Expected a Girder item as an argument\n',
            status=JobStatus.ERROR,
        )
        return
    item = job_args[0]
    try:
        label_barcode = get_image_barcode(item)
        label_text = get_image_text(item)
        status = JobStatus.SUCCESS
    except Exception as e:
        message = f'Attempting to find label text for file {item["name"]} resulted in {str(e)}.'
        status = JobStatus.ERROR
    if status == JobStatus.SUCCESS and len(label_barcode) > 0:
        message = f'Found label barcode for file {item["name"]}: {label_barcode}.\n'
    if status == JobStatus.SUCCESS and len(label_text) > 0:
        message = f'Found label text for file {item["name"]}: {label_text}.\n'
    else:
        message = f'Could not find label text for file {item["name"]}\n'
    Job().updateJob(job, log=message, status=status)


def get_label_text_for_item(itemId, job):
    item = Item().load(itemId, force=True)
    if item is None:
        return
    Job().updateJob(job, log=f'Finding label text for file: {item["name"]}.\n')
    try:
        label_barcode = get_image_barcode(item)
        if len(label_barcode) > 0:
            message = f'Found label barcode for file {item["name"]}: {label_barcode}.\n'
            Job().updateJob(job, log=message)
        label_text = get_image_text(item)
        if len(label_text) > 0:
            message = f'Found label text for file {item["name"]}: {label_text}.\n'
        else:
            message = f'Could not find label text for file {item["name"]}.\n'
        Job().updateJob(job, log=message)
        return (label_text, label_barcode)
    except Exception as e:
        Job().updateJob(job, log=f'Failed to process file {item["name"]}; {e}\n')
        return ({}, {})


def start_ocr_batch_job(job):
    """
    Function to be run for girder jobs of type wsi_deid.batch_ocr. Jobs using this function
    should include a list of girder item ids as an argument.

    :param job: A girder job
    """
    Job().updateJob(
        job,
        log='Starting batch job to find label text on items.\n',
        status=JobStatus.RUNNING,
    )
    job_args = job.get('args', None)
    if job_args is None:
        Job().updateJob(
            job,
            log='Expected a list of girder items as an argument.\n',
            status=JobStatus.ERROR,
        )
        return
    itemIds = job_args
    try:
        for itemId in itemIds:
            get_label_text_for_item(itemId, job)
        Job().updateJob(job, log='Finished batch job.\n', status=JobStatus.SUCCESS)
    except Exception as e:
        Job().updateJob(
            job,
            log=f'Batch job failed with the following exception: {str(e)}.\n',
            status=JobStatus.ERROR,
        )


def find_best_match(matches, multipleAllowed):
    minimumMatchCount = 1
    currentMatches = [match for match in matches if match.get('itemId')]
    while len(currentMatches) > 1 and not multipleAllowed:
        minimumMatchCount += 1
        currentMatches = [
            match for match in currentMatches if match['matchedWordCount'] >= minimumMatchCount
        ]
    if len(currentMatches):
        return [match.get('itemId') for match in currentMatches]
    return None


def match_images_to_upload_data(imageIdsToItems, uploadInfo, userId, job, reportInfo, itemIds):
    folderNameField = config.getConfig('folder_name_field', 'TokenID')
    user = User().load(userId, force=True)
    remainingImages = set(itemIds)
    for imageId, possibleMatches in imageIdsToItems.items():
        tokenId = uploadInfo[imageId][folderNameField]
        multipleAllowed = imageId.startswith(TokenOnlyPrefix)
        displayName = tokenId if imageId.startswith(TokenOnlyPrefix) else imageId
        bestMatch = find_best_match(possibleMatches, multipleAllowed)
        if not bestMatch:
            if len(possibleMatches) == 0:
                message = f'No items could be matched via OCR with ImageID {displayName}.\n'
            else:
                message = f'More than one item matched via OCR with ImageID {displayName}.\n'
            Job().updateJob(job, log=message)
            continue
        for match in bestMatch:
            item = Item().load(match, force=True)
            oldName = item['name']
            # Do we need to apply the name and folder templates here?
            newFolderName = get_image_name(tokenId, uploadInfo[imageId], item, True)
            newNameRoot = get_image_name(tokenId, uploadInfo[imageId], item)
            item = refile_image(
                item, user, newFolderName, TokenOnlyPrefix + newNameRoot,
                {TokenOnlyPrefix + newNameRoot: uploadInfo})
            # item = refile_image(item, user, tokenId, imageId, uploadInfo)
            remainingImages.discard(item['_id'])
            if uploadInfo.get(imageId, {}).get('fields', None):
                addToReport(reportInfo, item, {
                    'record': uploadInfo[imageId], 'status': 'ocrmatch'})
            else:
                addToReport(reportInfo, item, {'status': 'ocrmatch'})
            Job().updateJob(
                job,
                log=f'Moved item {oldName} to folder {tokenId} as {item["name"]}\n',
            )
    return remainingImages


def match_images_via_api(imageIds, userId, job, reportInfo):
    user = User().load(userId, force=True)
    remainingImages = set()
    apisearch = matching_api.APISearch()
    for imageId in imageIds:
        item = Item().load(imageId, force=True)
        if item is None:
            continue
        if not len(item.get('meta', {}).get('label_ocr', {})) and not len(
                item.get('meta', {}).get('label_barcodes', {})):
            remainingImages.add(imageId)
            continue
        result = []
        if 'label_barcode' in item['meta']:
            result = apisearch.lookupBarcodeRecord(item['meta']['label_barcode'])
        if len(result) == 0 and 'label_ocr' in item['meta']:
            result = apisearch.lookupOcrRecord(item['meta']['label_ocr'])
        if len(result) != 1 or not result[0].get('token_id'):
            Job().updateJob(
                job,
                log=f'Failed to look up item {item["name"]} from API\n',
            )
            remainingImages.add(imageId)
            continue
        tokenId = result[0]['token_id']
        info = {'fields': result[0].get('tumors')[0]}
        oldName = item['name']
        newFolderName = get_image_name(tokenId, info, item, True)
        newNameRoot = get_image_name(tokenId, info, item)
        item = refile_image(
            item, user, newFolderName, TokenOnlyPrefix + newNameRoot,
            {TokenOnlyPrefix + newNameRoot: info})
        Job().updateJob(
            job,
            log=f'Moved item {oldName} to folder {newFolderName} as '
            f'{item["name"]} based on api lookup\n',
        )
    return remainingImages


def addToReport(reportInfo, item, data):
    """
    Add additional data to a line in a report about a specific item.

    :param reportInfo: a dictionary where 'files' is a list of records that
        might be updated.
    :param item: the item that should be updated in the report.
    :param data: a dictionary of information used to update a line in the
        report.
    """
    try:
        file = next(Item().childFiles(item, limit=1))
    except Exception:
        return
    report = None
    for entry in reportInfo['files']:
        if entry['path'] == file.get('path', file.get('s3Key')):
            report = entry
            break
    if not report:
        return
    report.update(data)


def associate_unfiled_images(job):  # noqa
    """
    Function to be run for girder jobs of type wsi_deid.associate_unfiled. Jobs using this function
    should include a list of girder item ids as the first argument, and associated data from the
    import spreadsheet as the second argument.

    :param job: a girder job
    """
    from .import_export import importReport

    Job().updateJob(
        job,
        log='Starting job to associate unfiled images with upload data.\n',
        status=JobStatus.RUNNING,
    )
    job_args = job.get('args', None)
    if job_args is None or len(job_args) != 3:
        Job().updateJob(
            job,
            log='Expected a list of girder items and upload information as arguments.\n',
            status=JobStatus.ERROR,
        )
        return
    itemIds, uploadInfo, reportInfo = job_args
    try:
        rowToImageMatches = {}
        for key in list(uploadInfo):
            rowToImageMatches[key] = []
        # Without concurrent.futures, this is:
        # for itemId in itemIds:
        #     label_text = get_label_text_for_item(itemId, job)
        label_text_list = []
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, os.cpu_count() // 2)) as executor:
            futures = []
            for itemId in itemIds:
                futures.append(executor.submit(get_label_text_for_item, itemId, job))
            for future in futures:
                label_text_list.append(future.result())
        for idx, itemId in enumerate(itemIds):
            if label_text_list[idx] is None:
                continue
            label_text, barcode_text = label_text_list[idx]
            # And, without concurrent futures, the code resumes here
            # TODO: do something with the barcode for matching
            item = Item().load(itemId, force=True)
            imageToRowMatches = []
            addToReport(reportInfo, item, {'label': ' '.join(
                [word for conf, word in sorted([
                    (-entry['average_confidence'], word)
                    for word, entry in label_text.items() if len(word) > 1])])})
            addToReport(reportInfo, item, {'barcode': '|'.join(barcode_text)})
            # Don't rely on matching tokens that are only 1 character in length
            label_text = [word for word in label_text if len(word) > 1]
            for barcode in barcode_text:
                for chunk in barcode.split(';'):
                    if len(chunk.strip()):
                        for subchunk in chunk.strip().split():
                            if subchunk not in label_text:
                                label_text.append(subchunk)
            if len(label_text) > 0:
                for key, value in uploadInfo.items():
                    # key is the TokenID from the import spreadsheet, and value is associated info
                    matchTextFields = config.getConfig('import_text_association_columns') or []
                    uploadFields = value.get('fields', {})
                    text_to_match = [
                        uploadFields[field] for field in matchTextFields if field in uploadFields]
                    matchedWordCount = len(set(text_to_match) & set(label_text))
                    logger.info('Checking matches for %s: %r to %r: %d' % (
                        key, set(text_to_match), set(label_text), matchedWordCount))
                    if matchedWordCount > 0:
                        rowToImageMatches[key].append({
                            'itemId': item['_id'],
                            'matchedWordCount': matchedWordCount,
                        })
                        imageToRowMatches.append(key)
            if len(imageToRowMatches) > 0:
                message = f'{item["name"]} matched to ImageIDs {imageToRowMatches}.\n'
            else:
                message = f'Unable to find a match for {item["name"]}.\n'
            Job().updateJob(job, message)
        unmatchedImageIds = match_images_to_upload_data(
            rowToImageMatches, uploadInfo, job['userId'], job, reportInfo, itemIds)
        unmatchedImageIds = match_images_via_api(unmatchedImageIds, job['userId'], job, reportInfo)
        Job().updateJob(job, log='Finished batch job.\n', status=JobStatus.SUCCESS)
        user = User().load(job['userId'], force=True)
        importReport(noProgress, reportInfo['files'], reportInfo['excel'],
                     user, reportInfo['importPath'], 'OCR')
    except Exception as e:
        logger.exception('Job failed')
        Job().updateJob(
            job,
            log=f'Job failed with the following exceptions: {str(e)}.\n',
            status=JobStatus.ERROR,
        )
