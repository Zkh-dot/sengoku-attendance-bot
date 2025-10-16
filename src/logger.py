from enum import IntEnum
import os
import logging
from typing import Optional
from functools import wraps
import datetime

__all__ = ["get_logger"]

os.makedirs("logs", exist_ok=True)
filename = os.path.join(f"logs", f"logs_{datetime.datetime.now().strftime('%y-%m-%d_%H-%M')}.log")

class LoggingLevel(IntEnum):
    NOTSET = logging.NOTSET
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

def get_logger(logger_name: Optional[str] = None, log_consol = True, log_file = True, draw_progress = True):
    handlers = []
    if log_consol:
        handlers.append(logging.StreamHandler())
    if log_file:
        handlers.append(logging.FileHandler(os.path.join(filename), mode="w", encoding='utf-8'))
        
    logging.basicConfig(format=u'[{asctime} - {levelname}]: {message}\n',
                    style='{', level=logging.INFO,
                    handlers=handlers,
                    encoding = 'utf-8')
    logger = logging.getLogger(logger_name)

    # if not logger.hasHandlers(): #
    #     formatter = logging.Formatter(fmt='[{asctime}] {message}\n', style='{')

    #     stream_handler = logging.StreamHandler()
    #     stream_handler.setFormatter(formatter)

    #     logger.addHandler(stream_handler)
    #     logger.setLevel(logging.INFO)

    return logger


def trace_call(logger: logging.Logger, func):
    if not hasattr(func, 'custom_wrappers'):
        setattr(func, 'custom_wrappers', ['trace_call'])
    else:
        if 'trace_call' in getattr(func, 'custom_wrappers'):
            return func

    @wraps(func)
    def wrapper(*args, **kwargs):
        # logger.info(f'[TraceCall] === Run function "{func.__module__}.{func.__qualname__}"')
        # logger.info('[TraceCall] = Arguments: {}, {}'.format(args, kwargs))
        name = func.__qualname__
        logger.info("start {} at {}".format(name, datetime.datetime.now()))

        result = func(*args, **kwargs)

        # logger.info(f'[TraceCall] === Function "{func.__module__}.{func.__qualname__}" result: {result.returncode if hasattr(result, "returncode") else result}')
        logger.info("end {} at {}".format(
            name, datetime.datetime.now()))
        return result
    return wrapper

def ignore_pandas_warnings():
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module='pandas')
    warnings.filterwarnings("ignore", category=FutureWarning, module='pandas')