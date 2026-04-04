from picamera2 import Picamera2
import subprocess

UDP_IP = "138.195.198.235"
UDP_PORT = 5000

# Start ffmpeg process
ffmpeg = subprocess.Popen([
    "ffmpeg",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", "640x480",
    "-r", "30",
    "-i", "-",
    "-f", "mpegts",
    f"udp://{UDP_IP}:{UDP_PORT}"
], stdin=subprocess.PIPE)

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"size": (640, 480)}
))
picam2.start()

while True:
    frame = picam2.capture_array()
    ffmpeg.stdin.write(frame.tobytes())