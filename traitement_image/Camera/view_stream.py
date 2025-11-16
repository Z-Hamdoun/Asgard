import cv2
import time
# Remplace cette IP par celle de ta Raspberry Pi
raspberry_ip = "10.216.225.1"  
url = f"http://{raspberry_ip}:5000/video"

cap = cv2.VideoCapture(url)

while True:
    t1=time.time()
    ret, frame = cap.read()
    if not ret:
        print("Impossible de récupérer le flux")
        break
    cv2.imshow("Flux RPi", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    t2=time.time()
    print(1/(t2-t1))
cap.release()
cv2.destroyAllWindows()
