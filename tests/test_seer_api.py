import pytest

from wsi_deid import matching_api


@pytest.mark.plugin('wsi_deid')
@pytest.mark.plugin('large_image')
def test_api_search():
    api_search = matching_api.APISearch('localhost:8080/matching/wsi', 'api-key')
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
        '4': {'count': 1, 'average_confidence': 0.06642707626467459}
    }
    queries = api_search.getQueryList(ocr_record)

    # Ensure each query has enough data
    assert all([len(query) >= 3 for query in queries])

    # Ensure tokens with confidence < .75 aren't used for queries
    query_tokens_list = [list(query.values()) for query in queries]
    query_tokens = set([token for sublist in query_tokens_list for token in sublist])
    assert len(query_tokens) == 6
