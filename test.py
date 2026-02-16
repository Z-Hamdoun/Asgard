from Camera.class_Camera import Camera


cam = Camera(simulation=None)
cam.get_frame(save=True)
print("Success")
cam.close()
print("Camera closed.")