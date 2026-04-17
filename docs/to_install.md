## Installation
1. Clone main branch of Equitable-Polling-Locations
    1. This repo uses lfs. This can be downloaded from [https://git-lfs.com/](https://git-lfs.com/).
        1. Download the appropriate version from this website and follow the instructions included there.
        1. If those instructions don't work, (as may be the case on Linux or MacOS), run ```sudo ./install.sh``` after downloading the file, then follow the instructions above. See [here](https://stackoverflow.com/questions/58796472/git-lfs-is-not-a-git-command-on-macos).
1. Install Docker from [https://www.docker.com/](https://www.docker.com/)
    1. Windows:
       1. In the Windows Subsystem for Linux set the memory to at least 8gb in the ```.wslconfig``` in the ```%USERPROFILE%``` directory.
    1. MacOS:
       1. In the docker desktop app, under resources set the memory to at least 8gb.
1. Environment settings file `settings.yaml`
    1.  The settings file allows you to configure different environments to connect to such as dev or prod, and have each environment connect to a different database or dataset.
    1.  Copy the ```settings_example.yaml``` to ```settings.yaml```
    1.  Additional environments may be configured as necessary.

### Census API Key (optional, for new counties)

If you plan to download census data for counties not already in the repo, you need a free census API key.

1. [Apply for a census API key](https://api.census.gov/data/key_signup.html) (approved in seconds)
2. Install keyring on your host machine: `pip install keyring`
3. Store your key: `python run.py set_census_key`
4. Use `-k` when running scripts that need census data: `python run.py -k <script> [args]`

The `-k` flag caches the key locally in `authentication_files/credentials.json` (gitignored), so you only need to pass `-k` once. Subsequent runs will use the cached file.

### Test the Installation
To confirm the installation is setup correctly, run pytest with the following command in the root of the project directory:

```
docker compose run --rm app pytest
```

All tests should pass.

