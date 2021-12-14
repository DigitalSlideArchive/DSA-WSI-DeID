import concurrent.futures

from girder import logger
from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.user import User
from girder_jobs.models.job import Job, JobStatus

from . import config
from .constants import PluginSettings
from .process import get_image_text, get_standard_redactions


def start_ocr_item_job(job):
    Job().updateJob(job, log=f'Job {job.get("title")} started\n', status=JobStatus.RUNNING)
    job_args = job.get('args', None)
    if job_args is None:
        Job().updateJob(
            job,
            log='Expected a Girder item as an argument\n',
            status=JobStatus.ERROR
        )
        return
    item = job_args[0]
    try:
        label_text = get_image_text(item)
        status = JobStatus.SUCCESS
    except Exception as e:
        message = f'Attempting to find label text for file {item["name"]} resulted in {str(e)}.'
        status = JobStatus.ERROR
    if status == JobStatus.SUCCESS and len(label_text) > 0:
        message = f'Found label text for file {item["name"]}: {label_text}.\n',
    else:
        message = f'Could not find label text for file {item["name"]}\n'
    Job().updateJob(job, log=message, status=status)


def get_label_text_for_item(itemId, job):
    item = Item().load(itemId, force=True)
    Job().updateJob(job, log=f'Finding label text for file: {item["name"]}.\n')
    try:
        label_text = get_image_text(item)
        if len(label_text) > 0:
            message = f'Found label text for file {item["name"]}: {label_text}.\n'
        else:
            message = f'Could not find label text for file {item["name"]}.\n'
        Job().updateJob(job, log=message)
        return label_text
    except Exception as e:
        Job().updateJob(job, log=f'Failed to process file {item["name"]}; {e}\n')
        return {}


def start_ocr_batch_job(job):
    """
    Function to be run for girder jobs of type wsi_deid.batch_ocr. Jobs using this function
    should include a list of girder item ids as an argument.

    :param job: A girder job
    """
    Job().updateJob(
        job,
        log='Starting batch job to find label text on items.\n',
        status=JobStatus.RUNNING
    )
    job_args = job.get('args', None)
    if job_args is None:
        Job().updateJob(
            job,
            log='Expected a list of girder items as an argument.\n',
            status=JobStatus.ERROR
        )
        return
    itemIds = job_args[0]
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


def find_best_match(matches):
    minimumMatchCount = 1
    currentMatches = matches.copy()
    while len(currentMatches) > 1:
        minimumMatchCount += 1
        currentMatches = [
            match for match in currentMatches if match['matchedWordCount'] >= minimumMatchCount
        ]
    if len(currentMatches) == 1:
        return currentMatches[0].get('itemId', None)
    return None


def match_images_to_upload_data(imageIdsToItems, uploadInfo, userId, job):
    ingestFolderId = Setting().get(PluginSettings.HUI_INGEST_FOLDER)
    ingestFolder = Folder().load(ingestFolderId, force=True, exc=True)
    user = User().load(userId, force=True)
    for imageId, possibleMatches in imageIdsToItems.items():
        tokenId = uploadInfo[imageId]['TokenID']
        bestMatch = find_best_match(possibleMatches)
        if not bestMatch:
            # continue for now, might be worth updating the item metadata
            if len(possibleMatches) == 0:
                message = f'No items could be matched via OCR with ImageID {imageId}.\n'
            else:
                message = f'More than one item matched via OCR with ImageID {imageId}.\n'
            Job().updateJob(job, log=message)
            continue
        item = Item().load(bestMatch, force=True)
        parentFolder = Folder().findOne({'name': tokenId, 'parentId': ingestFolder['_id']})
        if not parentFolder:
            parentFolder = Folder().createFolder(ingestFolder, tokenId, creator=user)
        newImageName = f'{imageId}.{item["name"].split(".")[-1]}'
        Job().updateJob(
            job,
            log=f'Copied item {item["name"]} to folder {parentFolder["name"]} as {newImageName}\n'
        )
        item['name'] = newImageName
        item = Item().move(item, parentFolder)
        redactList = get_standard_redactions(item, imageId)
        itemMetadata = {
            'deidUpload': uploadInfo[imageId]['fields'],
            'redactList': redactList,
        }
        Item().setMetadata(item, itemMetadata)


def associate_unfiled_images(job):
    """
    Function to be run for girder jobs of type wsi_deid.associate_unfiled. Jobs using this function
    should include a list of girder item ids as the first argument, and associated data from the
    import spreadsheet as the second argument.

    :param job: a girder job
    """
    Job().updateJob(
        job,
        log='Starting job to associate unfiled images with upload data.\n',
        status=JobStatus.RUNNING
    )
    job_args = job.get('args', None)
    if job_args is None or len(job_args) != 2:
        Job().updateJob(
            job,
            log='Expected a list of girder items and upload information as arguments.\n',
            status=JobStatus.ERROR
        )
        return
    itemIds = job_args[0]
    uploadInfo = job_args[1]
    try:
        rowToImageMatches = {}
        for key in list(uploadInfo):
            rowToImageMatches[key] = []
        # Without concurrent.futures, this is:
        # for itemId in itemIds:
        #     label_text = get_label_text_for_item(itemId, job)
        label_text_list = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for itemId in itemIds:
                futures.append(executor.submit(get_label_text_for_item, itemId, job))
            for future in futures:
                label_text_list.append(future.result())
        for idx, itemId in enumerate(itemIds):
            label_text = label_text_list[idx]
            # And, without concurrent futures, the code resumes here
            item = Item().load(itemId, force=True)
            imageToRowMatches = []
            # Don't rely on matching tokens that are only 1 character in length
            label_text = [word for word in label_text if len(word) > 1]
            if len(label_text) > 0:
                for key, value in uploadInfo.items():
                    # key is the TokenID from the import spreadsheet, and value is associated info
                    matchTextFields = config.getConfig('import_text_association_columns')
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
        match_images_to_upload_data(rowToImageMatches, uploadInfo, job['userId'], job)
        Job().updateJob(job, log='Finished batch job.\n', status=JobStatus.SUCCESS)
    except Exception as e:
        logger.exception('Job failed')
        Job().updateJob(
            job,
            log=f'Job failed with the following exceptions: {str(e)}.\n',
            status=JobStatus.ERROR,
        )
