import logging


class LOGLEVEL():
    CRITICAL = 50
    ERROR    = 40
    WARNING  = 30
    INFO     = 20
    DEBUG    = 10
    NOTSET   = 0


def create_logger(logname,
                  base_level=LOGLEVEL.WARNING,
                  stream_level=LOGLEVEL.INFO,
                  ):
    format = f'%(levelname)s(%(name)s): %(message)s'
    logger = logging.getLogger(logname)
    logger.setLevel(base_level)
    formatter = logging.Formatter(format)
    stream = logging.StreamHandler()
    stream.setLevel(stream_level)
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    logger.propagate = False
    return logger


def get_all_mnms_logger():
    return [logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith('mnms')]


def get_logger(logger_name):
    return logging.getLogger(logger_name)


def set_all_mnms_logger_level(level):
    [logger.setLevel(level) for logger in get_all_mnms_logger()]

def attach_log_file(filename:str, file_level=LOGLEVEL.INFO):
    loggers = get_all_mnms_logger()
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(file_level)
    format = f'%(levelname)s(%(name)s): %(message)s'
    formatter = logging.Formatter(format)
    file_handler.setFormatter(formatter)
    for l in loggers:
        l.addHandler(file_handler)