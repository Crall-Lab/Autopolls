import argparse

from . import fifo
from . import model
from . import sharedmem


def run_server():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-e', '--edge', default=False, action='store_true',
        help='run model on the edge')
    parser.add_argument(
        '-f', '--fake', default=False, action='store_true',
        help='run fake model')
    parser.add_argument(
        '-j', '--junk', default=0.01, type=float,
        help='period to inject junk data to keep edge tpu happy')
    parser.add_argument(
        '-l', '--labels', default='',
        help='labels filename [if blank model must be directory]')
    parser.add_argument(
        '-m', '--model', default='',
        help='Model directory or file')
    parser.add_argument(
        '-t', '--test', default=False, action='store_true',
        help='run tests')
    parser.add_argument(
        '-T', '--type', default='classifier',
        choices=('classifier', 'detector'),
        help='model type')
    args = parser.parse_args()
    if args.test:
        print("Running fifo tests")
        fifo.test()
        print("\tok")
        print("Running sharedmem tests")
        sharedmem.test()
        print("\tok")
        return
    if args.fake:
        if args.type != 'classifier':
            raise Exception("Only able to fake classifier")
        meta = {
            'input': {'shape': (1, 224, 224, 3), 'dtype': 'uint8'},
            'output': {'shape': (1, 1024), 'dtype': 'f8'},
        }

        def f(in_array):
            out_array = numpy.zeros(
                meta['output']['shape'], dtype=meta['output']['dtype'])
            out_array[:] = in_array.mean()
            return out_array

        s = sharedmem.SharedMemoryServer(f, meta)
    else:
        if args.type == 'classifier':
            m = model.Classifier(args.model, args.labels, edge=args.edge)
        elif args.type == 'detector':
            m = model.Detector(args.model, args.labels, edge=args.edge)
        else:
            raise Exception("Unknown type %s" % (args.type, ))
        junk = None if args.junk == 0.0 else args.junk
        s = model.TFLiteServer(m, junk_period=junk)
    s.run_forever()
