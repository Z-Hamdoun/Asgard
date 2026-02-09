"""
Ce script récupère les données de position de Gazebo et les envoie sous forme de
message mavlink vision_position_estimate_send à un port série.

L'objectif est de simuler un module ESP32-UWB qui envoie ces messages à la carte 
ESP32 de télécommunication. Cette carte peut être simulée par test1.cpp, qui se 
connecte à ardupilot d'un coté et mission planner de l'autre.

"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pymavlink import mavutil
from lib.Hardware.class_Local_Position_Sensor import Local_Position_Sensor
import time

from parametrage import LAT_ORIGINE, LON_ORIGINE, ALT_ORIGINE
import cv2
import numpy as np
import threading

port = "/tmp/ttyV4"
baudrate = 57600
master = mavutil.mavlink_connection(
        port, baud=baudrate
    )

master.first_byte = False # Comme si on avait déjà reçu un message
master.WIRE_PROTOCOL_VERSION = "2.0" # On active MAVLink 2
os.environ['MAVLINK20'] = '1' # On active MAVLink 2
mavutil.set_dialect(dialect='ardupilotmega') # On charge le dialecte
# Reste de la fonction master.auto_mavlink_version
master.mav = mavutil.mavlink.MAVLink(master, srcSystem=master.source_system, srcComponent=master.source_component)
master.mav.robust_parsing = master.robust_parsing
master.WIRE_PROTOCOL_VERSION = mavutil.mavlink.WIRE_PROTOCOL_VERSION

def time_usec() -> int:
    """timestamp Unix en us"""
    return int(time.time() * 1e6)

next_send_home_ekf = time.time()

# instance used later in the main loop
sensor = {"x":0, "y":0, "z":0}

# Source - https://stackoverflow.com/a
# Posted by M lab, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-17, License - CC BY-SA 4.0

def my_estimatePoseSingleMarkers(corners, marker_size, mtx, distortion):
    '''
    This will estimate the rvec and tvec for each of the marker corners detected by:
       corners, ids, rejectedImgPoints = detector.detectMarkers(image)
    corners - is an array of detected corners for each detected marker in the image
    marker_size - is the size of the detected markers
    mtx - is the camera matrix
    distortion - is the camera distortion matrix
    RETURN list of rvecs, tvecs, and trash (so that it corresponds to the old estimatePoseSingleMarkers())
    '''
    marker_points = np.array([[-marker_size / 2, marker_size / 2, 0],
                              [marker_size / 2, marker_size / 2, 0],
                              [marker_size / 2, -marker_size / 2, 0],
                              [-marker_size / 2, -marker_size / 2, 0]], dtype=np.float32)
    trash = []
    rvecs = []
    tvecs = []
    for c in corners:
        nada, R, t = cv2.solvePnP(marker_points, c, mtx, distortion, False, cv2.SOLVEPNP_IPPE_SQUARE)
        rvecs.append(R)
        tvecs.append(t)
        trash.append(nada)
    return rvecs, tvecs, trash



def _init_camera_calibration_from_frame(frame):
    h, w = frame.shape[:2]
    f = 0.87 * w
    camera_matrix = np.array([[f, 0, w / 2],
                              [0, f, h / 2],
                              [0, 0, 1]], dtype=np.float64)
    dist_coeffs = np.zeros((5, 1), dtype=np.float64)
    return camera_matrix, dist_coeffs

def aruco_tracking_thread(camera_id=0, marker_length=0.1, camera_matrix=None, dist_coeffs=None, draw=False):
    """
    Thread that captures frames from the PC camera, detects ArUco markers,
    estimates pose and updates `sensor["x"], sensor["y"], sensor["z"]` (meters).
    - camera_id: integer id for cv2.VideoCapture
    - marker_length: physical size of the marker in meters
    - camera_matrix/dist_coeffs: optional calibration; if None they are approximated
    - draw: if True, show annotated window (press 'q' to quit window)
    """
    global sensor
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        return

    #aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    #params = cv2.aruco.DetectorParameters()  # Création des paramètres du détecteur

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detectorParams = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, detectorParams)

    # lazy calibration init if not provided
    calib_initialized = (camera_matrix is not None and dist_coeffs is not None)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if not calib_initialized:
            camera_matrix, dist_coeffs = _init_camera_calibration_from_frame(frame)
            calib_initialized = True

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)

        if ids is not None and [24] in ids and len(corners) > 0:
            #print(ids)
            # estimatePoseSingleMarkers returns rvecs, tvecs for each detected marker
            rvecs, tvecs, _ = my_estimatePoseSingleMarkers(corners, marker_length, camera_matrix, dist_coeffs)
            # use first detected marker
            tvec = tvecs[0]  # (x, y, z) in meters: x right, y down, z forward
            rvec = rvecs[0]

            # update sensor coordinates (keep OpenCV convention)
            #print(tvec[0][0], tvec[1][0], tvec[2][0])
            sensor["y"] = -float(tvec[0][0])
            sensor["z"] = -float(tvec[1][0])
            sensor["x"] = -float(tvec[2][0])

            if draw:
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, marker_length * 0.5)
        #else:
        #    sensor["x"] = float('NaN')
        #    sensor["y"] = float('NaN')
        #    sensor["z"] = float('NaN')

        if draw:
            cv2.imshow('Aruco Tracking', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    if draw:
        cv2.destroyAllWindows()

# start tracking in background so the main loop can continue sending MAVLink messages
_thread = threading.Thread(
    target=aruco_tracking_thread,
    kwargs={'camera_id': 0, 'marker_length': 0.045, 'camera_matrix': None, 'dist_coeffs': None, 'draw': True},
    daemon=True
)
_thread.start()


while 1:
    time.sleep(0.1)
    print(sensor["x"], sensor["y"], sensor["z"])
    master.mav.vision_position_estimate_send(
            time_usec(),
            sensor["x"], sensor["y"], sensor["z"],
            0, 0, 0,
            [float('NaN')]*21, 0
        )
    """if time.time() >= next_send_home_ekf:
        master.mav.set_gps_global_origin_send(
            11,
            int(LAT_ORIGINE*1e7), int(LON_ORIGINE*1e7), int(ALT_ORIGINE*1e3), 0
        )"""
