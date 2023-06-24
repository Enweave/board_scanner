import json
import os
import typing

from fps_limiter import LimitFPS

from modules import BRIGHTNESS_KEY, CONTRAST_KEY, BW_KEY, ROI_WIDTH, ROI_HEIGHT, HALFPI
from modules.camera import Droidcam
from modules.utils import apply_brightness_contrast, mk_trakbar, drawAxis
import numpy as np
import cv2


class ScannerApp:
    def __init__(
        self,
        window_name: str = "board_scanner",
        fps_limit: int = 30,
        webcam_index: int = 0,
        still_image: typing.Union[str, os.PathLike] = None,
        use_default_session_settings: bool = False,
    ):
        self._window_name = window_name
        self._fps_limit = fps_limit
        self._use_default_session_settings = use_default_session_settings
        self.settings_path = f"{window_name}_settings.json"

        self.SESSION_SETTINGS = self._load_session_settings()
        self._webcam_index = webcam_index
        self._still_image = still_image

        self._fps_limiter = LimitFPS(fps=self._fps_limit)
        self._camera = self._setup_camera()

        self._setup_window()
        self._setup_trackbars()

    def _load_session_settings(self) -> dict:
        default_settings = {
                BRIGHTNESS_KEY: 127,
                CONTRAST_KEY: 127,
                BW_KEY: 0,
                ROI_WIDTH: 100,
                ROI_HEIGHT: 100,
            }
        if (
            os.path.isfile(self.settings_path)
            and not self._use_default_session_settings
        ):
            with open(self.settings_path, "r") as f:
                loaded_settings = json.load(f)
                for key in default_settings.keys():
                    if key not in loaded_settings.keys():
                        loaded_settings[key] = default_settings[key]
                return loaded_settings
        else:
            return default_settings

    def _save_session_settings(self):
        with open(self.settings_path, "w") as f:
            json.dump(self.SESSION_SETTINGS, f)

    def _draw_roi(self, img: np.ndarray) -> np.ndarray:
        roi_width = self.SESSION_SETTINGS.get(ROI_WIDTH)
        roi_height = self.SESSION_SETTINGS.get(ROI_HEIGHT)
        img_height, img_width = img.shape[:2]
        center = (img_width // 2, img_height // 2)
        x = (img_width - roi_width) // 2
        y = (img_height - roi_height) // 2
        cv2.rectangle(
            img, (x, y), (x + roi_width, y + roi_height), (0, 255, 0), thickness=4
        )
        # draw crosshair
        drawAxis(img, center, (0, 0, 255), 0)
        drawAxis(img, center, (0, 0, 255), HALFPI)
        # drawAxis(img, (img_height // 2, img_width // 2), (0, 0, 255), 0.5)
        return img

    def _cycle(self):
        frame = self._camera.read()
        frame = self._apply_filters(frame)
        frame = self._draw_roi(frame)
        cv2.imshow(self._window_name, frame)

    def _stop(self):
        self._camera.__del__()
        self._save_session_settings()
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
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, BRIGHTNESS_KEY, 255)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, CONTRAST_KEY, 255)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, BW_KEY, 1)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, ROI_WIDTH, 700)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, ROI_HEIGHT, 700)

    def _apply_filters(self, img: np.ndarray) -> np.ndarray:
        img = apply_brightness_contrast(
            img,
            self.SESSION_SETTINGS.get(BRIGHTNESS_KEY),
            self.SESSION_SETTINGS.get(CONTRAST_KEY),
        )
        if self.SESSION_SETTINGS.get(BW_KEY):
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img

    def _setup_camera(self) -> Droidcam:
        if self._still_image:
            return Droidcam(use_webcam=False, img_src=self._still_image)
        else:
            return Droidcam(use_webcam=True, webcam_index=self._webcam_index)
