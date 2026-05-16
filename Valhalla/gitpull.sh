#!/bin/bash

# 1. Test connexion internet
if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "Online"
else
    echo "git pull error: erreur de connexion internet"
    exit 1
fi

# 2. Arrêt du service
sudo systemctl stop launcher.service
echo "stop launcher.service"
sleep 3

# 3. Déplacement dans le dossier
cd DASSAULT-HELICS-2026 || { 
    echo "git pull error: cd a pas marche"
    sudo systemctl start launcher.service
    echo "start launcher.service"
    exit 1
}

# 4. Exécution du git pull et capture de son résultat
git pull
GIT_STATUS=$? 

# 5. Redémarrage systématique du service
sudo systemctl start launcher.service
echo "launcher.service started"

# 6. Analyse du résultat de Git pour la réponse finale du script
if [ $GIT_STATUS -eq 0 ]; then
    echo "Git pull check"
else
    echo "git pull error: Conflit ou problème lors du git pull."
    exit 1 
fi