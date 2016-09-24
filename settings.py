REDIS_EXPIRE = 60 * 60
REDIS_CONFIG = {
    'db': 3,
}

try:
    from settings_local import *
except ImportError:
    pass
