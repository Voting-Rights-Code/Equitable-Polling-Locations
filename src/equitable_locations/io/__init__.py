import osmnx.settings as ox_settings
from equitable_locations import PROJECT_ROOT

ox_settings.cache_folder = PROJECT_ROOT / "untracked" / "osmnx_cache"
