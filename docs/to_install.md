## Installation
1. Clone main branch of Equitable-Polling-Locations
    1. This repo uses lfs. This can be downloaded from [https://git-lfs.com/].
        1. Download the appropriate version from this website and follow the instructions included there.
        1. If those instructions don't work, (as may be the case on Linux or MacOS), run ```sudo ./install.sh``` after downloading the file, then follow the instructions above. See [here](https://stackoverflow.com/questions/58796472/git-lfs-is-not-a-git-command-on-macos).

1. Install conda if you do not have it already
    1. This program uses SCIP as an optimizer, which is easily installed using Conda, but not using pip. (SCIP installation will be completed below by installing 'environment.yml')
    1. If you do not have conda installed already, use the relevant instructions [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html)

1. Create and activate conda environment. (Note, on a Windows machine, this requires using Anaconda Prompt.)
    1. `$ conda env create -f environment.yml`
    1. `$ conda activate equitable-polls`

1. Environment settings file `settings.yaml`
    1.  The settings file allows you to configure different environments to connect to such as dev or prod, and have each environment connect to a different database or dataset.
    1.  Copy the ```settings_example.yaml``` to ```settings.yaml```
    1.  Additional environments may be configured as necessary.



