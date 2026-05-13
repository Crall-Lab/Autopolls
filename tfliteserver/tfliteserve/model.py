import asyncio
import time

import numpy

#import tflite_runtime.interpreter as tflite
import ai_edge_litert.interpreter as tflite

load_delegate = tflite.load_delegate

from . import sharedmem


EDGETPU_SHARED_LIB = 'libedgetpu.so.1'


# load labels
def load_labels(path, encoding='utf-8'):
    """Loads labels from file (with or without index numbers).

    Args:
        path: path to label file.
        encoding: label file encoding.
    Returns:
        Dictionary mapping indices to labels.
    """
    with open(path, 'r', encoding=encoding) as f:
        lines = f.readlines()
        if not lines:
            return {}

        if lines[0].split(' ', maxsplit=1)[0].isdigit():
            pairs = [line.split(' ', maxsplit=1) for line in lines]
            return {int(index): label.strip() for index, label in pairs}
        else:
            return {index: line.strip() for index, line in enumerate(lines)}


class TFLiteModel:
    def __init__(self, model_fn, labels_fn=None, edge=False):
        # load model
        if edge:
            self.model = tflite.Interpreter(
                  model_path=model_fn,
                  experimental_delegates=[load_delegate(EDGETPU_SHARED_LIB, {})])
        else:
            self.model = tflite.Interpreter(model_path=model_fn)
        self.model.allocate_tensors()

        # load labels (if provided)
        if labels_fn is not None:
            self.labels = load_labels(labels_fn)
        else:
            self.labels = {}

        # prep input details
        self.input_details = self.model.get_input_details()[0]
        self.output_details = self.model.get_output_details()[0]
        self.input_tensor_index = self.input_details['index']
        self.output_tensor_index = self.output_details['index']
        self.q_out_scale, self.q_out_zero = self.output_details['quantization']

        self.meta = {
            'type': 'classifier',
            'input': self.input_details,
            'output': self.output_details,
            'labels': self.labels,
        }
        if 'quantization' in self.meta['output']:
            self.meta['output']['dtype'] = 'f8'

    def set_input(self, input_tensor):
        if input_tensor.dtype != self.input_details['dtype']:
            print("Converting input dtype:", input_tensor.dtype, self.input_details['dtype'])
            input_tensor = input_tensor.astype(self.input_details['dtype'])
        if (
                input_tensor.ndim != len(self.input_details['shape']) or
                numpy.any(input_tensor.shape != self.input_details['shape'])):
            print("Reshaping input:", input_tensor.shape, self.input_details['shape'])
            input_tensor = input_tensor.reshape(self.input_details['shape'])
        self.model.set_tensor(self.input_tensor_index, input_tensor)

    def get_output(self):
        t = self.model.get_tensor(self.output_tensor_index)
        # print(t)
        return (self.q_out_scale * (numpy.squeeze(t) - self.q_out_zero))

    def run(self, input_tensor):
        self.set_input(input_tensor)
        #t0 = time.monotonic()
        self.model.invoke()
        #t1 = time.monotonic()
        #if not hasattr(self, '_run_stats'):
        #    self._run_stats = {'n': 0, 'dts': 0}
        #dt = t1 - t0
        #self._run_stats['n'] += 1
        #self._run_stats['dts'] += dt
        #if self._run_stats['n'] > 99:
        #    n = self._run_stats['n']
        #    adt = self._run_stats['dts'] / n
        #    print("Average run time over %i calls: %s" % (n, adt))
        #    del self._run_stats
        return self.get_output()

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


class Classifier(TFLiteModel):
    pass


class Detector(TFLiteModel):
    def __init__(self, model_fn, labels_fn=None, edge=False):
        super().__init__(model_fn, labels_fn, edge)

        self.output_details = self.model.get_output_details()

        # outputs are:
        # - scores
        # - bboxes [top, left, bottom, right] normalized 0-1
        # - n_boxes (shape 1)
        # - classes
        assert len(self.output_details) == 4

        # make fake output with shape (n_boxes, 6)
        # 6 = [class, score, top, left, bottom, right]
        self.n_boxes = self.output_details[0]['shape'][1]

        # validate output shape
        assert tuple(self.output_details[0]['shape']) == (1, self.n_boxes)
        assert tuple(self.output_details[1]['shape']) == (1, self.n_boxes, 4)
        assert tuple(self.output_details[2]['shape']) == (1,)
        assert tuple(self.output_details[3]['shape']) == (1, self.n_boxes)

        self.meta['output'] = {
            'shape': (self.n_boxes, 6),
            'dtype': 'f8',
        }
        self.meta['type'] = 'detector'
        self.meta['n_boxes'] = self.n_boxes

    def get_output(self):
        scores, bboxes, _, classes = [
            numpy.squeeze(self.model.get_tensor(td['index'])) for td in self.output_details]
        # print(scores, bboxes, classes)
        return numpy.hstack((
            classes[:, numpy.newaxis],
            scores[:, numpy.newaxis],
            bboxes))


class TFLiteServer(sharedmem.SharedMemoryServer):
    def __init__(self, model, server_folder=None, junk_period=None):
        super(TFLiteServer, self).__init__(
            model, model.meta, server_folder)
        self.junk_input = numpy.random.randint(
            0, 255, size=model.meta['input']['shape'],
            dtype=model.meta['input']['dtype'])
        self.junk_period = junk_period
        self.last_run = time.monotonic()

    def run_client(self, client_name):
        self.last_run = time.monotonic()
        super(TFLiteServer, self).run_client(client_name)

    def run_junk(self):
        t = time.monotonic()
        if t - self.last_run > self.junk_period:
            self.function(self.junk_input)
            self.last_run = t
        dt = self.last_run + self.junk_period - t
        self.loop.call_later(dt, self.run_junk)

    def run_forever(self, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()

        if self.junk_period is not None and self.junk_period > 0:
            print("Running junk data every %s seconds" % self.junk_period)
            loop.call_soon(self.run_junk)

        super(TFLiteServer, self).run_forever(loop)
