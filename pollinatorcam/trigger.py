"""
Trigger:
    - takes in labels/predictions
        - compare against label mask (initally based on taxonomy)
        - turns trigger on/off
    - called periodically (in ioloop)
        - if rising edge, start recording
        - if falling edge, record (+1 second)
        - if still triggered, record at some max duty cycle
        - if no trigger, nothing...

So states will be:
    not triggered, not recording
    not triggered, post-recording
    trigger started, start recording
    triggered, recording
    triggered, duty cycle limited
    trigger stopped, if not recording, record 1 second

Duty cycle limit only during triggered period
    record initial 10 seconds
    if still tiggered, hold off for 90 seconds
    if during hold off, trigger falls, re-start recording
    if hold off finished, restart recording
"""

import datetime
#import json
import logging
import time
import os

import cv2
import numpy

from . import gstrecorder
from . import cvrecorder

hstname = open('/etc/hostname','r')
hstname1 = hstname.readline().split('\n')[0]
hstname.close()

mask_consts = {
#    'insects': [('slice', 75, 1067), 2291],
#    'birds': [('slice', 1103, 1589), ],
#    'mammals': [('slice', 1589, 1638), ],
}


def set_mask_labels(labels):
    for i in labels:
        mask_consts[labels[i]] = i


# def make_allow(insects=False, birds=False, mammals=False):
#     allow = numpy.zeros(N_CLASSES)
#     if insects:
#         allow[75:1067] = 1
#         allow[2291] = 1
#     if birds:
#         allow[1103:1589] = 1
#     if mammals:
#         allow[1589:1638] = 1
#     return allow


def update_mask(mask, valence, operation):
    """
    valence is True/False for allow/deny
    operation is:
        index range: ['slice', 75, 1067]
        individual index: 42
        list of indices:  [3, 1, 4]
    """
    if isinstance(operation, int):
        mask[operation] = valence
    elif isinstance(operation, (list, tuple)):
        if len(operation) == 0:
            return mask
        if operation[0] == 'slice':
            mask[slice(*operation[1:])] = valence
        else:
            mask[operation] = valence
    elif isinstance(operation, str):
        if operation not in mask_consts:
            raise ValueError("Unknown update_mask operation: %s" % (operation, ))
        ops = mask_consts[operation]
        if isinstance(ops, (tuple, list)):
            for op in ops:
                mask = update_mask(mask, valence, op)
        else:
            mask = update_mask(mask, valence, ops)
    else:
        raise ValueError("Unknown update_mask operation: %s" % (operation, ))
    return mask


def make_allow_mask(n_classes, *ops):
    """
    ops are: (True/False, operation) (see update_mask)
    """
    # if first op is deny (or missing) allow all
    if (len(ops) == 0) or (not ops[0][0]):
        mask = numpy.ones(n_classes, dtype=bool)
    else:  # else (first op is allow) start by denying all
        mask = numpy.zeros(n_classes, dtype=bool)
    for op in ops:
        mask = update_mask(mask, *op)
    logging.debug("Made allow mask: %s", mask)
    return mask


def parse_allow_mask(allow_string, check_consts=True):
    """
    allow_string: string
        comma separated values where values are:
            - name (lookup in mask_consts) pass through
            - number = label index
            - slice (has colon) = label range
    """
    ops = []
    tokens = allow_string.strip().split(',')
    if len(tokens) == 1 and len(tokens[0]) == 0:
        return ops
    for token in tokens:
        if token[0] not in '+-':
            raise ValueError(
                "Invalid allow string token (missing leading +-): %s"
                % (token, ))
        valence = token[0] == '+'
        operation = token[1:]
        if ':' in operation:  # slice
            sub_tokens = operation.split(':')
            if len(sub_tokens) != 2:
                raise ValueError(
                    "Invalid allow string token (slice has >2 values): %s"
                    % (token, ))
            for v in sub_tokens:
                if not v.isdigit():
                    raise ValueError(
                        "Invalid allow string token (slice not digit): %s"
                        % (token, ))
            op = ('slice', sub_tokens[0], sub_tokens[1])
        elif operation.isdigit():  # index
            op = int(operation)
        else:  # name
            if check_consts and operation not in mask_consts:
                raise ValueError(
                    "Invalid allow string token (unknown label): %s"
                    % (token, ))
            op = operation
        ops.append((valence, op))
    return ops


class RunningThreshold:
    def __init__(
            self, n_classes,
            min_n=10, n_std=3.0, min_dev=0.1, threshold=0.9, allow=None):
        self.min_n = min_n
        self.n_std = n_std
        self.min_dev = min_dev
        self.static_threshold = threshold
        if isinstance(allow, (list, tuple)):
            allow = make_allow_mask(n_classes, *allow)
        elif isinstance(allow, str):
            allow = make_allow_mask(n_classes, *parse_allow_mask(allow))
        self.allow = allow

        self.buffers = None
        self.mean = None
        self.std = None
        self.thresholds = None

    def make_buffers(self, b):
        self.buffers = numpy.empty((self.min_n, len(b)))
        self.index = -self.min_n
        self.thresholds = numpy.ones_like(b) * self.static_threshold
        if self.allow is None:
            self.allow = numpy.ones_like(b, dtype=bool)
    
    def update_buffers(self, b):
        if self.buffers is None:
            self.make_buffers(b)
        self.buffers[self.index] = b
        if self.index < 0:  # incomplete buffers
            self.index += 1
            # use default thresholds or don't trigger
            self.mean = None
            self.std = None
        else:
            self.index = (self.index + 1) % self.min_n
            # recompute mean and std
            self.mean = numpy.mean(self.buffers, axis=0)
            self.std = numpy.std(self.buffers, axis=0)

    def check(self, b):
        b = numpy.squeeze(b)
        self.update_buffers(b)
        d = b > self.thresholds
        if self.mean is not None:
            dev = self.std * self.n_std
            dev[dev < self.min_dev] = self.min_dev
            # use running avg
            d = numpy.logical_or(
                d,
                numpy.abs(b - self.mean) > dev)
        md = numpy.logical_and(d, self.allow)
        info = {
            'masked_detection': md,
            'indices': numpy.nonzero(md)[0],
        }
        return numpy.any(md), info
    
    def __call__(self, b):
        return self.check(b)


class Trigger:
    def __init__(
            self, duty_cycle, post_time, min_time, max_time):
        self.duty_cycle = duty_cycle
        self.min_time = min_time
        self.max_time = max_time
        self.post_time = post_time
        if duty_cycle == 0.0:
            raise ValueError("Invalid duty cycle, cannot be 0")
        self.hold_off_dt = (max_time + post_time) * (1. / self.duty_cycle - 1.)
        self.triggered = False

        self.times = {}
        self.meta = {}

        self.active = None

    def activate(self, t):
        self.times['start'] = t
        self.active = True
    
    def deactivate(self, t):
        self.active = False

    def rising_edge(self):
        self.times['rising'] = time.monotonic()
        if not self.active:
            self.activate(self.times['rising'])
            return True
        return False

    def falling_edge(self):
        self.times['falling'] = time.monotonic()
        if 'hold_off' in self.times:
            del self.times['hold_off']
        if not self.active:
            self.activate(self.times['falling'])
            return True
        return False

    def high(self):
        t = time.monotonic()
        if 'rising' not in self.times:
            self.rising_edge()
        # check duty cycle
        if self.active:
            if t - self.times['start'] >= self.max_time:
                if self.duty_cycle != 1.0:
                    # stop recording, go into hold off
                    self.deactivate(t)
                    self.times['hold_off'] =  t + self.hold_off_dt
        else:
            if 'hold_off' in self.times and t >= self.times['hold_off']:
                self.activate(t)
                return True
        return False

    def low(self):
        if self.active:
            t = time.monotonic()
            if 'falling' not in self.times:
                self.falling_edge()
            # stop after post_record and min_time
            if (
                    (t - self.times['falling'] >= self.post_time) and
                    (t - self.times['start'] >= self.min_time)):
                self.deactivate(t)
        return False

    def set_trigger(self, trigger, meta):
        self.last_meta = self.meta
        self.meta = meta
        if self.triggered:
            if trigger:
                self.meta['state'] = 'high'
                r = self.high()
            else:
                self.meta['state'] = 'falling_edge'
                r = self.falling_edge()
        else:
            if trigger:
                self.meta['state'] = 'rising_edge'
                r = self.rising_edge()
            else:
                self.meta['state'] = 'low'
                r = self.low()
        self.triggered = trigger
        return r

    def __call__(self, trigger, meta):
        return self.set_trigger(trigger, meta)


class TriggeredRecording(Trigger):
    def __init__(
            self, url, video_directory, still_directory, name,
            duty_cycle=0.1, post_time=1.0, min_time=3.0, max_time=10.0,
            save_video=True, periodic_still=False):
        self.video_directory = video_directory
        self.still_directory = still_directory
        self.name = name
        super(TriggeredRecording, self).__init__(
            duty_cycle, post_time, min_time, max_time)

        self.filename = None

        # set save_video to false to prevent any video saving
        self.save_video = save_video

        # save a still image every N seconds (0 = don't save)
        self.periodic_still = periodic_still

        self.url = url
        # TODO pre record time
        self.index = -1

        if self.save_video:
            # only need a recorder if videos are saved
            self.build_recorder()
        #self.recorder = gstrecorder.Recorder(url=self.url)
        #self.recorder.start()

    def build_recorder(self):
        #self.recorder = something
        raise NotImplementedError("Abstract base class")

    def video_filename(self, meta):
        if 'datetime' in meta:
            dt = meta['datetime']
        else:
            dt = datetime.datetime.now()
        d = os.path.join(self.video_directory, dt.strftime('%y%m%d'))
        if not os.path.exists(d):
            os.makedirs(d)
        return os.path.join(
            d,
            '%s_%s.mp4' % (dt.strftime('%H%M%S_%f'), self.name))

    def still_filename(self, meta):
        if 'datetime' in meta:
            dt = meta['datetime']
        else:
            dt = datetime.datetime.now()
        d = os.path.join(self.still_directory, dt.strftime('%y%m%d'))
        if not os.path.exists(d):
            os.makedirs(d)
        return os.path.join(
            d,hstname1+'_%s_%s.jpg' % (dt.strftime('%H%M%S_%f'), self.name))

    def activate(self, t):
        super(TriggeredRecording, self).activate(t)
        if not self.save_video:
            return
        if self.recorder.filename is not None:
            self.recorder.stop_saving()  # TODO instead switch files?

        # make new filename
        self.index += 1
        self.meta['video_index'] = self.index
        self.meta['camera_name'] = self.name
        vfn = self.video_filename(self.meta)
        self.meta['filename'] = vfn
        #fn = self.filename_gen(self.index, self.meta)

        # TODO wait for stop_saving to finish?

        # start saving
        logging.info("Saving to %s", vfn)
        print("~~~ Started recording [%s] ~~~" % vfn)
        self.recorder.start_saving(vfn)
        self.filename = vfn

    def deactivate(self, t):
        super(TriggeredRecording, self).deactivate(t)
        if not self.save_video:
            return
        if self.recorder.filename is not None:
            print("~~~ Stop recording ~~~")
            self.recorder.stop_saving()
            self.filename = None

    def new_image(self, im):
        # allow object to optionally buffer images
        pass

    def save_image(self, im):
        self.meta['camera_name'] = self.name
        fn = self.still_filename(self.meta)
        logging.info("Saving still to %s", fn)
        # TODO save image, in thread?
        # swap RGB->BGR
        cv2.imwrite(fn, im[:, :, ::-1])
        return fn


class GSTTriggeredRecording(TriggeredRecording):
    def build_recorder(self):
        # need to tell recorder pre/post/etc
        logging.debug("Building GST recorder")
        self.recorder = gstrecorder.GSTRecorder(url=self.url)
        self.recorder.start()


class CVTriggeredRecording(TriggeredRecording):
    def build_recorder(self):
        logging.debug("Building CV recorder")
        self.recorder = cvrecorder.CVRecorder(url=self.url)
        self.recorder.start()

    def new_image(self, im):
        if hasattr(self, 'recorder'):
            self.recorder.new_image(im)

        # check if image should be saved based on timer
        if self.periodic_still:
            t = time.monotonic()
            if (
                    not hasattr(self, 'last_still_time') or
                    t - self.last_still_time >= self.periodic_still):
                self.save_image(im)
                self.last_still_time = t


def test():

    def run_trigger(trig, N, ts_func, tick=0.001): 
        # run trigger for N seconds, monitor on/off times
        st = time.monotonic()
        stats = {
            'start': st,
            'on_times': [],
            'off_times': [],
            'on_time': 0.,
            'off_time': 0.,
        }
        t = st
        s = None
        last_state_change_time = None
        while t - st <= N:
            dt = t - st
            trig.set_trigger(ts_func(dt), {})
            if s is not None:
                if s and not trig.active:  # trigger deactivated
                    stats['on_time'] += (
                        t - last_state_change_time)
                    last_state_change_time = t
                    stats['off_times'].append(dt)
                elif not s and trig.active:  # trigger activated
                    stats['off_time'] += (
                        t - last_state_change_time)
                    last_state_change_time = t
                    stats['on_times'].append(dt)
            else:
                if trig.active:
                    stats['on_times'].append(dt)
                else:
                    stats['off_times'].append(dt)
                last_state_change_time = t
            s = trig.active
            time.sleep(tick)
            t = time.monotonic()

        # add last period
        if trig.active:
            stats['on_time'] += (t - last_state_change_time)
        else:
            stats['off_time'] += (t - last_state_change_time)

        stats['duty'] = stats['on_time'] / N
        return stats


    N = 1.0
    duty = 0.01
    post_time = 0.001
    min_time = 0.005
    max_time = 0.01

    acceptable_duty_error = 0.1

    # test all on
    trig = Trigger(duty, post_time, min_time, max_time)
    stats = run_trigger(trig, N, lambda dt: True)
    if abs(stats['duty'] - duty) > (duty * acceptable_duty_error):
        raise Exception("Bad duty cycle: %s != %s" % (stats['duty'], duty))

    # across various duty cycles
    for dc in (0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        trig = Trigger(dc, post_time, min_time, max_time)
        stats = run_trigger(trig, N, lambda dt: True)
        if abs(stats['duty'] - dc) > (dc * acceptable_duty_error):
            raise Exception("Bad duty cycle: %s != %s" % (stats['duty'], dc))
        print(dc, stats['duty'])

    # test all off
    trig = Trigger(duty, post_time, min_time, max_time)
    stats = run_trigger(trig, N, lambda dt: False)
    assert stats['duty'] < acceptable_duty_error

    # test min time
    N = 0.015
    trig = Trigger(duty, post_time, min_time, max_time)
    stats = run_trigger(trig, N, lambda dt: dt < 0.002, tick=0.0001)
    assert abs(stats['on_time'] - min_time) < 0.005

    # test max time
    trig = Trigger(duty, post_time, min_time, max_time)
    stats = run_trigger(trig, N, lambda dt: True, tick=0.0001)
    assert abs(stats['on_time'] - max_time) < 0.005
