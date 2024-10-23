import pytest
import warnings
from model_config import get_canonical_config_args, CANONICAL_FIELDS

def test_get_canonical_config_args_server(mocker):
    mocker.patch('model_config.gc.SERVER', True)
    mocker.patch('model_config.gc.PROD_DATASET', 'your_dataset')
    mocker.patch('model_config.gc.PROJECT', 'your_project')
    mock_client = mocker.patch('model_config.bigquery.Client')
    mock_query_result = mocker.MagicMock()
    mock_query_result.to_dataframe.return_value.columns = CANONICAL_FIELDS
    mock_client.return_value.query.return_value = mock_query_result

    expected_fields = CANONICAL_FIELDS
    assert sorted(get_canonical_config_args()) == sorted(expected_fields)

def test_get_canonical_config_args_local(mocker):
    mocker.patch('model_config.gc.SERVER', False)
    expected_fields = CANONICAL_FIELDS
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert sorted(get_canonical_config_args()) == sorted(expected_fields)
        assert any(item.category == UserWarning for item in w)
