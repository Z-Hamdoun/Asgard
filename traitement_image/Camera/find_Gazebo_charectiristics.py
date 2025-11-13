def find_gazebocamera_caracteristics(
        camera_info_topic: str = "/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/camera_info",
        image_topic: str = "/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"
    ) -> None:
    """Affiche les propriétés de la caméra sur Gazebo.

    Args:
        camera_info_topic (str): Topic CameraInfo.
        image_topic (str): Topic Image.
    """
    from gz.transport13 import Node  # Gazebo Transport bindings
    from gz.msgs10.camera_info_pb2 import CameraInfo
    from gz.msgs10.image_pb2 import Image
    import time
    node = Node()

    mat_received = False
    image_received = False

    def camera_info_callback(msg):
        global mat_received
        if not mat_received:
            intr = msg.intrinsics
            fx = intr.k[0]
            skew = intr.k[1]
            cx = intr.k[2]
            fy = intr.k[4]
            cy = intr.k[5]
            K_matrix = [
                [fx, skew, cx],
                [0,  fy,   cy],
                [0,   0,    1]
            ]
            D_matrix = msg.distortion.k
            print("Matrice K :\n", K_matrix)
            print("Distorsion D :", D_matrix)
            print("\n")
            mat_received = True

    def image_callback(msg):
        global image_received
        if not image_received:
            width = msg.width
            height = msg.height
            print(f"Width: {width}")
            print(f"Height: {height}")
            print("\n")
            image_received = True

    subscribed = node.subscribe(CameraInfo, camera_info_topic, camera_info_callback)
    if not subscribed:
        raise RuntimeError("Impossible d'accéder au topic camera_info")

    subscribed = node.subscribe(Image, image_topic, image_callback)
    if not subscribed:
        raise RuntimeError("Impossible d'accéder au topic image")

    while not mat_received and not image_received:
        time.sleep(0.05)

if __name__ == "__main__":
    find_gazebocamera_caracteristics()
