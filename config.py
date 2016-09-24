import json
import logging
import os
import time
from threading import Thread

from engine import redis
import settings


logger = logging.getLogger(__name__)


class ConfigLoader(Thread):

    def __init__(self, name=settings.DYNAMIC_CONFIG):
        super().__init__()
        self.name = name
        self.load()

    def load(self):
        config = redis.get(self.name)
        if config:
            logger.info('Loading config from Redis...')
            settings.dynamic = json.loads(config.decode())
        elif os.path.exists(self.name):
            logger.info('Loading config from a file...')
            settings.dynamic = json.load(open(self.name))
            redis.set(self.name, json.dumps(settings.dynamic),
                      ex=settings.REDIS_EXPIRE)

    def run(self):
        while True:
            self.load()
            time.sleep(settings.DYNAMIC_CONFIG_INTERVAL)
