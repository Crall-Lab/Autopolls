"""
To try for circular buffer
1) rtspsrc: buffer-mode=2 latency=2000 drop-on-latency=true [and remove all queues], no go

Start of video artifact fix:
1) set alignment of h265parse to "au" (only output full frames): causes the pipeline to die

flushing?
rtspjitterbuffer why reset skew correction? seems ok as the buffering supposedly still happens
jitterbuffer dropping older than base time, only seems to happen at the beginning

all latency shit in rtspsrc seems to do nothing
"""

import os
import subprocess
import sys
import time
import threading

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject


url_string = "rtsp://{user}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"

rtsp_cmd_string = (  # TODO configure queue latency/max-size-time/etc?
    'rtspsrc name=src0 location="{url}" ! '
    'capsfilter name=caps0 caps=application/x-rtp,media=video ! '
    #'queue name=queue0 max-size-bytes=0 max-size-buffers=0 leaky=2 silent=true max-size-time=2000000000 min-threshold-time=1500000000 ! '  # this is the 'delay'
    #'queue name=queue0 max-size-bytes=0 max-size-buffers=0 leaky=2 silent=true max-size-time=2500000000 min-threshold-time=2000000000 ! '  # this is the 'delay'
    'queue name=queue0 max-size-bytes=0 max-size-buffers=0 leaky=2 silent=true max-size-time=7000000000 min-threshold-time=5000000000 ! '  # this is the 'delay'
    'fakesink name=fakesink0 sync=false '
)

usb_cmd_string = (
    'v4l2src device="{url}" ! '
    # size/resolution selection?
    'jpegdec ! '
    'queue name=queue0 max-size-bytes=0 max-size-buffers=0 leaky=2 silent=true max-size-time=7000000000 min-threshold-time=5000000000 ! '  # this is the 'delay'
    'fakesink name=fakesink0 sync=false '
)




class GSTRecorder(threading.Thread):
    _inited = False
    def __init__(self, *args, **kwargs):
        self.url = kwargs.pop('url')
        if 'daemon' not in kwargs:
            kwargs['daemon'] = True
        super(Recorder, self).__init__(*args, **kwargs)

        if not self._inited or not Gst.is_initialized():
            Gst.init([])
            self._inited = True

        if 'rtsp' in self.url:
            cmd_string = rtsp_cmd_string
        else:
            cmd_string = usb_cmd_string
        self.pipeline = Gst.parse_launch(
            cmd_string.format(url=self.url))

        self.queue = self.pipeline.get_child_by_name("queue0")
        #self.caps0 = self.pipeline.get_child_by_name("caps0")
        self.fakesink = self.pipeline.get_child_by_name("fakesink0")

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self._on_message_cb = self.bus.connect("message", self.on_message)

        self.filename = None
        self.playmode = False

    def teardown(self):
        if hasattr(self, 'bus'):
            self.bus.disconnect(self._on_message_cb)
            self.bus.remove_signal_watch()
            del self.bus

    def __del__(self):
        if self.playmode:
            self.stop_pipeline()

    def on_message(self, bus, message):
        t = message.type
        if t & Gst.MessageType.EOS:
            print("!!! End of stream !!!")
            if self.filename is not None:
                self.stop_filesink()
            else:
                self.pipeline.set_state(Gst.State.NULL)
                self.playmode = False
                self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            self.pipeline.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            print("Error: %s[%s]" % (err, debug))
            self.playmode = False
            self.loop.quit()
        elif t & Gst.MessageType.LATENCY:
            print("Latency message:", t)
        #print(t, message)

    def stop_element(self, element):
        #print("stop_element")
        element.set_state(Gst.State.NULL)
        return GLib.SOURCE_REMOVE  # needed?

    def stop_filesink(self):
        #print("=======================")
        #print("==== stop filesink ====")
        #print("=======================")
        self.depay.set_locked_state(True)
        self.parse.set_locked_state(True)
        self.parse_caps.set_locked_state(True)
        self.mux.set_locked_state(True)
        self.filesink.set_locked_state(True)

        self.depay.set_state(Gst.State.NULL)
        self.parse.set_state(Gst.State.NULL)
        self.parse_caps.set_state(Gst.State.NULL)
        self.mux.set_state(Gst.State.NULL)
        self.filesink.set_state(Gst.State.NULL)

        self.pipeline.remove(self.depay)
        self.pipeline.remove(self.parse)
        self.pipeline.remove(self.parse_caps)
        self.pipeline.remove(self.mux)
        self.pipeline.remove(self.filesink)

        self.filename = None

    def drop_buffer_cb(self, pad, info):
        flags = info.get_buffer().get_flags()
        print("Buffer flags: ", flags)
        if flags != 0:
            # complete buffer stop dropping
            print("Dropping incomplete buffer...")
            return Gst.PadProbeReturn.DROP
        print("Done dropping")
        return Gst.PadProbeReturn.REMOVE

    def create_filesink(self, fn):
        # TODO use GstBin instead
        self.depay = Gst.ElementFactory.make('rtph265depay', 'depay0')
        self.parse = Gst.ElementFactory.make('h265parse', 'parse0')
        # TODO connect pad probe to parse src pad, drop buffers until full frame
        src_pad = self.parse.get_static_pad('src')
        src_pad.add_probe(Gst.PadProbeType.BUFFER, self.drop_buffer_cb)
        self.parse_caps = Gst.ElementFactory.make('capsfilter', 'caps1')
        #self.parse_caps.set_property(
        #    'caps',
        #    Gst.Caps('video/x-h265, stream-format=byte-stream, alignment=au')
        #)
        # TODO set parse caps alignment to au
        self.mux = Gst.ElementFactory.make('mp4mux', 'mux0')
        self.filesink = Gst.ElementFactory.make('filesink', 'filesink0')
        self.filesink.set_property('location', fn)
        self.filesink.set_property('async', False)  # don't close async
        # TODO TEST sync False
        self.filesink.set_property('sync', False)  # don't drop non-synced buffered
        # TEST ts_offset + to delay rendering: nope, nope, nope
        #self.filesink.set_property('ts-offset', 3 * Gst.SECOND)
        #self.filesink.set_property('max-lateness', -1)
        #self.filesink.set_property('render-delay', 3 * Gst.SECOND)
        self.filename = fn

        #self.pipeline.add(self.depay, self.parse, self.mux, self.filesink)
        self.pipeline.add(
            self.depay, self.parse, self.parse_caps, self.mux, self.filesink)

        self.depay.link(self.parse)
        self.parse.link(self.parse_caps)
        #self.parse.link(self.mux)
        self.parse_caps.link(self.mux)
        self.mux.link(self.filesink)

    def insert_filesink(self, pad, info, fn):
        print("insert_filesink")
        peer = pad.get_peer()
        pad.unlink(peer)
        self.pipeline.remove(self.fakesink)
        GLib.idle_add(self.stop_element, self.fakesink)

        self.create_filesink(fn)

        # link pad [rtsp src pad] to depay
        pad.link(self.depay.get_static_pad('sink'))
        self.depay.sync_state_with_parent()
        self.parse.sync_state_with_parent()
        self.parse_caps.sync_state_with_parent()
        self.mux.sync_state_with_parent()
        self.filesink.sync_state_with_parent()
        return Gst.PadProbeReturn.REMOVE  # don't call again

    def insert_fakesink(self, pad, info):
        #print("insert_fakesink")
        peer = pad.get_peer()
        pad.unlink(peer)

        m = Gst.Event.new_eos()
        r = peer.send_event(m)
        if not r:
            print("Failed sending eos to insert_fakesink")

        self.fakesink = Gst.ElementFactory.make('fakesink', 'fakesink0')
        self.fakesink.set_property('sync', False)
        self.pipeline.add(self.fakesink)

        pad.link(self.fakesink.get_static_pad('sink'))
        self.fakesink.sync_state_with_parent()
        return Gst.PadProbeReturn.REMOVE

    def start_saving(self, fn):
        #print("++++++++++++++++++++++")
        #print("++++ Start saving ++++")
        #print("++++++++++++++++++++++")
        # get src pad of queue
        src_pad = self.queue.get_static_pad('src')
        #src_pad = self.caps0.get_static_pad('src')
        src_pad.add_probe(Gst.PadProbeType.IDLE, self.insert_filesink, fn)
        #GLib.timeout_add(500, self._set_latency)
        return

    def stop_saving(self):
        #print("---------------------")
        #print("---- Stop saving ----")
        #print("---------------------")
        src_pad = self.queue.get_static_pad('src')
        #src_pad = self.caps0.get_static_pad('src')
        src_pad.add_probe(Gst.PadProbeType.IDLE, self.insert_fakesink)
        #GLib.timeout_add(500, self._set_latency)
        return

    def stop_pipeline(self, and_join=True):
        m = Gst.Event.new_eos()
        #print("Made EOS")
        r = self.pipeline.send_event(m)
        if not r:
            print("Failed to send eos to pipeline")
        #print("send_event(EOS) = %s" % r)
        #print("Sent EOS")
        if and_join:
            self.join()
            self.teardown()

    def print_pipeline_states(self, and_pads=False):
        for i in range(self.pipeline.get_children_count()):
            try:
                node = self.pipeline.get_child_by_index(i)
                s = node.get_state(0.001)[1]
                if s == Gst.State.NULL:
                    ss = '__ null __'
                elif s == Gst.State.PLAYING:
                    ss = '++ PLAYING ++'
                else:
                    ss = '  %s  ' % s.value_nick
                print(i, '\t', ss, '\t', node.name)
                if not and_pads:
                    continue
                for p in node.pads:
                    print("\t" * 5, p.name, p.is_active())
            except Exception as e:
                print(i, 'ERROR', e)
    
    def periodic_cb(self):
        #return GLib.SOURCE_REMOVE
        print(self.pipeline.get_latency())
        print(self.pipeline.get_child_by_name('src0').get_property('latency'))
        #self.print_pipeline_states()
        return GLib.SOURCE_CONTINUE

    def _set_latency(self):
        print("Set latency")
        self.pipeline.set_latency(3 * Gst.SECOND)
        print(self.pipeline.get_latency())
        return GLib.SOURCE_REMOVE

    def run(self):
        self.playmode = True
        self.loop = GLib.MainLoop()
        #GLib.timeout_add(500, self.periodic_cb)

        self.pipeline.set_state(Gst.State.PLAYING)
        #GLib.timeout_add(500, self._set_latency)
        self.loop.run()
        self.playmode = False


def test_recorder(ip='192.168.0.4'):
    url = url_string.format(
        user=os.environ['PCAM_USER'],
        password=os.environ['PCAM_PASSWORD'],
        ip=ip)

    class Ticker:
        def tick(self):
            self.t0 = time.monotonic()

        def tock(self):
            self.dt = time.monotonic() - self.t0
            return self.dt

    t = Ticker()
    for fn in ('test_file.mp4', 'test_file2.mp4'):
        # create recorder instance
        r = Recorder(url=url)
        # start running (begins filling circular buffer)
        r.start()
        time.sleep(1)  # wait a bit

        # start actually recording (frames will be delayed by buffer)
        t.tick()
        r.start_saving(fn)
        t.tock()
        print("Start recording took", t.dt)

        time.sleep(3)
        # stop recording and join started thread
        t.tick()
        r.stop_saving()
        t.tock()
        print("Stop recording took", t.dt)

        t.tick()
        r.stop_pipeline()
        t.tock()
        print("Joining took", t.dt)
        time.sleep(2)


def test_for_open_files(ip='192.168.0.103'):
    url = url_string.format(
        user=os.environ['PCAM_USER'],
        password=os.environ['PCAM_PASSWORD'],
        ip=ip)

    # get process id
    pid = os.getpid()
    get_open_files = lambda: len(
        subprocess.check_output(
            ['lsof', '-p', str(pid)]).decode('ascii').splitlines())
    tnof = None
    for index in range(10):
        fn = '%04i.mp4' % index
        print("Index: %i, fn: %s" % (index, fn))
        #r = Recorder(filename=fn, ip=ip, pre_record_time=1000)
        r = Recorder(url=url)
        print("\tStarting")
        r.start()
        #time.sleep(1.0)
        r.start_saving(fn)

        print("\tRecording...")
        time.sleep(2.0)

        print("\tStopping...")
        r.stop_saving()

        print("\tClosing")
        time.sleep(1.0)
        r.stop_pipeline()

        # print number of open files
        nof = get_open_files()
        if tnof is None:
            tnof = nof
        print("\tDone, open Files: %i" % (nof, ))
        #if nof != tnof:
        #    raise Exception("File open leak")
        #time.sleep(1.0)


if __name__ == '__main__':
    ip = None
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    #test_recorder(ip)
    test_for_open_files(ip)
