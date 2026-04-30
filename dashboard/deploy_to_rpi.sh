#!/bin/bash
# Script pour déployer test_rpi.py sur une Raspberry Pi

if [ $# -eq 0 ]; then
    echo "Usage: $0 <rpi_ip_address>"
    echo "Exemple: $0 192.168.1.100"
    exit 1
fi

RPI_IP=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Déploiement de test_rpi.py vers $RPI_IP..."

# Créer le dossier sur la RPi
ssh helics@$RPI_IP "mkdir -p ~/pnp_test"

# Copier les fichiers
scp $SCRIPT_DIR/test_rpi.py helics@$RPI_IP:~/pnp_test/
scp $SCRIPT_DIR/algo.py helics@$RPI_IP:~/pnp_test/
scp $SCRIPT_DIR/README_RPI.md helics@$RPI_IP:~/pnp_test/

echo "✅ Fichiers copiés !"
echo ""
echo "Pour lancer sur la RPi :"
echo "  ssh helics@$RPI_IP"
echo "  cd ~/pnp_test"
echo "  python3 test_rpi.py"
echo ""
echo "Assurez-vous que picamera2 est installé :"
echo "  sudo apt install python3-picamera2 python3-opencv"