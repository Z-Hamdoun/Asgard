# Project Valkyrie

## Simulation

* Lancement du monde Gazebo
```sh
gz sim -v4 -r ~/gz_ws/src/ardupilot_gazebo/worlds/iris_zephyr_aruco.sdf
```

* Lancement Ardupilot SITL du gros drone
```sh
~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I0 --sysid=1 --use-dir=$HOME/gz_ws/ardupilot_output/iris_with_gimbal
```

* Petit drone
```sh
~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I1 --sysid=2 --use-dir=$HOME/gz_ws/ardupilot_output/drone1
```

## RPI 1 (carte 32Gb)

**Nom d'utilisateur RPI**: `Asgard`

**MDP**: `Dassault2025`

*Connecté sur le wifi "Asgard" avec le meme mot de passe*

## RPI 2 (carte 64Gb)

Raspberry Pi OS Lite (64-bit)
**hostname**: `uav-companion`
**username**: `helics`
**password**: `opensesame`
**WiFi SSID**: `hotspot-helics`
**WiFi pwd**: `wifisupelec`
**SSH**: activated + using password authentification