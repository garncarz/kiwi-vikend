REDIS_EXPIRE = 60 * 60
REDIS_CONFIG = {
    'db': 3,
}

DYNAMIC_CONFIG = 'config.json'
DYNAMIC_CONFIG_INTERVAL = 30
dynamic = {
    'on': True,
    'margin': 0,
}


try:
    from settings_local import *
except ImportError:
    pass
