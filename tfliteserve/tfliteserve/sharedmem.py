"""
'Host' a model.TFLiteModel using shared memory buffers

the shared buffers include: 
    input array
    output array (after quantization removal)

Need separate codes per client, clients will need to have a unique channel.
Channel negotiation is... complicated, skip it, just pre-assign.

Each client should make it's own folder

main_dir: /dev/shm/tfliteserver

each client directory has:
    - input
    - output
    - meta: input/output details

client connects:
    - makes new folder in directory (if directory exists, delete it)
    - server sees new folder, fills with meta data & buffers
    - client connects to buffers
"""

import asyncio
import logging
import os
import pickle
import select
import shutil
import threading
import time

import numpy

from . import fifo


default_server_folder = '/dev/shm/tfliteserver'


def validate_meta(meta):
    if 'input' not in meta:
        raise ValueError("Invalid metadata missing input")

    if 'output' not in meta:
        raise ValueError("Invalid metadata missing output")

    for k in ('input', 'output'):
        if k not in meta:
            raise ValueError("Invalid metadata missing %s" % k)
        for sk in ('shape', 'dtype'):
            if sk not in meta[k]:
                raise ValueError("Invalid metadata missing %s %s" % (k, sk))


class SharedMemoryException(Exception):
    pass


class SharedMemoryBuffers:
    """
    Construct shared buffers (or access existing ones) in a folder on disk.
    These buffers are designed to be used by multiple processes where
    one process (Server) handles 'processing' input provided from other
    processes (Clients) via the input_array shared buffer and results
    are returned from the Server to the Client via the output_array.
    
    Coordination of the shared buffers occures via two fifos.


    Parameters
    ---------
    name: string
        Buffer collection name (will be subdir in shared buffer server_folder).
    meta: dict or None
        Dictionary containing metadata about the shared buffers including:
            input: dict, see tensorflow flite interpreter input_details
            output: dict, see tensorflow flite interpreter output_details
            labels: dict, see model.load_labels
        If None, meta will be read from the meta file in the folder
    server_folder: string or None
        Folder path in which to store shared memory mapped files. If None
        default_server_folder will be used.
    create: bool, default=True
        Create shared buffers otherwise remove folder and wait for another
        process to create the buffers.

    Attributes
    ----------
    folder: string
        Folder containing shared memory mapped files.
    input_array: numpy.memmap
        Shape = meta['input']['shape'], dtype = meta['input]['dtype']
    output_array: numpy.memmap
        Shape = meta['input']['shape'], dtype = meta['input]['dtype']
        if model has quantization, dtype will be overridden as float64

    Methods
    -------
    set_input: Copy values into input array shared buffer.
    get_input: Get contents or reference of input array.
    set_output: Copy values into output array shared buffer. 
    get_output: Get contents or reference of output array.

    Notes
    -----
    Direct use of arrays (without copying values) is very discouraged as
    these memmapped values can be changed by other processes.

    Examples
    --------
    """
    def __init__(self, name, meta=None, server_folder=None, create=True):
        if server_folder is None:
            server_folder = default_server_folder
        folder = os.path.join(server_folder, name)
        self.folder = folder
        self.is_client = None
        if create:
            if meta is None:
                raise ValueError("meta is required if creating buffers")
            self._create_buffers(meta)
        else:
            self._wait_for_buffers()

    def __repr__(self):
        return "SharedMemoryBuffers(%s,%s)" % (hex(id(self)), self.is_client)

    def _create_buffers(self, meta=None):
        mfn = os.path.join(self.folder, 'meta')

        ir_fn = os.path.join(self.folder, 'input_ready')  # to server
        or_fn = os.path.join(self.folder, 'output_ready')  # to client

        if meta is None:
            self.is_client = True
            # load meta from directory
            with open(mfn, 'rb') as f:
                meta = pickle.load(f)
            self.in_fifo = fifo.writer(ir_fn)
            self.out_fifo = fifo.reader(or_fn)
        else:
            self.is_client = False
            if not os.path.exists(self.folder):
                os.makedirs(self.folder)
            self.in_fifo = fifo.reader(ir_fn, True)
            self.out_fifo = fifo.writer(or_fn, True)
            # write meta to directory
            with open(mfn, 'wb') as f:
                pickle.dump(meta, f)

        validate_meta(meta)
        self.meta = meta

        input_shape = tuple(meta['input']['shape'])
        input_dtype = numpy.dtype(meta['input']['dtype'])

        #mode = 'w+' if self.is_client else 'r+'
        ifn = os.path.join(self.folder, 'input')
        mode = 'r+' if os.path.exists(ifn) else 'w+'
        #if not os.path.exists(ifn):
        #    mode = 'w+'
        self.input_array = numpy.memmap(
            ifn, dtype=input_dtype, mode=mode, shape=input_shape)

        output_shape = tuple(meta['output']['shape'])
        output_dtype = numpy.dtype(meta['output']['dtype'])

        #mode = 'r+' if self.is_client else 'w+'
        ofn = os.path.join(self.folder, 'output')
        mode = 'r+' if os.path.exists(ofn) else 'w+'
        self.output_array = numpy.memmap(
            ofn, dtype=output_dtype, mode=mode, shape=output_shape)
        
        for fn in (ir_fn, or_fn, ifn, ofn, mfn):
            logging.debug("%s waiting for %s", self, fn)
            while not os.path.exists(fn):
                time.sleep(0.001)

        # flush input
        #while ffp in select.select([ffp,], [], [], 0.001)[0]:
        #    ffp.read(1)

        self.connect()

        # flush
        #if self.is_client:
        #    while self.in_fifo.read():
        #        pass
        #else:
        #    while self.out_fifo.read():
        #        pass

    def connect(self, timeout=None):
        if timeout is None:
            r = self.in_fifo.connect()
            return self.out_fifo.connect() and r
        t = time.monotonic()
        while (time.monotonic() - t) <= timeout:
            if self.connect():
                return True
        return False
        #if self.is_client is False:
        #    r = self.in_fifo.connect()
        #    return self.out_fifo.connect() and r
        #else:
        #    r = self.out_fifo.connect()
        #    return self.in_fifo.connect() and r

    def connected(self):
        return self.in_fifo.connected() and self.out_fifo.connected()

    def _wait_for_buffers(self):
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        fns = [
            os.path.join(self.folder, fn) for fn in [
                'meta',
                'input',
                'output',
                'input_ready',
                'output_ready']
        ]
        for fn in fns:
            logging.debug("%s waiting for %s", self, fn)
            while not os.path.exists(fn):
                time.sleep(0.001)
        self._create_buffers()

    def set_input(self, values):
        """Copy values to input_array buffer and flush to disk

        Parameters
        ----------
        values: ndarray
            Must be the same size and dtype of input_array
        """
        assert self.is_client
        if not self.connect():
            return False
        self.input_array[:] = values
        self.input_array.flush()

        return self.in_fifo.write()

    def get_input(self, copy=True):
        """Get a copy of or reference to input_array

        Parameters
        ----------
        copy: bool, default=True
            if True, copy contents of input_array, if False a reference
            to input_array will be returned.

        Returns
        -------
        values: ndarray
            Either a copy or reference of output_array.
        """
        if copy:
            return numpy.copy(self.input_array)
        return self.input_array

    def set_output(self, values):
        """Copy values to output_array buffer and flush to disk

        Parameters
        ----------
        values: ndarray
            Must be the same size and dtype of output_array
        """
        assert not self.is_client
        if not self.connect():
            return False
        self.output_array[:] = values
        self.output_array.flush()

        return self.out_fifo.write()

    def get_output(self, copy=True):
        """Get a copy of or reference to output_array

        Parameters
        ----------
        copy: bool, default=True
            if True, copy contents of output_array, if False a reference
            to output_array will be returned.

        Returns
        -------
        values: ndarray
            Either a copy or reference of input_array.
        """
        if copy:
            return numpy.copy(self.output_array)
        return self.output_array


class SharedMemoryServer:
    def __init__(self, function, meta, server_folder=None):
        self.function = function
        if server_folder is None:
            server_folder = default_server_folder
        self.folder = server_folder
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self.clients = {}
        self.check_for_new_clients_period = 0.5
        self.run_client_timeout = 1.0
        validate_meta(meta)
        self.meta = meta

    def check_for_new_clients(self):
        for cn in os.listdir(self.folder):
            if cn not in self.clients:
                self.add_client(cn)
        for cn in self.clients:
            self.add_reader(cn)  # only adds if needed
        self.loop.call_later(
            self.check_for_new_clients_period,
            self.check_for_new_clients)

    def remove_client(self, name):
        if name not in self.clients:
            return
        logging.debug("Removing client: %s", name)
        if self.clients[name].has_reader:
            self.loop.remove_reader(self.clients[name].in_fifo.fnum)
            self.clients[name].has_reader = False
        del self.clients[name]

    def add_reader(self, name):
        c = self.clients[name]
        if c.has_reader:
            return False
        if not c.connect():
            return False
        logging.debug("Adding reader for %s", name)
        self.loop.add_reader(
            c.in_fifo.fnum, self.run_client, name)
        c.has_reader = True

    def add_client(self, name):
        if name in self.clients:
            self.remove_client(name)
        logging.debug("Adding client: %s", name)
        c = SharedMemoryBuffers(
            name, self.meta, server_folder=self.folder, create=True)
        c.has_reader = False
        self.clients[name] = c
        self.add_reader(name)

    def run_client(self, client_name):
        logging.debug("Running client: %s", client_name)
        b = self.clients[client_name]
        if not b.in_fifo.read(block=True, timeout=self.run_client_timeout):
            # client failed
            logging.info("Client in_fifo read failed: %s", client_name)
            self.remove_client(client_name)
            return
        try:
            b.set_output(self.function(b.input_array))
        except BrokenPipeError as e:
            logging.info("Client connection failed: %s[%s]", client_name, e)
            self.remove_client(client_name)

    def run_forever(self, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        
        self.loop = loop
        self.loop.call_soon(self.check_for_new_clients)
        
        self.loop.run_forever()
        self.loop.close()


class SharedMemoryClient:
    def __init__(self, name, server_folder=None, wait=True):
        self.name = name
        self.buffers = SharedMemoryBuffers(
            name, server_folder=server_folder, create=False)
        if wait:
            self.wait_for_server()

    def wait_for_server(self, timeout=None):
        return self.buffers.connect(timeout)

    def run(self, input_array, timeout=None):
        if not self.buffers.set_input(input_array):
            raise SharedMemoryException("Input could not be set")

        # wait for output ready signal
        if not self.buffers.out_fifo.read(block=True, timeout=timeout):
            raise SharedMemoryException("Server communication failed")

        return self.buffers.get_output(copy=True)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


def test(verbose=False):
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    meta = {
        'input': {
            'shape': (1, 224, 224, 3),
            'dtype': 'uint8',
        },
        'output': {
            'shape': (1, 1024),
            'dtype': 'f8',
        },
    }

    def make_input(v=None):
        if v is None:
            return numpy.random.randint(
                0, 255,
                size=meta['input']['shape'], dtype=meta['input']['dtype'])
        else:
            return numpy.ones(
                meta['input']['shape'], dtype=meta['input']['dtype']) * v

    def f(i):
        o = numpy.zeros(
            meta['output']['shape'], dtype=meta['output']['dtype'])
        o[:] = i.mean()
        return o

    class ServerThread:
        def __init__(self):
            self.thread = threading.Thread(
                target=self.run_server, daemon=True)
            self.thread.start()
        
        def run_server(self):
            self.server = SharedMemoryServer(f, meta)
            #self.loop = asyncio.get_event_loop()
            self.loop = asyncio.new_event_loop()
            self.server.run_forever(loop=self.loop)

        def _stop_loop(self):
            self.loop.stop()

        def kill(self):
            self.loop.call_soon_threadsafe(self._stop_loop)
            self.thread.join()

    st = ServerThread()
    assert st.thread.is_alive(), "Server failed to start"

    for i in range(2):
        c = SharedMemoryClient('test')
        assert c.wait_for_server(1.0), "Server never connected"
        r = c.run(make_input(10), timeout=1.0).mean()
        assert abs(r - 10) < 1E-4, "Input/Output[%i] fail: %s != 10" % (i, r)
        del c

    c = SharedMemoryClient('test')
    st.kill()
    assert not st.thread.is_alive(), "Server failed to die"

    ok = False
    try:
        c.run(make_input(10), timeout=0.1)
        ok = False
    except Exception as e:
        ok = True
    assert ok, "Server disconnnect didn't fail"

    st = ServerThread()
    assert st.thread.is_alive(), "Server failed to restart"

    assert c.wait_for_server(1.0), "Server never connected"
    r = c.run(make_input(10), timeout=1.0).mean()
    assert abs(r - 10) < 1E-4, "Input/Output[%i] fail: %s != 10" % (i, r)

    st.kill()
