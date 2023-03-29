"""
"""

import subprocess
import sys
import time
import threading

import cv2


video_settings = {
    'fourcc': 'mp4v',
    'framesize': (2592, 1944),  #TODO?
    'fps': 5,  # TODO?
}


class CVRecorder(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.filename = None
        self.writer = None
        url = kwargs.pop('url')
        super().__init__(*args, **kwargs)

    def run(self):
        # TODO thread run function
        # wait for new image (signal, pipe, etc) from new_image
        # write new_image to filename
        while True:
            time.sleep(1)
            pass

    def start_saving(self, fn):
        # TODO write in thread
        self.filename = fn
        # fn, fourcc, fps, framesize, iscolor
        self.writer = cv2.VideoWriter(
            fn, cv2.VideoWriter_fourcc(*video_settings['fourcc']),
            video_settings['fps'],
            video_settings['framesize'],
            True)

    def stop_saving(self):
        # TODO write in thread
        self.filename = None
        self.writer.release()
        self.writer = None

    def new_image(self, im):
        # TODO write in thread
        # TODO pre record period?
        if self.writer is not None:
            # TODO swap rgb to bgr
            self.writer.write(im)
