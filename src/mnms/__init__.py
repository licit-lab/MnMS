from .log import create_logger, LOGLEVEL

log = create_logger(__name__, stream_level=LOGLEVEL.WARNING)