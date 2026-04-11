from class_Camera import Camera
import time
camera = Camera(simulation=None)

while True:
    result = camera.analyse()
    print(result)
    time.sleep(1)
