class GazeboCaracteristics:
    def __init__(self, 
        camera_info_topic: str = "/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/camera_info",
        image_topic: str = "/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"):
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

        self.mat_received = False
        self.image_received = False

        subscribed = node.subscribe(CameraInfo, camera_info_topic, self.camera_info_callback)
        if not subscribed:
            raise RuntimeError("Impossible d'accéder au topic camera_info")

        subscribed = node.subscribe(Image, image_topic, self.image_callback)
        if not subscribed:
            raise RuntimeError("Impossible d'accéder au topic image")

        while not self.mat_received and not self.image_received:
            time.sleep(0.05)
    
    def camera_info_callback(self, msg):
        if not self.mat_received:
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
            self.mat_received = True
    
    def image_callback(self, msg):
        if not self.image_received:
            width = msg.width
            height = msg.height
            print(f"Width: {width}")
            print(f"Height: {height}")
            print("\n")
            self.image_received = True

if __name__ == "__main__":
    GazeboCaracteristics()
