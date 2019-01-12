import sys
import ssl
import asyncio


try:
    import aiohttp
    from aiohttp import ClientSession

    AIOHTTP_ERROR_MENAGERIE = (
        ssl.CertificateError,
        asyncio.TimeoutError,
        aiohttp.ClientOSError,
        aiohttp.ServerDisconnectedError,
        aiohttp.ClientResponseError,
        aiohttp.ClientError,
    )
except ImportError:
    pass


def go_async(launch_task, close_loop=False):
    '''
    Convenience function to launch a coroutine asynchronously
    Basically Python 3.7's asyncio.run() simulated for 3.5 & 3.6
    
    WARNING: You can generally only use this once per interpreter session, unless you set close_loop=False

    >>> import asyncio
    >>> from amara3.asynctools import go_async
    >>> async def x():
    ...     await asyncio.sleep(1)
    ...     return 'ndewo'
    >>> retval = go_async(x())
    >>> retval
    'ndewo'
    '''
    loop = asyncio.get_event_loop()
    resp = loop.run_until_complete(launch_task)
    if close_loop: loop.close()
    return resp

#async def progress_indicator docstring rendered here for easy testing, for now
'''
import sys
import asyncio
from amara3.asynctools import progress_indicator, go_async
async def x():
    print('1', end='')
    await asyncio.sleep(2)
    print('2', end='')
    await asyncio.sleep(2)
    print('3', end='')

_ = go_async(asyncio.gather(x(), progress_indicator(0.5)))
'''

async def progress_indicator(delay, loop=None, out=sys.stdout, max_width=80):
    '''
    Coroutine useful for progress indication to console,
    printing dots when scheduled, after a given delay

    >>> import sys
    >>> import asyncio
    >>> from amara3.asynctools import progress_indicator, go_async
    >>> async def x():
    ...     print('1', end='')
    ...     await asyncio.sleep(2)
    ...     print('2', end='')
    ...     await asyncio.sleep(2)
    ...     print('3', end='')
    >>> _ = go_async(asyncio.gather(x(), progress_indicator(0.5)))
    1...2....3.>>> 
    '''
    if not loop: loop = asyncio.get_event_loop()
    count_to_width = 0
    while True:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            break
        count_to_width += 1
        #Set a max width for th eline of dots & newline if reached
        if count_to_width > max_width:
            print('', file=sys.stderr)
            count_to_width = 0
        #Print a dot, with no newline afterward & force the output to appear immediately
        print('.', end='', file=out, flush=True)
        #Check if this is the last remaining task, and exit if so
        num_active_tasks = [ task for task in asyncio.Task.all_tasks(loop)
                                  if not task.done() ]
        if len(num_active_tasks) == 1:
            break


#class req_tracer docstring rendered here for easy testing, for now
'''
import aiohttp
from amara3.asynctools import go_async, req_tracer
rtimings = req_tracer()
async def access_site():
    url = 'http://artscene.textfiles.com/information/ascii-newmedia.txt'
    async with aiohttp.ClientSession(trace_configs=[rtimings.trace_config]) as sess:
        #If trace_request_ctx omitted, results stored in rtimings.request[None]
        async with sess.get(url, trace_request_ctx={'reqid': 'ID'}) as response:
            t = rtimings.request['ID'].get('total_elapsed', 0)
            t = '{:.3f}'.format(t) if t else 'UNKNOWN'
            print('Web request took', t, 'seconds')
            return response

resp = go_async(access_site())
'''

class req_tracer:
    '''
    aiohttp request tracer helper
    Requires aiohttp version 3.0.
    
    See: https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp-client-tracing-reference
    
    >>> import aiohttp
    >>> from amara3.asynctools import go_async, req_tracer
    >>> rtimings = req_tracer()
    >>> async def access_site():
    ...     url = 'http://artscene.textfiles.com/information/ascii-newmedia.txt'
    ...     async with aiohttp.ClientSession(trace_configs=[rtimings.trace_config]) as sess:
    ...         #If trace_request_ctx omitted, results stored in rtimings.request[None]
    ...         async with sess.get(url, trace_request_ctx={'reqid': 'ID'}) as response:
    ...             t = rtimings.request['ID'].get('total_elapsed', 0)
    ...             t = '{:.3f}'.format(t) if t else 'UNKNOWN'
    ...             print('Web request took', t, 'seconds')
    ...             return response
    ... 
    >>> resp = go_async(access_site())
    Web request took 0.121 seconds
    >>> 
    '''
    def __init__(self):
        #Store the tracked timings according to a key specified in the request context (or use None key if none provided)
        self.request = {}
        self.trace_config = aiohttp.TraceConfig()
 
        self.trace_config.on_request_start.append(self.start_t)
        self.trace_config.on_request_redirect.append(self.redirected)
        self.trace_config.on_dns_resolvehost_start.append(self.dns_start_t)
        self.trace_config.on_dns_resolvehost_end.append(self.dns_end_t)
        self.trace_config.on_connection_create_start.append(self.connect_start_t)
        self.trace_config.on_connection_create_end.append(self.connect_end_t)
        self.trace_config.on_request_end.append(self.end_t)
        self.trace_config.on_request_chunk_sent.append(self.chunk_sent)
        self.trace_config.on_response_chunk_received.append(self.chunk_received)

    async def start_t(self, session, context, params):
        time = session.loop.time()
        context.start_t = time
        context.is_redirect = False
 
    async def connect_start_t(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.connect_start_t = since_start
 
    async def redirected(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.redirected = since_start
        context.is_redirect = True
 
    async def dns_start_t(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.dns_start_t = since_start
 
    async def dns_end_t(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.dns_end_t = since_start
 
    async def connect_end_t(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.connect_end_t = since_start
     
    async def chunk_sent(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.chunk_sent = since_start
     
    async def chunk_received(self, session, context, params):
        time = session.loop.time()
        since_start = time - context.start_t
        context.chunk_received = since_start
 
    async def end_t(self, session, context, params):
        if not context.trace_request_ctx: return
        #Store the tracked timings according to a key specified in the request context (or use None key if none provided)
        reqid = context.trace_request_ctx.get('reqid')
        time_now = session.loop.time()
        total_elapsed = time_now - context.start_t
        context.end_t = total_elapsed
 
        #The DNS & connect callbacks are not getting called, for some reason
        #dns_lookup_and_dial_time = context.dns_end_t - context.dns_start_t
        #connect_time = context.connect_end_t - dns_lookup_and_dial_time
        #transfer_time = total_elapsed - context.connect_end_t
        is_redirect = context.is_redirect
        
        self.request.setdefault(reqid, {}).update({
            #'dns_lookup_and_dial_time': dns_lookup_and_dial_time,
            #'connect_time': connect_time,
            #'transfer_time': transfer_time,
            'is_redirect': is_redirect,
            'total_elapsed': total_elapsed
        })

