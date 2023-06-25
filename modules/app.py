import json
import os
import typing

from fps_limiter import LimitFPS

from machine.grbl import GRBL
from modules import (
    BRIGHTNESS_KEY,
    CONTRAST_KEY,
    BW_KEY,
    ROI_WIDTH_KEY,
    ROI_HEIGHT_KEY,
    HALFPI,
    THRESHOLD_KEY,
    HOLE_SIZE_MIN_KEY,
    HOLE_SIZE_MAX_KEY,
)
from modules.camera import Droidcam
from modules.utils import (
    apply_brightness_contrast,
    mk_trakbar,
    drawAxis,
    combine_two_color_images_with_anchor,
    get_contour_extremes,
)
import numpy as np
import cv2


class SearchWindow:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.tx = 0
        self.ty = 0
        self.bx = 0
        self.by = 0
        self.update_bounds(x, y, width, height)

    def update_bounds(self, x: int, y: int, width: int, height: int):
        self.tx = x + width // 2
        self.ty = y + height // 2
        self.bx = x - width // 2
        self.by = y - height // 2

    def get_roi(self, img: np.ndarray) -> np.ndarray:
        return img[self.by : self.ty, self.bx : self.tx]

    def offset_point(self, point: tuple) -> tuple:
        return point[0] + self.bx, point[1] + self.by


class ScannerApp:
    def __init__(
        self,
        machine_port: str,
        window_name: str = "board_scanner",
        fps_limit: int = 30,
        webcam_index: int = 0,
        still_image: typing.Union[str, os.PathLike] = None,
        use_default_session_settings: bool = False,
    ):
        self.is_running = False
        self._machine_port = machine_port
        self.machine = self._setup_machine()
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
        self._search_window = None
        self._setup_trackbars()

    def _load_session_settings(self) -> dict:
        default_settings = {
            BRIGHTNESS_KEY: 127,
            CONTRAST_KEY: 127,
            BW_KEY: 0,
            ROI_WIDTH_KEY: 100,
            ROI_HEIGHT_KEY: 100,
            THRESHOLD_KEY: 127,
            HOLE_SIZE_MIN_KEY: 100,
            HOLE_SIZE_MAX_KEY: 700,
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
        if self._search_window:
            cv2.rectangle(
                img,
                (self._search_window.bx, self._search_window.by),
                (self._search_window.tx, self._search_window.ty),
                (0, 255, 0),
                thickness=4,
            )
        return img

    def _detect_holes(
        self, img: np.ndarray, thresh: np.ndarray
    ) -> (np.ndarray, typing.List):
        centers = []
        filtered_contours = []
        thresh = cv2.bitwise_not(thresh)
        img_height, img_width = img.shape[:2]
        roi_width = self.SESSION_SETTINGS.get(ROI_WIDTH_KEY)
        roi_height = self.SESSION_SETTINGS.get(ROI_HEIGHT_KEY)
        if not self._search_window:
            self._search_window = SearchWindow(
                img_width // 2, img_height // 2, roi_width, roi_height
            )
        else:
            self._search_window.update_bounds(
                img_width // 2, img_height // 2, roi_width, roi_height
            )

        roi_part = self._search_window.get_roi(thresh)
        contours, _ = cv2.findContours(
            roi_part, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if (
                self.SESSION_SETTINGS.get(HOLE_SIZE_MIN_KEY)
                < area
                < self.SESSION_SETTINGS.get(HOLE_SIZE_MAX_KEY)
            ):
                filtered_contours.append(cnt)

        roi_part = cv2.cvtColor(roi_part, cv2.COLOR_GRAY2BGR)
        if filtered_contours:
            for cnt in filtered_contours:
                cv2.drawContours(roi_part, [cnt], 0, (255, 0, 0), 1)
                center = get_contour_extremes(cnt)
                centers.append(self._search_window.offset_point(center))
        combine_two_color_images_with_anchor(
            img, roi_part, self._search_window.bx, self._search_window.by
        )
        return img, centers

    def _setup_window(self):
        cv2.namedWindow(self._window_name)

    def _setup_trackbars(self):
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, BRIGHTNESS_KEY, 255)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, CONTRAST_KEY, 255)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, THRESHOLD_KEY, 255)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, BW_KEY, 1)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, ROI_WIDTH_KEY, 700)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, ROI_HEIGHT_KEY, 700)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, HOLE_SIZE_MIN_KEY, 100000)
        mk_trakbar(self._window_name, self.SESSION_SETTINGS, HOLE_SIZE_MAX_KEY, 3069797)

    def _apply_filters(self, img: np.ndarray) -> (np.ndarray, np.ndarray):
        img = apply_brightness_contrast(
            img,
            self.SESSION_SETTINGS.get(BRIGHTNESS_KEY),
            self.SESSION_SETTINGS.get(CONTRAST_KEY),
        )
        thresh = None
        if self.SESSION_SETTINGS.get(BW_KEY):
            grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(
                grey,
                self.SESSION_SETTINGS.get(THRESHOLD_KEY),
                255,
                cv2.THRESH_BINARY,
            )
        return img, thresh

    def _draw_center(
        self, img: np.ndarray, center: typing.Tuple[int, int]
    ) -> np.ndarray:
        drawAxis(img, center, (0, 0, 255), 0)
        drawAxis(img, center, (0, 0, 255), HALFPI)
        cv2.circle(img, center, 5, (0, 0, 255), cv2.FILLED)
        cv2.putText(
            img, str(center), center, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
        )
        return img

    def _draw_centers(self, img: np.ndarray, centers: typing.List) -> np.ndarray:
        for center in centers:
            self._draw_center(img, center)
        return img

    def _setup_camera(self) -> Droidcam:
        if self._still_image:
            return Droidcam(use_webcam=False, img_src=self._still_image)
        else:
            return Droidcam(use_webcam=True, webcam_index=self._webcam_index)

    def _setup_machine(self) -> GRBL:
        machine = GRBL(port=self._machine_port)
        machine.reset()
        machine.send_wake_up()
        machine.home()
        return machine

    def _cycle(self):
        frame = self._camera.read()
        frame, thresh = self._apply_filters(frame)
        if thresh is not None:
            frame, centers = self._detect_holes(frame, thresh)
            frame = self._draw_centers(frame, centers)
        frame = self._draw_roi(frame)
        cv2.imshow(self._window_name, frame)

    def _stop(self):
        self._camera.__del__()
        self._save_session_settings()
        self.is_running = False
        cv2.destroyAllWindows()

    def _keyboard_handler(self, key):
        JOG_VALUE = 1
        if key == ord("q"):
            self._stop()
        elif key == ord("w"):
            self.machine.jog(d_x=0, d_y=JOG_VALUE)
        elif key == ord("s"):
            self.machine.jog(d_x=0, d_y=-JOG_VALUE)
        elif key == ord("a"):
            self.machine.jog(d_x=-JOG_VALUE, d_y=0)
        elif key == ord("d"):
            self.machine.jog(d_x=JOG_VALUE, d_y=0)

    def run(self):
        self.is_running = True
        while self.is_running:
            if self._fps_limiter():
                key = cv2.waitKey(1)
                self._keyboard_handler(key)
                self._cycle()
