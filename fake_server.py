import tfliteserve

import numpy

m = {
    'input': {'shape': (1, 224, 224, 3), 'dtype': 'uint8'},
    'output': {'shape': (1, 1024), 'dtype': 'f8'},
}


def f(in_array):
    a = numpy.zeros(
        m['output']['shape'], dtype=m['output']['dtype'])
    v = in_array.mean()
    print("mean: %s" % v)
    if v < 50:  # if dark, output 1s
        a[:] = 1
    return a


s = tfliteserve.sharedmem.SharedMemoryServer(f, m, 0.001)
s.run_forever()
