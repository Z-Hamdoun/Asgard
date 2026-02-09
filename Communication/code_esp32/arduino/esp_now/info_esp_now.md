### Practical rule of thumb

- Simple ESP-NOW mesh or point-to-point: put everyone in station mode, unless you need one board to act as a Wi-Fi access point for other clients.

- Gateway board (bridging ESP-NOW to Wi-Fi network): often set it to AP+STA so it can run ESP-NOW and also either connect upstream or host downstream clients.


Je pense donc qu'on va mettre tout le monde en STATION mode car on n'a pas besoin de WIFI


### Projet à tester
dossier esp-test : https://github.com/thomasfla/Linux-ESPNOW/tree/master

il faut essayer de monter le baudrate



### Tests physiques :
1 drone : 
testé sans perte de paquets de 500k à 9Mbps

2 drones : 
25% de perte sur MavProxy avec 500k -> aucune perte en 9M

3 drones : 
le baudrate du master doit être augmenté -> passé de 115200bps à 460800bps 

4 drones : 
à partir de ce moment-là, plus possible de ne pas avoir de pertes : toujours 50% de perte, quel que soit le nombre de drones



Comportement bizarre : mavproxy incrémente de 255 le nombre de paquets perdus assez régulièrement quand 2 drones sont connectés.


Les ttyUSBx se déconnectent à partir de 3. CAD que au bout d'un moment, il va en rester que 2. Ca augmente artificiellement la perte de paquets (+50% quand 4 drones se sont connectés mais que seul 2 restent)
