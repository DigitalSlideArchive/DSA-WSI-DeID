import pytest

from wsi_deid import matching_api


@pytest.fixture
def api_search():
    return matching_api.APISearch('localhost:8080/matching/wsi', 'api-key')


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_api_search(api_search):
    ocr_record = {
        '0': {'count': 1, 'average_confidence': 0.9999516016140575},
        'DOB:01/01/2012': {'count': 1, 'average_confidence': 0.9976619567946853},
        'FizzBuzz': {'count': 1, 'average_confidence': 0.9804523125837243},
        '1': {'count': 2, 'average_confidence': 0.9459053159787807},
        'X11-1111': {'count': 1, 'average_confidence': 0.9429555019183363},
        '01/01/2017': {'count': 1, 'average_confidence': 0.9169495973518527},
        'Baz': {'count': 1, 'average_confidence': 0.647559972533129},
        '2': {'count': 2, 'average_confidence': 0.6162420787858203},
        'Bar': {'count': 1, 'average_confidence': 0.43514642854791696},
        '3': {'count': 3, 'average_confidence': 0.4339335586178012},
        'Foo': {'count': 1, 'average_confidence': 0.3054464843248889},
        'X': {'count': 1, 'average_confidence': 0.21402806451189438},
        'x0x0-XXX': {'count': 1, 'average_confidence': 0.19517887159795738},
        '4': {'count': 1, 'average_confidence': 0.06642707626467459},
    }
    queries = api_search.getOCRQueryList(ocr_record)

    # Ensure each query has enough data
    assert all(len(query) >= 2 for query in queries)

    # Ensure tokens with confidence < .5 aren't used for queries
    query_tokens_list = [list(query.values()) for query in queries]
    query_tokens = {token for sublist in query_tokens_list for token in sublist}
    assert len(query_tokens) == 7


match_name_cases = [
    ('FizzBuzz', ['Fizz', 'Buzz', 'FizzBuzz']),
    ('fizzBuzz', ['fizz', 'Buzz', 'fizzBuzz']),
    ('Fizz', ['Fizz']),
    ('fizz', ['fizz']),
    ('hosp', []),
]


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
@pytest.mark.parametrize('match_key', ['name_first', 'name_last'])
@pytest.mark.parametrize(('token', 'expected_values'), match_name_cases)
def test_api_search_add_matches_name(api_search, match_key, token, expected_values):
    matches = {key: [] for key in api_search.matchers}
    api_search.addMatches(matches, match_key, token)
    key_match_values = [item['value'] for item in matches[match_key]]
    assert all(value in expected_values for value in key_match_values)


expected_date = '01-01-2020'
expected_date_1920 = '01-01-1920'
match_dob_cases = [
    ('01/01/1920', expected_date_1920),
    ('1920/01/01', expected_date_1920),
    ('1920.01.01', expected_date_1920),
    ('1920-01-01', expected_date_1920),
    ('1920_01_01', expected_date_1920),
    ('1920_1_1', expected_date_1920),
    ('1920_01_1', expected_date_1920),
    ('1920_1_01', expected_date_1920),
    ('01/01/2020', expected_date),
    ('01.01.2020', expected_date),
    ('01_01_2020', expected_date),
    ('01-01-2020', expected_date),
    ('2020/01/01', expected_date),
    ('01/01/20', expected_date),
    ('1/1/20', expected_date),
    ('01/1/20', expected_date),
    ('1/01/20', expected_date),
    ('1/01/20', expected_date),
    ('DOB:01/01/20', expected_date),
    ('DOB.01/01/20', expected_date),
    ('DOB01/01/20', expected_date),
]


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
@pytest.mark.parametrize(('token', 'expected_value'), match_dob_cases)
def test_api_search_add_matches_dob(api_search, token, expected_value):
    matches = {key: [] for key in api_search.matchers}
    match_key = 'date_of_birth'
    api_search.addMatches(matches, match_key, token)
    dob_match_value = matches[match_key][0]['value']
    assert dob_match_value == expected_value


match_dos_cases = [
    ('01/01/1920', expected_date_1920),
    ('1920/01/01', expected_date_1920),
    ('1920.01.01', expected_date_1920),
    ('1920-01-01', expected_date_1920),
    ('1920_01_01', expected_date_1920),
    ('1920_1_1', expected_date_1920),
    ('1920_01_1', expected_date_1920),
    ('1920_1_01', expected_date_1920),
    ('01/01/2020', expected_date),
    ('01.01.2020', expected_date),
    ('01_01_2020', expected_date),
    ('01-01-2020', expected_date),
    ('2020/01/01', expected_date),
    ('01/01/20', expected_date),
    ('1/1/20', expected_date),
    ('01/1/20', expected_date),
    ('1/01/20', expected_date),
    ('1/01/20', expected_date),
]


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
@pytest.mark.parametrize(('token', 'expected_value'), match_dos_cases)
def test_api_search_add_matches_date_of_service(api_search, token, expected_value):
    matches = {key: [] for key in api_search.matchers}
    match_key = 'date_of_service'
    api_search.addMatches(matches, match_key, token)
    dob_match_value = matches[match_key][0]['value']
    assert dob_match_value == expected_value


match_case_num_cases = [
    ('A1-B2', 'A1-B2'),
    ('A1.B2', 'A1-B2'),
    ('A1/B2', 'A1-B2'),
    ('A1_B2', 'A1-B2'),
    ('11-B2', '11-B2'),
    ('A1-22', 'A1-22'),
]


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
@pytest.mark.parametrize(('token', 'expected_value'), match_case_num_cases)
def test_api_search_add_matches_path_case_num(api_search, token, expected_value):
    matches = {key: [] for key in api_search.matchers}
    match_key = 'path_case_num'
    api_search.addMatches(matches, match_key, token)
    dob_match_value = matches[match_key][0]['value']
    assert dob_match_value == expected_value
