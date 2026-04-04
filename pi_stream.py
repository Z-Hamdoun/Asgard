from picamera2 import Picamera2
import subprocess
import numpy as np

UDP_IP = "138.195.198.235"
UDP_PORT = 5000

ffmpeg = subprocess.Popen([
    "ffmpeg",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", "640x480",
    "-r", "30",
    "-i", "-",
    "-f", "mpegts",
    "-codec:v", "mpeg1video",   # IMPORTANT (more stable)
    f"udp://{UDP_IP}:{UDP_PORT}"
], stdin=subprocess.PIPE)

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"size": (640, 480)}
))
picam2.start()

while True:
    frame = picam2.capture_array()

    # FIXES
    frame = frame[:, :, :3]
    frame = np.ascontiguousarray(frame)

    ffmpeg.stdin.write(frame.tobytes())