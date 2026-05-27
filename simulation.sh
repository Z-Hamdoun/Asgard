# Simulation
gnome-terminal --tab --title="Simulation" -- bash -c "gz sim -v4 -r ~/gz_ws/src/ardupilot_gazebo/worlds/iris_zephyr_aruco.sdf
; sleep 2; exec bash"

# Master drone
gnome-terminal --tab --title="Master Drone" -- bash -c "~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I0 --sysid=1 --use-dir=$HOME/gz_ws/ardupilot_output/iris_with_gimbal -A '--serial1=udpclient:127.0.0.1:14554'
; exec bash"

# Auxiliary drone
gnome-terminal --tab --title="Auxiliary Drone" -- bash -c "~/ardupilot/Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console -I1 --sysid=2 --use-dir=$HOME/gz_ws/ardupilot_output/drone1 -A '--serial1=udpclient:127.0.0.1:14564'
; exec bash"