# Project ASGARD
# 🌍 Simulation

Le script simulation.sh permet de lancer l'environnement complet de simulation :

```sh
./simulation.sh  
```

### Détails des commandes

#### 1\. Monde Gazebo

Lance la simulation Gazebo avec le fichier monde spécifique contenant les deux drones et le marqueur ArUco. Modifiez le monde `iris_zephyr_aruco.sdf` pour ajouter d'autres objets.

```sh
gz sim -v4 -r ~/gz_ws/src/ardupilot_gazebo/worlds/iris_zephyr_aruco.sdf  
```

#### 2\. ArduPilot SITL (Software In The Loop)

La commande suivante est utilisée pour lancer la simulation du contrôleur de vol pour chaque drone.

**Structure générique de la commande :**

```sh
~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I<INSTANCE> --sysid=<SYSTEM_ID> --use-dir=<OUTPUT_DIR> [OPTIONS]  
```

**Explication des paramètres :**

| **Paramètre** | **Description** | **Valeur Drone Maître** | **Valeur Drone Auxiliaire** |
| --- | --- | --- | --- |
| \-v | **Type de véhicule :** Spécifie le firmware (ex: Copter). | ArduCopter | ArduCopter |
| \-f | **Frame :** Définit la configuration du châssis. | gazebo-iris | gazebo-iris |
| \--model | **Interface Physique :** Protocole avec Gazebo (JSON). | JSON | JSON |
| \--console | **Console MAVProxy :** Ouvre une GUI de contrôle. | Inclus | Inclus |
| \-I | **Instance :** Index SITL (définit les ports TCP/UDP). | 0   | 1   |
| \--sysid | **ID Système MAVLink :** Identifiant réseau unique. | 1   | 2   |
| \--use-dir | **Dossier de sortie :** Stockage logs/params séparé. | .../iris_with_gimbal | .../drone1 |

**Paramètres Optionnels Utiles :**

- `--map` : Affiche une carte 2D avec la position du drone (nécessite internet).
- `--console`: Affiche un terminal pour le drone

**Commande pour le Drone Maître (Gros drone) :**
```sh
~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I0 --sysid=1 --use-dir=$HOME/gz_ws/ardupilot_output/iris_with_gimbal  
```

**Commande pour le Drone Auxiliaire (Petit drone) :**
```sh
~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I1 --sysid=2 --use-dir=$HOME/gz_ws/ardupilot_output/drone1  
```

# Configuration wifi des deux RPI

**WiFi SSID:** `Asgard`

**WiFi pwd:** `wifisupelec`

## Valhalla

```sh
ssh asgard@valhalla.local
```

**Hostname**: `valhalla`

**Username**: `asgard`

**Password**: `opensesame`


## Valkyrie

Raspberry Pi OS Lite (64-bit)

```sh
ssh helics@valkyrie.local
```

**Hostname**: `valkyrie`

**Username**: `helics`

**Password**: `opensesame`

## Commandes systemd
```sh
# Met à jour systemd avec le nouveau fichier
sudo systemctl daemon-reload

# Active le lancement automatique au démarrage de la carte
sudo systemctl enable valkyrie.service

# Démarre le script maintenant (sans avoir à redémarrer le drone)
sudo systemctl start valkyrie.service

# Le script arrete temporairement mais redemarera apres un boot A FAIT AVANT UN GIT PULL
sudo systemctl stop valkyrie.service

# Si on veut que le script ne redemarre plus au reboot
sudo systemctl disable valyrie.service

# Le paramètre -f permet de suivre les logs en direct
journalctl -u valkyrie.service -f
```

# Mavproxy

```sh
mavproxy.py --master=/dev/ttyAMA0 --baudrate 921600
```

