from urllib.request import urlopen

import cv2
import numpy as np
import requests
from imutils.video import WebcamVideoStream
import subprocess


class Droidcam(object):
    """
    Facade for webcam or still image
    """

    #TODO: remove droidcam stuff

    def __init__(
        self,
        ip="192.168.10.241",
        use_webcam=True,
        webcam_index=0,
        img_src=None,
        exposure=30,
        setup=False,
    ):
        self.address = "http://%s:8080" % ip
        self.use_webcam = use_webcam
        self.img = None
        self.setup = setup

        if img_src:
            self.img = cv2.imread(img_src, 1)

            def _read():
                return self.img

        else:
            if use_webcam:
                if self.setup:
                    # TODO: find crossplatform solution
                    props = [
                        "v4l2-ctl -d /dev/video%d -c exposure_auto=1" % webcam_index,
                        "v4l2-ctl -d /dev/video%d -c exposure_auto_priority=0"
                        % webcam_index,
                        # 'v4l2-ctl -d /dev/video%d -c exposure_auto_priority=0' % webcam_index,
                        # 'v4l2-ctl -d /dev/video%d -c exposure_auto=0' % webcam_index,
                        "v4l2-ctl -d /dev/video%d -c exposure_absolute=%d"
                        % (webcam_index, exposure),
                    ]

                    for i, prop in enumerate(props):
                        subprocess.call([prop], shell=True)
                        print(prop)

                # self.vs.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
                # self.vs.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

                # grabMode = self.vs.stream.get(cv2.CAP_PROP_PVAPI_PIXELFORMAT)
                # print(grabMode)
                # result_set = self.vs.stream.set(cv2.CAP_, 1)
                self.vs = WebcamVideoStream(src=webcam_index)
                self.vs.start()

                def _read():
                    return self.vs.read()

            else:

                def _read():
                    frame = urlopen("%s/shot.jpg" % self.address)
                    image = cv2.imdecode(
                        np.array(bytearray(frame.read()), dtype=np.uint8), -1
                    )
                    return image

        self._read = _read

        print("CAM INIT")

    def __del__(self):
        print("CAM DEAD")
        if self.use_webcam:
            self.vs.stop()

    def check(self):
        req = requests.get(self.address)
        return req.status_code

    def send_settings(self):
        param_size = "settings/video_size?set=960x720"
        param_quality = "settings/quality?set=50"
        resp_size = requests.get("%s/%s" % (self.address, param_size))
        resp_quality = requests.get("%s/%s" % (self.address, param_quality))

    def set_flashligth(self, enable=True):
        param = "enabletorch" if enable else "disabletorch"
        responce = requests.get("%s/%s" % (self.address, param))
        return responce.status_code

    def read(self):
        return self._read()

    def read_resize(self, width=300):
        frame = self._read()
        sheight, swidth = frame.shape[:2]

        wpercent = width / float(swidth)
        height = int((float(sheight) * float(wpercent)))
        img = cv2.resize(self._read(), dsize=(width, height))
        return img
