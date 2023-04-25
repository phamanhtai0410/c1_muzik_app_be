import logging

from src.utilities import RedisClient


def ignore_duplicates(func):
    def wrapper(*args, **kwargs):
        redis_ = RedisClient()
        try:
            clones_count = redis_.connection.incr(f"{func.__name__}{args, kwargs}")
            if clones_count == 1:
                # this is the first running instance of the task, execute
                func(*args, **kwargs)
            redis_.connection.decr(f"{func.__name__}{args, kwargs}")
        except Exception as e:
            logging.error(e)
            redis_.connection.decr(f"{func.__name__}{args, kwargs}")

    return wrapper
