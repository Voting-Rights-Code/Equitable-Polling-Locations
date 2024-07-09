import requests
import json

## just a stub - not working

class CensusData:
    def __init__(self):
        self.cache_file = "census_cache.json"
        self.base_url = "https://api.census.gov/data/2019/pep/population"

    def get_data(self, county):
        data = self.read_cache(county)
        if data:
            return data
        else:
            data = self.fetch_data(county)
            self.cache_data(county, data)
            return data

    def fetch_data(self, county):
        url = f"{self.base_url}?get=POP,NAME&for=county:{county}&in=state:*"
        response = requests.get(url)
        if response.status_code == 200:
            data = json.loads(response.text)
            return data
        else:
            raise Exception("Failed to fetch data from the API.")

    def cache_data(self, county, data):
        cache = self.read_cache()
        cache[county] = data
        with open(self.cache_file, "w") as file:
            json.dump(cache, file)

    def read_cache(self, county=None):
        try:
            with open(self.cache_file, "r") as file:
                cache = json.load(file)
                if county:
                    return cache.get(county)
                else:
                    return cache
        except FileNotFoundError:
            return None
