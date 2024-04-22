import itertools
import json
import re

import requests


class APISearch:
    dateDOBRE = re.compile(
        r'^(?P<dob>(?:DOB(?:[:.]|)|))'
        r'(?P<month>[0-1]?\d)(?:[-_/.])(?P<day>[0-3]?\d)(?:[-_/.])(?P<year>(?:19|20|29|)\d\d)$')
    dateDOB2RE = re.compile(
        r'^(?P<dob>(?:DOB(?:[:.]|)|))'
        r'(?P<year>(?:19|20|29)\d\d)(?:[-_/.])(?P<month>[0-1]?\d)(?:[-_/.])(?P<day>[0-3]?\d)$')
    dateRE = re.compile(
        r'(?P<month>\d?\d)(?:[-_/.])(?P<day>\d?\d)(?:[-_/.])(?P<year>(?:19|20|)\d\d)$')
    date2RE = re.compile(
        r'(?P<year>(?:19|20|)\d\d)(?:[-_/.])(?P<month>[0-1]?\d)(?:[-_/.])(?P<day>\d?\d)$')
    nameRE = re.compile(r'^(?P<name>[a-zA-Z]{2,50})$')
    name1RE = re.compile(r'^(?P<name>[a-zA-Z][a-z]{1,49})\s*(?:[A-Z][a-zA-Z]{1,49})$')
    name2RE = re.compile(r'^(?:([a-zA-Z][a-z]{0,49}|\d))\s*(?P<name>[A-Z][a-z][a-zA-Z]{0,48})$')
    name3RE = re.compile(r'^(?P<name>[a-zA-Z]{2,50})(?:[-_/.])(?:[a-zA-Z]{2,50})$')
    name4RE = re.compile(r'^(?:[a-zA-Z]{2,50})(?:[-_/.])(?P<name>[a-zA-Z]{2,50})$')
    pathnumRE = re.compile(r'^(?P<pathnum>(?:\w{2,10}|\d{2,10})[-_/.](?:\w{2,10}|\d{2,10}))$')
    matchers = {
        'date_of_birth': {
            're': [dateDOBRE, dateDOB2RE],
            'format': lambda match: '%02d-%02d-%04d' % (
                int(match['month']),
                int(match['day']),
                int(re.sub('^29', '20', match['year']))
                if int(match['year']) > 100 else (int(match['year']) + 2000),
            ),
        },
        'date_of_service': {
            're': [dateRE, date2RE],
            'format': lambda match: '%02d-%02d-%04d' % (
                int(match['month']),
                int(match['day']),
                int(re.sub('^29', '20', match['year']))
                if int(match['year']) > 100 else (int(match['year']) + 2000),
            ),
        },
        'name_first': {
            're': [nameRE, name1RE, name2RE, name3RE, name4RE],
            'format': lambda match: match['name'],
            'skip': ['Hosp', 'dsoH', 'ctr', 'mc', 'jw'],
        },
        'name_last': {
            're': [nameRE, name1RE, name2RE, name3RE, name4RE],
            'format': lambda match: match['name'],
            'skip': ['Hosp', 'dsoH', 'ctr', 'mc', 'jw'],
        },
        'path_case_num': {
            're': [pathnumRE],
            'format': lambda match: re.sub(r'^5', 'S', re.sub(r'[_./]', '-', match['pathnum'])),
        },
    }

    apiMatchMethods = [
        {'path_case_num', 'name_last', 'name_first', 'date_of_birth'},
        {'path_case_num', 'name_last', 'name_first'},
        {'path_case_num', 'name_last', 'date_of_birth'},
        {'path_case_num', 'name_first', 'date_of_birth'},
        {'path_case_num', 'name_last', 'name_first', 'date_of_service'},
        {'name_last', 'name_first', 'date_of_birth'},
        {'path_case_num', 'name_last'},
        {'path_case_num', 'date_of_birth'},
    ]

    confidenceThreshold = 0.50

    def __init__(self, url=None, apikey=None, logger=None):
        """
        Initialize the class with the api url and key.
        """
        if logger is None:
            try:
                from girder import logger
            except Exception:
                import logging

                logger = logging.getLogger('matching_api')
                logger.setLevel(logging.DEBUG)
                logger.addHandler(logging.StreamHandler())
        self.logger = logger
        if url is None or apikey is None:
            try:
                from girder.models.setting import Setting

                from .constants import PluginSettings

                if not apikey and not url:
                    apikey = Setting().get(PluginSettings.WSI_DEID_DB_API_KEY)
                url = url or Setting().get(PluginSettings.WSI_DEID_DB_API_URL)
            except Exception:
                self.logger.exception('Failed to get API url and key')
        self.url = url
        self.apikey = apikey

    def addMatches(self, matches, matchkey, word):
        matches.setdefault(matchkey, [])
        matcherlist = self.matchers[matchkey]
        for matcher in matcherlist['re']:
            groups = matcher.match(word)
            if groups:
                value = matcherlist['format'](groups.groupdict())
                if value.lower() in [v.lower() for v in matcherlist.get('skip', [])]:
                    continue
                matches[matchkey].append({
                    'word': word,
                    'value': value})

    def getQueryList(self, words):
        matches = {key: [] for key in self.matchers}
        for word in words:
            for key in self.matchers:
                self.addMatches(matches, key, word)
        for matchlist in matches.values():
            matchlist.append(None)
        queries = []
        for values in itertools.product(*matches.values()):
            params = {}
            used = set()
            for k, v in zip(matches.keys(), values):
                if v is not None and (v['word'], v['value']) not in used:
                    params[k] = v['value']
                    used.add((v['word'], v['value']))
            if any(not len(apiset - set(params)) for apiset in self.apiMatchMethods):
                if params not in [entry[-1] for entry in queries]:
                    queries.append((-len(params), len(queries), params))
        queries = [entry[-1] for entry in sorted(queries)]
        return queries

    def getOCRQueryList(self, ocrRecord):
        # Sort the works by confidence and count, culling for confidence
        words = {e[-2]: e[-1] for e in sorted([
            (-v['average_confidence'], -v['count'], k, v)
            for k, v in ocrRecord.items()
            if v['average_confidence'] >= self.confidenceThreshold])}
        queries = self.getQueryList(words)
        self.logger.debug('OCR query list %r %r', ocrRecord, queries)
        return queries

    def lookupQuery(self, query):
        self.logger.info('Checking matching API for %r from %s', query, self.url)
        if not self.url or not self.apikey:
            return []
        headers = {
            'X-SEERDMS-API-Key': self.apikey,
            'Content-Type': 'application/json',
        }
        try:
            req = requests.post(self.url, headers=headers, data=json.dumps(query))
        except Exception:
            self.logger.exception('Failed to query API')
            return []
        return req.json()

    def lookupQueries(self, queryList):
        for query in queryList:
            result = self.lookupQuery(query)
            if len(result):
                self.logger.info('Found match from API for %r', query)
                return result
        return []

    def lookupOcrRecord(self, ocrRecord):
        queryList = self.getOCRQueryList(ocrRecord)
        return self.lookupQueries(queryList)

    def getBarcodeQueryList(self, barcodeRecord):
        queries = []
        for record in barcodeRecord:
            words = [val.strip() for val in record.split(';') if val.strip()]
            for query in self.getQueryList(words):
                if query not in queries:
                    queries.append(query)
        self.logger.debug('Barcode query list %r %r', barcodeRecord, queries)
        return queries

    def lookupBarcodeRecord(self, barcodeRecord):
        queryList = self.getBarcodeQueryList(barcodeRecord)
        return self.lookupQueries(queryList)
