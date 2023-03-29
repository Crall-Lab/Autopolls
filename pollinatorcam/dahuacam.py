# Maybe just use amcrest for a fuller api and hack together an
# api for JUST what I need
# - whatever is needed for camera configuration
# - fps control

import argparse
import datetime
import os
import urllib
import socket

import requests


def build_camera_url(
        ip, user=None, password=None, channel=1, subtype=0):
    if user is None:
        user = os.environ['PCAM_USER']
    if password is None:
        password = os.environ['PCAM_PASSWORD']
    return (
        "rtsp://{user}:{password}@{ip}:554"
        "/cam/realmonitor?channel={channel}&subtype={subtype}".format(
            user=user,
            password=password,
            ip=ip,
            channel=channel,
            subtype=subtype))


def mac_address_to_name(cam):
    mac = cam.get_config('Network.eth0.PhysicalAddress').strip().split('=')[1]
    return ''.join(mac.split(':'))


def initial_configuration(c, reboot=True):
    # TODO combine with snap config
    # TODO pull out a 'config' structure that contains settings
    # TODO add error checking
    config_result = {}
    if c.password != os.environ['PCAM_PASSWORD']:
        r = c.set_password(os.environ['PCAM_PASSWORD'])
        config_result['password'] = r

    # set current time
    r = c.set_current_time()
    config_result['time'] = r

    # extra format
    prefix = 'Encode[0].ExtraFormat[0].Video'
    config = [
        #('resolution', '352x240'),
        #('Height', '240'),
        #('Width', '352'),
        #('CustomResolutionName', 'CIF'),
        #('BitRate', '128'),

        ('resolution', '640x480'),
        ('Height', '480'),
        ('Width', '640'),
        ('CustomResolutionName', 'VGA'),
        ('BitRate', '512'),

        ('BitRateControl', 'VBR'),
        ('Compression', 'H.265'),
        ('FPS', '10'),
        ('GOP', '20'),
        ('Pack', 'DHAV'),
        ('Priority', '0'),
        ('Profile', 'Main'),
        ('Quality', '4'),
        ('QualityRange', '6'),
        ('SVCTLayer', '1'),
    ]
    r = c.set_config(config, prefix=prefix)
    config_result['extra'] = r
    #print("Set %s: %s" % (prefix, r))

    #table.Encode[0].ExtraFormat[0].VideoEnable=true

    # main format
    prefix = 'Encode[0].MainFormat[0].Video'
    # GOP of 1 makes 'blocky' videos
    # GOP != 1 makes artifact full videos (with valve at front of pipeline)
    # testing GOP == 5 with valve at end
    config = [
        ('resolution', '2592x1944'),
        ('BitRate', '4096'),
        ('BitRateControl', 'VBR'),
        ('Compression', 'H.265'),
        ('CustomResolutionName', '2592x1944'),
        ('FPS', '5'),
        #('GOP', '1'),  # TODO needed for valve, does this make larger videos?
        ('GOP', '5'),  # TODO needed for valve, does this make larger videos?
        ('Height', '1944'),
        ('Pack', 'DHAV'),
        ('Priority', '0'),
        ('Profile', 'Main'),
        ('Quality', '4'),
        ('QualityRange', '6'),
        ('SVCTLayer', '1'),
        ('Width', '2592'),
    ]
    r = c.set_config(config, prefix=prefix)
    config_result['main'] = r
    #print("Set %s: %s" % (prefix, r))

    #table.Encode[0].MainFormat[0].VideoEnable=true

    # disable motion detection
    r = c.set_config([
        ('MotionDetect[0].Enable', 'false'),
        ('MotionDetect[0].EventHandler.RecordEnable', 'false'),
    ])

    # videowidget overlay
    t = c.get_video_widget()
    config = []
    for l in t.splitlines():
        if 'EncodeBlend' in l:
            k = '.'.join(l.split('.')[1:]).split('=')[0]
            config.append((k, 'false'))
    r = c.set_config(config)
    config_result['widget'] = r

    # set name to mac address
    mac = c.get_config('Network.eth0.PhysicalAddress').strip().split('=')[1]
    name = ''.join(mac.split(':'))
    r = c.set_config([('General.MachineName', name),])
    config_result['name'] = r

    # TODO enable ftp
    # TODO snapshot schedule
    # TODO snapshot saving
    # TODO snapshot period
   
    # TODO reboot
    if reboot:
        c.reboot()
    return config_result


def set_record_config(c, enable):
    prefix = 'Record[0]'
    config = [
        ('HolidayEnable', 'true'),
        ('PreRecord', '0'),
    ]
    key_bs = 'TimeSection[{}][0]'
    value_bs = '{}%2000:00:00-23:59:59'
    for ts in range(8):
        k = key_bs.format(ts)
        v = value_bs.format(int(enable))
        config.append((k, v))
    r = c.set_config(config, prefix=prefix)
    return r


def set_continuous_video():
    # TODO RecordStoragePoint[0].TimingRecord.FTP=true
    # TODO MediaGlobal.PacketLength (video length in minutes?)
    # TODO Record[0]:
    # - HolidayEnable=true
    # - TimeSection[0-7][0]=1 00:00:00-23:59:59
    # - Stream = 0? what is this setting?
    # TODO nas config, fps, etc
    pass


def set_snap_config(c, nas=None, fps=1/60.):
    if nas is None:
        nas = {'user': 'ipcam', 'enable': True}
    if 'ip' not in nas:
        nas['ip'] = get_host_ip(c.ip)
    if ('user' not in nas) and ('PCAM_NAS_USER' in os.environ):
        nas['user'] = os.environ['PCAM_NAS_USER']
    if ('password' not in nas) and ('PCAM_NAS_PASSWORD' in os.environ):
        nas['password'] = os.environ['PCAM_NAS_PASSWORD']
    for k in ('ip', 'user', 'password'):
        assert k in nas, "nas config missing %s" % k

    config_result = {}

    # set current time
    r = c.set_current_time()
    config_result['time'] = r

    # set storage location
    # TODO RecordStoragePoint[0].TimingRecord.FTP=false
    r = c.set_config([
        ('RecordStoragePoint[0].TimingSnapShot.FTP', 'true'),])
    config_result['storagepoint'] = r

    # Encode[0].SnapFormat[0]
    # - resolution 2592x1944
    # - quality 5
    # - FPS (can be fractional)
    prefix = 'Encode[0].SnapFormat[0].Video'
    config = [
        ('resolution', '2592x1944'),
        ('Quality', '5'),
        ('FPS', str(fps)),
    ]
    r = c.set_config(config, prefix=prefix)
    config_result['encode'] = r

    # Snap[0]:
    # - HolidayEnable=true
    # - TimeSection[0-6][0]=1 00:00:00-23:59:59
    prefix = 'Snap[0]'
    config = [('HolidayEnable', 'true')]
    key_bs = 'TimeSection[{}][{}]'
    value_bs = '{}%2000:00:00-23:59:59'
    for ts in range(8):
        #for dow in range(6):
        for dow in range(1):  # not allowed to set anything other than 0
            k = key_bs.format(ts, dow)
            v = value_bs.format(int(dow == 0))
            config.append((k, v))
    r = c.set_config(config, prefix=prefix)
    config_result['snap'] = r

    # NAS[0]:
    # - Address=<NAS IP>
    # - Enable=true
    # - UserName=<user>
    # - Password=<password>
    prefix = 'NAS[0]'
    config = [
        ('Address', nas['ip']),
        ('UserName', nas['user']),
        ('Password', nas['password']),
        ('Directory', str(nas.get('directory', ' '))),
        ('Enable', str(nas.get('enable', False)).lower()),
    ]
    r = c.set_config(config, prefix=prefix)
    config_result['nas'] = r

    return config_result


class DahuaCameraError(Exception):
    pass


class DahuaCamera:
    def __init__(self, ip, user=None, password=None):
        if user is None:
            user = os.environ['PCAM_USER']
        if password is None:
            password = os.environ['PCAM_PASSWORD']
        self.user = user
        self.password = password
        self.ip = ip

        self.session = requests.Session()
        self.session.auth = requests.auth.HTTPDigestAuth(
            self.user, self.password)

    def rtsp_url(self, channel=1, subtype=0):
        return (
            "rtsp://{user}:{password}@{ip}:554"
            "/cam/realmonitor?channel={channel}&subtype={subtype}".format(
                user=self.user,
                password=self.password,
                ip=self.ip,
                channel=channel,
                subtype=subtype))

    def get_input_caps(self, channel=1):
        url = (
            "http://{ip}/cgi-bin/devVideoInput.cgi?"
            "action=getCaps&channel={channel}".format(
                ip=self.ip, channel=channel))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_record_caps(self):
        url = (
            "http://{ip}/cgi-bin/recordManager.cgi?"
            "action=getCaps".format(ip=self.ip))
        r = self.session.get(url)
        return r.text

    # getConfig = get_input_options, get_config_caps, get_encode_config
    def get_config(self, parameter):
        """Returns video and audio"""
        url = (
            "http://{ip}/cgi-bin/configManager.cgi?"
            "action=getConfig&name={parameter}".format(
                ip=self.ip,
                parameter=parameter))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_input_options(self):
        # TODO parse text, check return code
        return self.get_config('VideoInOptions')

    def set_config(self, config, prefix=None):
        if prefix is None:
            add_prefix = lambda k: k
        else:
            add_prefix = lambda k: '.'.join((prefix, k))
        url = (
            "http://{ip}/cgi-bin/configManager.cgi?"
            "action=setConfig".format(ip=self.ip))
        if len(config) == 0:
            raise ValueError("No parameters provided")
        for c in config:
            assert len(c) == 2
            k, v = c
            url += "&%s=%s" % (add_prefix(k), v)
        #print(url)
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def set_options(self, **kwargs):
        """Set video and audio input options or encode config"""
        url = (
            "http://{ip}/cgi-bin/configManager.cgi?"
            "action=setConfig".format(ip=self.ip))
        if len(kwargs) == 0:
            raise ValueError("No parameters provided")
        for k in kwargs:
            v = kwargs[k]
            url += "&%s=%s" % (k, v)
        r = self.session.get(url)
        # TODO parse text, check return code

    def get_config_caps(self):
        """Returns video and audio"""
        url = (
            "http://{ip}/cgi-bin/encode.cgi?"
            "action=getConfigCaps".format(ip=self.ip))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_encode_config(self):
        """Returns video and audio"""
        # TODO parse text, check return code
        return self.get_config('Encode')

    def get_video_standard(self):
        # TODO parse text, check return code
        return self.get_config('VideoStandard')

    def get_video_widget(self):
        # TODO parse text, check return code
        return self.get_config('VideoWidget')

    def get_network_interfaces(self):
        url = (
            "http://{ip}/cgi-bin/netApp.cgi?"
            "action=getInterfaces".format(ip=self.ip))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_upnp_status(self):
        url = (
            "http://{ip}/cgi-bin/netApp.cgi?"
            "action=getUPnPStatus".format(ip=self.ip))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_network_config(self):
        # TODO parse text, check return code
        return self.get_config('Network')

    def get_pppoe_config(self):
        # TODO parse text, check return code
        return self.get_config('PPPoE')

    def get_ddns_config(self):
        # TODO parse text, check return code
        return self.get_config('DDNS')

    def get_email_config(self):
        # TODO parse text, check return code
        return self.get_config('Email')

    def get_wlan_config(self):
        # TODO parse text, check return code
        return self.get_config('WLan')

    def get_upnp_config(self):
        # TODO parse text, check return code
        return self.get_config('UPnP')

    def get_ntp_config(self):
        # TODO parse text, check return code
        return self.get_config('NTP')

    def get_alarm_server_config(self):
        # TODO parse text, check return code
        return self.get_config('AlarmServer')

    def get_alarm_config(self):
        # TODO parse text, check return code
        # TODO bad request, not sure if this is just not supported
        return self.get_config('Alarm')

    def get_alarm_out_config(self):
        # TODO parse text, check return code
        # TODO bad request, not sure if this is just not supported
        return self.get_config('AlarmOut')

    def get_alarm_url(self, action):
        url = (
            "http://{ip}/cgi-bin/alarm.cgi?"
            "action={action}".format(ip=self.ip, action=action))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_alarm_in_slots(self):
        return self.get_alarm_url('getInSlots')

    def get_alarm_out_slots(self):
        return self.get_alarm_url('getOutSlots')

    def get_alarm_in_states(self):
        return self.get_alarm_url('getInStates')

    def get_alarm_out_states(self):
        return self.get_alarm_url('getOutStates')

    def get_motion_detect_config(self):
        # TODO parse text, check return code
        return self.get_config('MotionDetect')

    def get_blind_detect_config(self):
        # TODO parse text, check return code
        return self.get_config('BlindDetect')

    def get_loss_detect_config(self):
        # TODO parse text, check return code
        return self.get_config('LossDetect')

    def get_event_indices(self, code):
        if code not in ('VideoMotion', 'VideoLoss', 'VideoBlind'):
            raise ValueError("Invalid code")
        url = (
            "http://{ip}/cgi-bin/eventManager.cgi?"
            "action=getEventIndexes&code={code}".format(
                ip=self.ip, code=code))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    # Skipped PTZ

    def get_record_config(self):
        return self.get_config('Record')

    def get_record_mode_config(self):
        return self.get_config('RecordMode')

    def get_snap_config(self):
        return self.get_config('Snap')

    def get_general_config(self):
        return self.get_config('General')

    def get_current_time(self):
        url = (
            "http://{ip}/cgi-bin/global.cgi?"
            "action=getCurrentTime".format(ip=self.ip))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def set_current_time(self, new_datetime=None):
        if new_datetime is None:
            new_datetime = datetime.datetime.now()
        s = datetime.datetime.strftime(new_datetime, "%Y-%m-%d %H:%M:%S")
        qs = urllib.parse.quote(s)
        url = (
            "http://{ip}/cgi-bin/global.cgi?"
            "action=setCurrentTime&time={qs}".format(ip=self.ip, qs=qs))
        r = self.session.get(url)
        # TODO parse text, check return code
        return r.text

    def get_locales_config(self):
        return self.get_config('Locales')

    def set_password(self, password):
        url = (
            "http://{ip}/cgi-bin/userManager.cgi?"
            "action=modifyPassword&name={user}&"
            "pwd={new_password}&pwdOld={password}".format(
                ip=self.ip, user=self.user,
                new_password=password, password=self.password))
        r = self.session.get(url)
        if r.ok:
            self.password = password
            self.session.auth = requests.auth.HTTPDigestAuth(
                self.user, self.password)
        return r.text

    def reboot(self):
        url = (
            "http://{ip}/cgi-bin/magicBox.cgi?action=reboot".format(
                ip=self.ip))
        r = self.session.get(url)
        return r.text

    def get_name(self):
        r = self.get_config('General.MachineName')
        if 'Error' in r or '=' not in r:
            raise DahuaCameraError(r.strip())
        return r.strip().split('=')[1]


def get_host_ip(ip, port=80):
    """Lookup host [this] ip using a camera [or other] ip"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((ip, port))
    return s.getsockname()[0]


def cmdline_run():
    nas = {
        'user': 'ipcam',
        'enable': True,
    }

    # look for options in env
    if 'PCAM_NAS_USER' in os.environ:
        nas['user'] = os.environ['PCAM_NAS_USER']
    if 'PCAM_NAS_PASSWORD' in os.environ:
        nas['password'] = os.environ['PCAM_NAS_PASSWORD']

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-D', '--nasdir', type=str, default=' ',
        help='NAS directory to store snaps')
    parser.add_argument(
        '-F', '--fps', type=float, default=1/60.,
        help="snapshot fps")
    parser.add_argument(
        '-i', '--ip', type=str, required=True,
        help="camera ip address")
    parser.add_argument(
        '-I', '--nasip', type=str,
        help='NAS ip address, if not provided will be looked up')
    parser.add_argument(
        '-k', '--keepalive', action='store_true',
        help='Do not reboot after configuration')
    parser.add_argument(
        '-p', '--password', default=None,
        help='camera password')
    parser.add_argument(
        '-P', '--naspassword', type=str, required='password' not in nas,
        help='NAS password')
    parser.add_argument(
        '-R', '--reboot', action='store_true',
        help='Only reboot camera')
    parser.add_argument(
        '-u', '--user', default=None,
        help='camera username')
    parser.add_argument(
        '-U', '--nasuser', type=str,
        help='NAS user')
    parser.add_argument(
        '-S', '--snaponly', action='store_true',
        help='Only set snap config')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Make output more verbose')
    args = parser.parse_args()

    # host/nas ip from arg or get using socket
    if args.nasip is None:
        nas['ip'] = get_host_ip(args.ip)
    else:
        nas['ip'] = args.nasip
    if args.nasuser is not None:
        nas['user'] = args.nasuser
    if args.naspassword is not None:
        nas['password'] = args.naspassword
    nas['directory'] = args.nasdir

    print("Connecting to camera: %s" % args.ip)
    cam = DahuaCamera(args.ip, args.user, args.password)
    if args.verbose:
        print("Connected:", cam.ip, cam.user, cam.password)
    n = cam.get_name()
    print("Camera name: %s" % n)
    if args.reboot:
        print("Rebooting...")
        return cam.reboot()
    print("Configuring snapshots: %s, %s" % (args.fps, nas))
    sr = set_snap_config(cam, nas, args.fps)
    if not args.snaponly:
        print("Configuring video...")
        ir = initial_configuration(cam, reboot=False)
    else:
        ir = {}
    ok = True
    for d in (sr, ir):
        for k in d:
            if d[k].strip() != 'OK':
                ok = False
                print("Failed to set config %s: %s" % (k, d[k].strip()))
            elif args.verbose:
                print("Configuration result %s: %s" % (k, d[k].strip()))
    if not args.keepalive and ok:
        print("Rebooting...")
        cam.reboot()


if __name__ == '__main__':
    cmdline_run()
