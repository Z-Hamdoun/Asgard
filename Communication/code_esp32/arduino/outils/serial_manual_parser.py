import serial

port = "/dev/ttyUSB1"
BAUDRATE = 115200

app_serial = serial.Serial(port, baudrate=BAUDRATE, timeout=0)

def show():
    while True:
        data = app_serial.read(1024)
        for i, byte in enumerate(data):
            if byte == 253 and len(data) > 10+i:
                print([dd for dd in data[i:i+10]])


show()