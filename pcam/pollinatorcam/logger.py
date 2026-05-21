import datetime
import json
import os
import struct

import numpy


class MetaJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, numpy.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime.datetime):
            return obj.__str__()
        return json.JSONEncoder.default(self, obj)


def iter_raw_file(fn):
    data = [
        ('detection', 1, lambda b: struct.unpack('b', b)[0]),
        ('timestamp', 8, lambda b: struct.unpack('d', b)[0]),
        ('labels', 2988 * 8, lambda b: numpy.fromstring(b, dtype='f8')),
    ]
    reading = True
    with open(fn, 'rb') as f:
        while reading:
            entry = {}
            for datum in data:
                l, n, uf = datum
                b = f.read(n)
                if len(b) != n:
                    reading = False
                    break
                entry[l] = uf(b)
            else:
                yield entry


class AnalysisResultsSaver:
    def __init__(self, data_dir):
        self.file = None
        self.data_dir = data_dir

    def __del__(self):
        if self.file is not None:
            self.file.close()

    def check_file(self, timestamp, record):
        if self.file is not None:
            if self.file.datetime.hour == timestamp.hour:
                return
            else:
                self.file.close()
                self.file = None
        d = os.path.join(self.data_dir, timestamp.strftime('%y%m%d'))
        if not os.path.exists(d):
            os.makedirs(d)
        # TODO better filename
        fn = os.path.join(d, '%02i.raw' % timestamp.hour)
        self.file = open(fn, 'ab')
        self.file.datetime = timestamp

    def save(self, timestamp, record):
        assert isinstance(timestamp, datetime.datetime)

        self.check_file(timestamp, record)

        # pack data, write to file
        # byte 0 = detection bool
        # byte 1:8 = timestamp
        # TODO save length of array
        # byte 9:? = 8 bytes per item
        bs = (
            struct.pack('b', record['detection']) +
            struct.pack('d', timestamp.timestamp()) +
            record['labels'].tobytes())
        self.file.write(bs)
