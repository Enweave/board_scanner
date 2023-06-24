import os
import typing

from fps_limiter import LimitFPS

from modules import BRIGHTNESS_KEY, CONTRAST_KEY, BW_KEY
from modules.camera import Droidcam
from modules.utils import apply_brightness_contrast, mk_trakbar
import numpy as np
import cv2


class ScannerApp:
    def __init__(
        self,
        window_name: str = "board_scanner",
        fps_limit: int = 30,
        webcam_index: int = 0,
        still_image: typing.Union[str, os.PathLike] = None,
    ):
        self._window_name = window_name
        self._fps_limit = fps_limit
        self._img_filter_params = {
            BRIGHTNESS_KEY: 127,
            CONTRAST_KEY: 127,
            BW_KEY: 0,
        }
        self._webcam_index = webcam_index
        self._still_image = still_image

        self._fps_limiter = LimitFPS(fps=self._fps_limit)
        self._camera = self._setup_camera()

        self._setup_window()
        self._setup_trackbars()

    def _cycle(self):
        frame = self._camera.read()
        frame = self._apply_filters(frame)
        cv2.imshow(self._window_name, frame)

    def _stop(self):
        self._camera.__del__()
        cv2.destroyAllWindows()

    def run(self):
        while True:
            if cv2.waitKey(1) == ord("q"):
                self._stop()
                break
            if self._fps_limiter():
                self._cycle()

    def _setup_window(self):
        cv2.namedWindow(self._window_name)

    def _setup_trackbars(self):
        mk_trakbar(self._window_name, self._img_filter_params, BRIGHTNESS_KEY, 255)
        mk_trakbar(self._window_name, self._img_filter_params, CONTRAST_KEY, 255)
        mk_trakbar(self._window_name, self._img_filter_params, BW_KEY, 1)

    def _apply_filters(self, img: np.ndarray) -> np.ndarray:
        img = apply_brightness_contrast(
            img,
            self._img_filter_params.get(BRIGHTNESS_KEY),
            self._img_filter_params.get(CONTRAST_KEY),
        )
        if self._img_filter_params.get(BW_KEY):
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _setup_camera(self) -> Droidcam:
        if self._still_image:
            return Droidcam(
                use_webcam=False, img_src=self._still_image
            )
        else:
            return Droidcam(
                use_webcam=True, webcam_index=self._webcam_index
            )
