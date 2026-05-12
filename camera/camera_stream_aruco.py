from class_Camera import Camera
import time
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
camera = Camera(simulation=None)

while True:
    result = camera.analyse()
    print(result)
    time.sleep(0.05)
