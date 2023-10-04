''' Misc utils '''

from time import time

enabled: bool = False

def set_timers_enabled(value: bool):
    global enabled
    enabled = value

def timer(func):
    # This function shows the execution time of
    # the function object passed

    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        if enabled:
            print(f'Function {func.__name__!r} executed in {(t2-t1):.4f}s')
        return result
    return wrap_func