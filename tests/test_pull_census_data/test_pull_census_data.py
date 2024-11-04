import pull_census_data

def test_pull_tiger_file(mocker):

    mocker.patch("pull_census_data.unzip_file", return_value="")
    mocker.patch("pull_census_data.download_file", return_value="")

    results = pull_census_data.pull_tiger_file("New Jersey", "34", 'Bergen_NJ', '003', "tabblock20")

    results_zero = results[0]
    assert results_zero == 'https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/34_NEW_JERSEY/34003/tl_2020_34003_tabblock20.zip'

    results_one = str(results[1])
    assert results_one == 'datasets\\census\\tiger\\Bergen_NJ'
