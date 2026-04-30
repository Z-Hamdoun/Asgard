"""
Ce script récupère les données série sur le port 1 et les envoie sur les ports 2 et 3.
Il transmet les données de 2 et 3 uniquement à 1.
"""

import serial

port3 = "/tmp/ttyV1"
port2 = "/tmp/ttyV2"
#port2 = "/dev/pts/25"
port1 = "/dev/ttyUSB0"

BAUDRATE = 115200

SerialObj1 = serial.Serial(port1)
SerialObj2 = serial.Serial(port2)
SerialObj3 = serial.Serial(port3)


for serobj in [SerialObj1, SerialObj2, SerialObj3]:
    serobj.baudrate = BAUDRATE  # set Baud rate to 9600
    serobj.bytesize = 8     # Number of data bits = 8
    serobj.parity   ='N'    # No parity
    serobj.stopbits = 1     # Number of Stop bits = 1

#SerialObj1.baudrate = 1000000
#SerialObj3.baudrate = 57600

while 1:
    if SerialObj1.in_waiting:
        data = SerialObj1.read_all()
        SerialObj2.write(data)
        SerialObj3.write(data)

    if SerialObj2.in_waiting:
        SerialObj1.write(SerialObj2.read_all())
    if SerialObj3.in_waiting:
        SerialObj1.write(SerialObj3.read_all())
