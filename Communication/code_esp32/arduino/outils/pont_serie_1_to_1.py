"""
Ce script récupère les données série sur le port 1 et les envoie sur les ports 2 et 3.
Il transmet les données de 2 et 3 uniquement à 1.
"""

import serial

port1 = "/tmp/ttyV1"
port2 = "/dev/ttyUSB0"

BAUDRATE = 115200

SerialObj1 = serial.Serial(port1)
SerialObj2 = serial.Serial(port2)


for serobj in [SerialObj1, SerialObj2]:
    serobj.baudrate = BAUDRATE  # set Baud rate to 9600
    serobj.bytesize = 8     # Number of data bits = 8
    serobj.parity   ='N'    # No parity
    serobj.stopbits = 1     # Number of Stop bits = 1

#SerialObj1.baudrate = 1000000
#SerialObj3.baudrate = 57600

while 1:
    if SerialObj1.in_waiting:
        SerialObj2.write(SerialObj1.read_all())

    if SerialObj2.in_waiting:
        SerialObj1.write(SerialObj2.read_all())

