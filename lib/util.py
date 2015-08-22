# amara3.util
"""
Some utilities for general use in Amara

Copyright 2008-2015 Uche Ogbuji
"""

def coroutine(func):
    '''
    Decorator: Eliminate the need to call next() to kick-start a co-routine
    From David Beazley: http://www.dabeaz.com/generators/index.html
    '''
    def start(*args,**kwargs):
        coro = func(*args,**kwargs)
        next(coro)
        return coro
    return start

