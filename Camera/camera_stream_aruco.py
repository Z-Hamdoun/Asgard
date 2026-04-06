from class_Camera import Camera

camera = Camera(simulation=None)

while True:
    result = camera.analyse()
    if result[-2]:
        print("ARUCOOOOOO")
