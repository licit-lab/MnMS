import logging

class LOGLEVEL():
    CRITICAL = 50
    ERROR    = 40
    WARNING  = 30
    INFO     = 20
    DEBUG    = 10
    NOTSET   = 0

logger = logging.getLogger('routeservice')
logger.setLevel(logging.INFO)
_formatter = logging.Formatter('%(levelname)s(routeservice): %(message)s')
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(_formatter)
logger.addHandler(_ch)


def set_log_level(level):
    logger.setLevel(level)
    _ch.setLevel(level)