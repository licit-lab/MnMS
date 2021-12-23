import logging

class LOGLEVEL():
    CRITICAL = 50
    ERROR    = 40
    WARNING  = 30
    INFO     = 20
    DEBUG    = 10
    NOTSET   = 0


def create_logger(logname,
                  format='%(levelname)s(mnms): %(message)s',
                  logfile=None,
                  base_level=LOGLEVEL.INFO,
                  stream_level=LOGLEVEL.DEBUG,
                  file_level=LOGLEVEL.INFO
                  ):
    logger = logging.getLogger(logname)
    logger.setLevel(base_level)
    formatter = logging.Formatter(format)
    stream = logging.StreamHandler()
    stream.setLevel(stream_level)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if logfile is not None:
        file = logging.FileHandler(logfile)
        file.setLevel(file_level)
        logger.addHandler(file)

    return logger

rootlogger = create_logger('mnms')