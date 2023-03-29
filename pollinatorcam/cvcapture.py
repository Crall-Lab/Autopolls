import logging
import threading
import time

import cv2


class CVCaptureThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.cam = kwargs.pop('cam')
        if 'retry' in kwargs:
            self.retry = kwargs.pop('retry')
        else:
            self.retry = False
        kwargs['daemon'] = kwargs.get('daemon', True)
        properties = kwargs.pop('properties', {})

        # limit capture rate to at most N seconds
        self.capture_period = kwargs.pop('capture_period', 0)
        self.last_capture_time = time.monotonic() - self.capture_period

        super(CVCaptureThread, self).__init__(*args, **kwargs)

        if hasattr(self.cam, 'rtsp_url'):
            self.url = self.cam.rtsp_url(channel=1, subtype=1)
        else:
            self.url = self.cam
        self._start_cap(properties)

        self.error = None
        self.keep_running = True

        self.timestamp = None
        self.image = None
        self.image_ready = threading.Condition() 


    def _start_cap(self, properties=None):
        if hasattr(self, 'cap'):
            del self.cap
        self.cap = cv2.VideoCapture(self.url)
        #self.cap = cv2.VideoCapture(0)
        #logging.info("Cap started with backend: %s", self.cap.getBackendName())

        # TODO settings should be dynamic to allow focus adjustment
        if properties is not None:
            self.set_properties(properties)

    def set_properties(self, properties, retries=5):
        # reorder list of property names to have some elements first
        pnames = list(properties.keys())
        fi = 0
        for k in ('fourcc', 'frame_width', 'frame_height'):
            if k in pnames:
                i = pnames.index(k)
                pnames[fi], pnames[i] = pnames[i], pnames[fi]
                fi += 1
        set_values = {}
        for name in pnames:
            value = properties[name]
            if isinstance(name, str):
                if 'CAP_PROP_' not in name:
                    name = 'CAP_PROP_' + name.upper()
            #old_value = cap.get(getattr(cv2, attr))
            if 'FOURCC' in name:
                #old_value = parse_fourcc(old_value)
                if isinstance(value, str):
                    value = cv2.VideoWriter_fourcc(*value)
            attr = getattr(cv2, name)
            # set property
            logging.info("attempt set %s to %s" % (name, value))
            self.cap.set(attr, value)
            set_values[name] = (attr, value)

        # check set properties
        retry = False
        for name in set_values:
            attr, target_value = set_values[name]
            actual_value = self.cap.get(attr)
            logging.info("actual value of %s = %s" % (name, actual_value))
            # TODO float vs int?
            if actual_value != target_value:
                print("Failed to set video property %s[%s] to %s" % (name, actual_value, target_value))
                retry = True
        if retry:
            if retries == 0:
                raise Exception("Failed to set properties after retrying")
            logging.warning("retrying property settings...")
            return self.set_properties(properties, retries - 1)
        logging.info("set_properties finished successfully")

    def _read_frame(self):
        t = time.monotonic()
        if (t - self.last_capture_time) < self.capture_period:
            # grab (and throw out) frame
            self.cap.grab()
            return
        r, im = self.cap.read()
        self.last_capture_time = t
        #r, im = self.cap.read()
        # convert to rgb
        if not r or im is None:
            raise Exception("Failed to capture: %s, %s" % (r, im))
        with self.image_ready:
            #if self.timestamp is not None:
            #    print("Frame dt:", time.time() - self.timestamp)
            self.timestamp = time.time()
            self.image = im[:, :, ::-1]  # BGR to RGB
            self.error = None
            self.image_ready.notify()

    def run(self):
        while self.keep_running:
            try:
                self._read_frame()
            except Exception as e:
                with self.image_ready:
                    self.error = e
                    self.timestamp = time.time()
                    self.image = None
                    self.image_ready.notify()
                if not self.retry:
                    break
                logging.info("Restarting capture: %s[%s]", self.url, e)
                self._start_cap()

    def next_image(self, timeout=None):
        with self.image_ready:
            if not self.image_ready.wait(timeout=timeout):
                raise RuntimeError("No new image within timeout")
            if self.error is None:
                return True, self.image, self.timestamp
            return False, self.error, self.timestamp

    def stop(self):
        if self.is_alive():
            self.keep_running = False
            self.join()

    def __del__(self):
        self.stop()
