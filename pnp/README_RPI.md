# Test PnP pour Raspberry Pi avec Pi Camera

Ce script est l'équivalent de `test.py` mais adapté pour fonctionner avec une Pi Camera sur Raspberry Pi.

## Installation

Sur votre Raspberry Pi, installez les dépendances :

```bash
sudo apt update
sudo apt install python3-picamera2 python3-opencv python3-numpy
```

### Vérifier que la Pi Camera fonctionne :
```bash
# Test rapide de la caméra :
python3 -c "from picamera2 import Picamera2; print('Pi Camera OK')"
```

## Déploiement (3 méthodes simples)

### Méthode 1 : Script automatique (Le plus simple)
```bash
# Sur votre PC, ouvrez un terminal dans le dossier pnp/
cd /home/eloi/dassault-helics-2026/pnp

# Lancez le script de déploiement :
./deploy_to_rpi.sh 192.168.1.100
```
*Remplacez `192.168.1.100` par l'IP de votre RPi*

### Méthode 2 : Copie par réseau (SSH)
```bash
# Sur votre PC :
scp test_rpi.py helics@192.168.1.100:~/
scp algo.py helics@192.168.1.100:~/

# Sur votre RPi :
cd ~
python3 test_rpi.py
```

### Méthode 3 : Carte SD (Si vous avez accès physique)
1. Retirez la carte SD de la RPi
2. Insérez-la dans votre PC
3. Copiez `test_rpi.py` et `algo.py` dans `/home/helics/`
4. Remettez la carte SD dans la RPi
5. Lancez : `python3 test_rpi.py`

## Exemple concret

Imaginons votre RPi a l'IP `192.168.1.50` :

```bash
# Sur PC :
cd /home/eloi/dassault-helics-2026/pnp
./deploy_to_rpi.sh 192.168.1.50

# Ou manuellement :
scp test_rpi.py helics@192.168.1.50:~/pnp_test/
scp algo.py helics@192.168.1.50:~/pnp_test/

# Sur RPi :
cd ~/pnp_test
python3 test_rpi.py
```

## Comment trouver l'IP de votre RPi

### Méthode 1 : Via votre box internet (Le plus simple) ⭐
1. Ouvrez votre navigateur web
2. Tapez l'adresse de votre box : `192.168.1.1` ou `192.168.0.1`
3. Connectez-vous (login/mot de passe souvent `admin/admin`)
4. Cherchez la liste des appareils connectés
5. Trouvez "raspberrypi" ou "pi"

### Méthode 2 : Sur la RPi directement (Si vous avez un écran)
```bash
# Sur la RPi, tapez :
hostname -I
```
→ Affiche l'IP (ex: `192.168.1.100`)

### Méthode 3 : Scan réseau depuis votre PC
```bash
# Sur votre PC :
sudo apt install nmap
nmap -sn 192.168.1.0/24
```
→ Cherchez "raspberrypi" dans les résultats

### Méthode 4 : Via votre routeur (Alternative)
- Box Orange : `192.168.1.1`
- Box SFR : `192.168.0.1` ou `192.168.1.1`
- Box Free : `192.168.0.254` ou `192.168.1.254`
- Box Bouygues : `192.168.1.254`

### Méthode 5 : Application mobile
Installez "Fing" ou "Network Scanner" sur votre téléphone :
- Scan automatique du réseau
- Trouve tous les appareils avec leur IP

### Exemple concret :
Si votre box affiche :
```
Raspberry Pi - 192.168.1.50
```

Alors votre commande sera :
```bash
./deploy_to_rpi.sh 192.168.1.50
```

### Si rien ne marche :
- Vérifiez que la RPi est allumée et connectée au WiFi
- Essayez `ping raspberrypi.local` depuis votre PC
- Redémarrez votre RPi et votre box

## Résumé

**Besoin :** Copier 2 fichiers (`test_rpi.py` + `algo.py`) sur la RPi

**Objectif :** Pouvoir lancer `python3 test_rpi.py` sur la RPi

**3 solutions :** Script auto → SSH → Carte SD

## Utilisation

1. Copiez ce script sur votre Raspberry Pi
2. Lancez-le :

```bash
cd ~/pnp_test
python3 test_rpi.py
```

## Interface du script

Le script ouvre **3 fenêtres** :

### 1. "Calibrage Couleur" - Les sliders
- `H1 Min/Max` : Teinte plage 1 (rouge par défaut)
- `H2 Min/Max` : Teinte plage 2 (rouge foncé)
- `S Min` : Saturation minimum
- `V Min` : Luminosité minimum
- `Circularity` : Circularité des points (0.8 = assez circulaire)

### 2. "Vue Drone (Pi Camera)" - La vidéo
- **Rouge** : Points candidats détectés
- **Vert** : Les 5 points sélectionnés + calcul PnP réussi
- **Texte** : Coordonnées X, Y, Z en cm
- **Réticule** : Ligne pointant vers la cible

### 3. "Masque Nettoye" - Le masque binaire
- Blanc = pixels détectés comme magenta
- Noir = pixels ignorés

## Calibration

1. **Placez vos points magenta** devant la caméra
2. **Ajustez les sliders** jusqu'à ce que :
   - Vos points apparaissent en **blanc** dans le masque
   - Les contours sont **propres** (pas de bruit)
   - Vous voyez "LOCK CONFIRME" en vert

3. **Testez avec différents éclairages** et distances

## Commandes

- `q` : Quitter le programme

## Résultat attendu

Quand la calibration fonctionne, vous verrez :
- ✅ **5 points entourés en vert**
- ✅ **"LOCK CONFIRME"** en haut à gauche
- ✅ **Coordonnées X, Y, Z** calculées en cm
- ✅ **Réticule** pointant vers la cible

## Dépannage

### "picamera2 not found"
```bash
sudo apt install python3-picamera2
```

### "Camera not detected" / "IndexError: list index out of range"
- Vérifiez que la Pi Camera est bien branchée
- Le câble doit être inséré **dans le bon sens** (contacts vers la carte)
- Activez la caméra : `sudo raspi-config` → Interfacing Options → Camera → Enable
- Redémarrez la RPi : `sudo reboot`
- Test : `vcgencmd get_camera` (doit afficher "detected=1")
- Test : `python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"`

### "No points detected"
- Vérifiez l'éclairage
- Ajustez les sliders de couleur
- Vos points sont-ils vraiment magenta ?

### "Script freeze"
- Appuyez sur `Ctrl+C` pour forcer l'arrêt
- Relancez : `python3 test_rpi.py`

## Différences avec test.py

- Utilise `picamera2` au lieu de `cv2.VideoCapture(0)`
- Configuration optimisée pour la Pi Camera (résolution 1280x720)
- Même interface de calibration avec sliders
- Même logique de détection PnP

## Fichiers nécessaires

- `test_rpi.py` : Script principal
- `algo.py` : Algorithme PnP
- `README_RPI.md` : Ce fichier
- `deploy_to_rpi.sh` : Script de déploiement (optionnel)