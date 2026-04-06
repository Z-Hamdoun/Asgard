from picamera2 import Picamera2
import subprocess
import numpy as np
import argparse
from class_Camera import Camera

parser = argparse.ArgumentParser()
parser.add_argument("--ip", required=True, help="PC IP address")
parser.add_argument("--port", type=int, default=5000, help="UDP port")

args = parser.parse_args()

UDP_IP = args.ip
UDP_PORT = args.port

ffmpeg = subprocess.Popen([
    "ffmpeg",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", "640x480",
    "-r", "30",
    "-i", "-",
    "-f", "mpegts",
    "-codec:v", "mpeg1video",
    f"udp://{UDP_IP}:{UDP_PORT}"
], stdin=subprocess.PIPE)

# picam2 = Picamera2()
# picam2.configure(picam2.create_video_configuration(
#     main={"size": (640, 480)}
# ))
# picam2.start()
camera = Camera(simulation=None)

while True:
    frame = camera.analyse()[-1]

    frame = frame[:, :, :3]
    frame = np.ascontiguousarray(frame)

    ffmpeg.stdin.write(frame.tobytes())