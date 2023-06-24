import socket

import cv2
import numpy as np
from numpy import interp


def point2int(p):
    return int(p[0]), int(p[1])


def drawAxis(img, center, colour=(0, 0, 255), angle=0.):
    hyp = 1000
    linex = center[0] + np.sin(angle) * hyp
    liney = center[1] - np.cos(angle) * hyp
    cv2.line(img, (int(center[0]), int(center[1])), (int(linex), int(liney)), colour, 3)


def mask_it(frame, lower=(0, 0, 0), upper=(255, 255, 255)):
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_ts = np.array(lower)
    upper_ts = np.array(upper)
    mask = cv2.inRange(img, lower_ts, upper_ts)
    res = cv2.bitwise_or(frame, img, mask=mask)
    # res = cv2.bitwise_xor(frame, img, mask=mask)
    return res


def mask_it_xor(frame, lower=(0, 0, 0), upper=(255, 255, 255)):
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_ts = np.array(lower)
    upper_ts = np.array(upper)
    mask = cv2.inRange(img, lower_ts, upper_ts)
    res = cv2.bitwise_xor(frame, img, mask=mask)
    return res


def rect_get_center(A, B):
    xCenter = (A[0] + B[0]) / 2
    yCenter = (A[1] + B[1]) / 2
    return xCenter, yCenter


def mk_trakbar(window: str, dikt: dict, key: str, maxv: int) -> None:
    def callback(value):
        dikt[key] = value

    cv2.createTrackbar(key, window, dikt.get(key, 0), maxv, callback)


def calibrate_aquire(frame, w=9, h=9):
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 0.001)

    objp = np.zeros((w * h, 3), np.float32)
    objp[:, :2] = np.mgrid[0:w, 0:h].T.reshape(-1, 2)

    detect = False
    objpoints = []
    imgpoints = []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    ret, corners = cv2.findChessboardCorners(gray, (w, h), None)

    if ret == True:
        detect = True
        objpoints = objp

        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        imgpoints = corners

        cv2.drawChessboardCorners(frame, (w, h), corners2, ret)

    return detect, objpoints, imgpoints


def create_calibration(frame, objpoints, imgpoints, w=None, h=None):
    if w == None and h == None:
        h, w = frame.shape[:2]
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, (w, h),
                                                       None, None)

    mean_error = 0

    for i, o in enumerate(objpoints):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
        mean_error += error

    print("total error: ", mean_error / len(objpoints))
    newmtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))

    return mtx, dist, newmtx, roi


def load_calibration(path):
    with np.load(path) as data:
        mtx, dist, newmtx, roi = [data[key] for key in ('mtx', 'dist', 'newmtx', 'roi')]
    return mtx, dist, newmtx, roi


def apply_calibtation(frame, mtx, dist, newmtx, roi, crop=False):
    frame = cv2.undistort(frame, mtx, dist, None, newmtx)

    # x, y, w, h = roi
    # print(x, y, w, h)
    # if x>0 and crop:
    # frame = frame[y:y+h, x:x+w]
    return frame


def offset_point(point, rotation_vector, translation_vector, camera_matrix,
                 dist_coeffs):
    nose_end_point2D, jacobian = cv2.projectPoints(
        np.array([(float(point[0]), float(point[1]), -40.0)]),
        rotation_vector,
        translation_vector,
        camera_matrix,
        dist_coeffs
    )
    return int(nose_end_point2D[0][0][0]), int(nose_end_point2D[0][0][1])


def solve_marker_plane(im, image_points, calibrator, center):
    model_points = np.array([
        (0.0, 0.0, 0.0),  # 'lt'
        (160.0, 0.0, 0.0),  # 'rt'
        (160.0, 100.0, 0.0),  # 'rb'
        (0.0, 100.0, 0.0),  # 'lb'
        # (80.0, 50.0, 0.0  )   # center
    ], dtype=np.float32)

    # print(image_points.shape)
    image_points_a = np.ascontiguousarray(image_points[:, :2]).reshape(
        (image_points.shape[0], 1, 2))
    # model_points_a = np.ascontiguousarray(model_points[:, :2]).reshape((model_points.shape[0], 1, 2))
    rvec = np.zeros((3, 1))
    tvec = np.zeros((3, 1))

    camera_matrix, dist_coeffs = calibrator.get_mtx_dist()
    success, rotation_vector, translation_vector, inliers = cv2.solvePnPRansac(
        model_points,
        image_points_a,
        camera_matrix,
        dist_coeffs,
        useExtrinsicGuess=True,
        # rvec, tvec,
        # flags=cv2.SOLVEPNP_ITERATIVE
        flags=cv2.SOLVEPNP_AP3P,
    )

    roof_points = []

    prev_point = None
    first_point = None
    for i, p in enumerate(image_points):
        p2 = offset_point(model_points[i], rotation_vector, translation_vector,
                          camera_matrix, dist_coeffs)
        roof_points.append(p2)

        if prev_point:
            cv2.line(im, prev_point, (int(p[0]), int(p[1])), (255, 0, 0), 1)
        else:
            first_point = (int(p[0]), int(p[1]))
        prev_point = (int(p[0]), int(p[1]))
    cv2.line(im, prev_point, first_point, (255, 0, 0), 1)

    for i, p2 in enumerate(roof_points):
        cv2.line(im, (int(image_points[i][0]), int(image_points[i][1])), p2,
                 (0, 225, 0), 2)

    cv2.line(im, center,
             offset_point((80, 50), rotation_vector, translation_vector, camera_matrix,
                          dist_coeffs), (0, 225, 0), 2)


def combine_two_color_images_with_anchor(background, foreground, anchor_x=0, anchor_y=0,
                                         alpha=0):
    # Check if the foreground is inbound with the new coordinates and raise an error if out of bounds
    background_height = background.shape[1]
    background_width = background.shape[1]
    foreground_height = foreground.shape[0]
    foreground_width = foreground.shape[1]
    if foreground_height + anchor_y > background_height or foreground_width + anchor_x > background_width:
        raise ValueError(
            "The foreground image exceeds the background boundaries at this location")

    # do composite at specified location
    start_y = anchor_y
    start_x = anchor_x
    end_y = anchor_y + foreground_height
    end_x = anchor_x + foreground_width

    # b_channel, g_channel, r_channel = cv2.split(foreground)

    blended_portion = cv2.add(
        background[start_y:end_y, start_x:end_x],
        foreground,
        # mask=b_channel
    )

    background[start_y:end_y, start_x:end_x] = blended_portion


def get_ip():
    ips = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if
           not ip.startswith("127.")]

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ips.append(s.getsockname()[0])
    s.close()

    return next(ip for ip in ips if ip)


def plot_point(out, point, color):
    cv2.circle(out, point, 3, color, 2)


def get_contour_extremes(c):
    # color = (255, 255, 255)
    # c = c['pts']

    M = cv2.moments(c)
    cX = int(M["m10"] / M["m00"])
    cY = int(M["m01"] / M["m00"])
    return cX, cY
    # plot_point(img, (cX, cY), color)

    # extLeft = tuple(c[c[:, :, 0].argmin()][0])
    # extRight = tuple(c[c[:, :, 0].argmax()][0])
    # extTop = tuple(c[c[:, :, 1].argmin()][0])
    # extBot = tuple(c[c[:, :, 1].argmax()][0])
    # plot_point(img, extLeft, color)
    # plot_point(img, extTop, color)
    # plot_point(img, extBot, color)
    # plot_point(img, extRight, color)


def apply_brightness_contrast(
        input_img: np.ndarray, brightness=127, contrast=127
) -> np.ndarray:
    brightness = interp(brightness, [0, 255], [-126, 126])
    contrast = interp(contrast, [0, 255], [-126, 126])

    if brightness != 0:
        if brightness > 0:
            shadow = brightness
            highlight = 255
        else:
            shadow = 0
            highlight = 255 + brightness
        alpha_b = (highlight - shadow) / 255
        gamma_b = shadow

        buf = cv2.addWeighted(input_img, alpha_b, input_img, 0, gamma_b)
    else:
        buf = input_img.copy()

    if contrast != 0:
        f = float(131 * (contrast + 127)) / (127 * (131 - contrast))
        alpha_c = f
        gamma_c = 127 * (1 - f)

        buf = cv2.addWeighted(buf, alpha_c, buf, 0, gamma_c)
    return buf
