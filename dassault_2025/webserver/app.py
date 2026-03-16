import threading
import time
import os
import sys
from decimal import Decimal

import eventlet
eventlet.monkey_patch(all=True)  # Patch explicite de tous les modules (socket, thread, time, etc.)

# Ajout d'un diagnostic de base pour vérifier qu'Eventlet est bien patché
orig_socket = eventlet.patcher.original('socket')
patched_socket = eventlet.patcher.original('socket')
print(f"Socket patché? {'Oui' if orig_socket != patched_socket else 'Non'}")

from flask import Flask, Response, render_template, jsonify, request, send_from_directory
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///missions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'olympe_secret_key'  # Nécessaire pour Flask-SocketIO

from logger_utils import logger
from models import *
import action as ACTION
from socket_utils import socketio, init_socketio
import api as api


# Initialisation de la base de données
db.init_app(app)

# Initialisation de SocketIO
init_socketio(app)

# Fonction pour surveiller les modifications de fichiers et redémarrer le serveur automatiquement
def watch_for_changes(interval=1):
    mtimes = {}
    
    def get_mtimes(path):
        times = {}
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(('.py', '.html', '.js', '.css')):
                    full_path = os.path.join(root, file)
                    try:
                        times[full_path] = os.path.getmtime(full_path)
                    except OSError:
                        pass
        return times
    
    # Initialiser les temps de modification
    mtimes = get_mtimes('.')
    
    while True:
        time.sleep(interval)
        for path, mtime in get_mtimes('.').items():
            if path not in mtimes or mtime > mtimes[path]:
                print(f"Changement détecté dans {path}, redémarrage du serveur...")
                mtimes = get_mtimes('.')
                # Forcer eventlet à redémarrer le hub
                try:
                    eventlet.hubs.get_hub().abort()
                    # Redémarrer le processus
                    os.execv(sys.executable, ["\"" + sys.executable + "\""] + sys.argv)
                except Exception as e:
                    print(f"Erreur lors du redémarrage : {e}")
                break

def dict_from_module(module):
    context = {}
    for setting in dir(module):
        # you can write your filter here
        context[setting] = getattr(module, setting)

    return context

## ROUTES PRINCIPALES
@app.route("/")
def index():
    return render_template('index.html')

@app.route("/localisation")
def localisation():
    return render_template('localisation.html', **dict_from_module(ACTION))

@app.route("/control")
def control():
    return render_template('control.html', **dict_from_module(ACTION))

@app.route('/favicon.ico')
def favicon():
    return Response(status=204)  # Pas de contenu 

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

@app.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def map_tile(z, x, y):
    """Fonction pour gérer les tuiles de carte.
    Si la tuile existe en cache, elle est servie directement.
    Sinon, elle est téléchargée depuis Google Maps, mise en cache, puis servie."""
    import requests
    from urllib.parse import quote_plus
    from pathlib import Path
    
    logger.info(f"Demande de tuile: z={z}, x={x}, y={y}")
    
    # Définir le chemin de la tuile en cache
    cache_path = os.path.join(app.root_path, 'static', 'tiles', str(z), str(x), f"{y}.png")
    cache_dir = os.path.dirname(cache_path)
    
    logger.debug(f"Chemin du cache: {cache_path}")
    
    # Vérifier si la tuile existe en cache
    if os.path.exists(cache_path):
        # Si la tuile existe, la servir directement
        logger.info(f"Tuile trouvée dans le cache: {cache_path}")
        return send_from_directory(os.path.dirname(cache_path), f"{y}.png")
    
    # Si la tuile n'existe pas, la télécharger depuis Google Maps
    logger.info(f"Tuile non trouvée dans le cache, téléchargement depuis Google Maps")
    
    try:
        # S'assurer que le dossier de cache existe
        os.makedirs(cache_dir, exist_ok=True)
        logger.debug(f"Dossier de cache créé: {cache_dir}")
        
        # URL de la tuile Google Maps
        tile_url = f"https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
        logger.debug(f"URL de la tuile: {tile_url}")
        
        # Télécharger la tuile
        response = requests.get(tile_url, stream=True)
        logger.debug(f"Code de statut de la réponse: {response.status_code}")
        
        if response.status_code == 200:
            # Sauvegarder la tuile en cache
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Tuile téléchargée et sauvegardée: {cache_path}")
            
            # Vérifier que le fichier a bien été créé
            if os.path.exists(cache_path):
                logger.debug(f"Fichier créé avec succès: {cache_path}, taille: {os.path.getsize(cache_path)} octets")
            else:
                logger.error(f"Échec de création du fichier: {cache_path}")
            
            # Servir la tuile
            return send_from_directory(os.path.dirname(cache_path), f"{y}.png")
        else:
            # En cas d'erreur, renvoyer une image transparente ou une erreur 404
            logger.error(f"Erreur lors du téléchargement de la tuile: {response.status_code}")
            error_tile_path = os.path.join(app.root_path, 'static', 'images', 'error-tile.png')
            if os.path.exists(error_tile_path):
                logger.info(f"Utilisation de l'image d'erreur: {error_tile_path}")
                return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'error-tile.png')
            return Response(status=404)
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de la tuile [{z}/{x}/{y}]: {e}")
        # Essayer d'utiliser l'image d'erreur si disponible
        error_tile_path = os.path.join(app.root_path, 'static', 'images', 'error-tile.png')
        if os.path.exists(error_tile_path):
            logger.info(f"Utilisation de l'image d'erreur: {error_tile_path}")
            return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'error-tile.png')
        return Response(status=500)

# Use blueprint for the api
app.register_blueprint(api.bp)

@socketio.on('user_position')
def handle_user_position(data):
    """Handle user GPS position"""
    
    print("data", data)
    msg = data["msg"]
    #print("msg:", msg)

    pos = db.session.query(UsrPosFollowMe).first()
    if not pos:
        pos = UsrPosFollowMe(latitude=0, longitude=0, altitude=0, timestamp=0)
        db.session.add(pos)
        db.session.commit()
    
    if msg in ("enable follow me", "disable follow me"):
        # Reset position when enabling follow me
        pos.latitude = 0
        pos.longitude = 0
        pos.altitude = 0
        pos.msg = "NOK"
        pos.timestamp = 0

    elif msg == "ok":
        pos.latitude = data.get("latitude")
        pos.longitude = data.get("longitude")
        pos.altitude = data.get("altitude")
        pos.msg = "OK"
        pos.timestamp = time.time()

    else:
        print("erreur position utilisateur: ", msg)
    db.session.commit()
    return {'status': 'received'}

# Point d'entrée principal
if __name__ == "__main__":
    with app.app_context():
        # Check if we need to recreate the database tables to include new fields
        check_and_sync_database(logger)
        
        # Start the file watcher for automatic restart
        watcher_thread = threading.Thread(target=watch_for_changes)
        watcher_thread.daemon = True
        watcher_thread.start()
        
        try:
            # Diagnostic réseau - vérifier si l'adresse est déjà utilisée
            import socket
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            test_result = test_socket.connect_ex(('127.0.0.1', 5000))
            if test_result == 0:
                logger.warning("ATTENTION: Le port 5000 semble déjà être utilisé!")
                print("\n" + "*" * 50)
                print("ATTENTION: Le port 5000 est déjà utilisé par une autre application.")
                print("Veuillez fermer les autres instances de l'application ou utiliser un autre port.")
                print("*" * 50 + "\n")
            test_socket.close()
            
            # Lancement du serveur avec support WebSocket via eventlet
            print("\n" + "*" * 50)
            print("Serveur en cours de démarrage sur http://127.0.0.1:5000")
            print("Vous pourrez aussi utiliser http://localhost:5000")
            print("*" * 50 + "\n")
            
            # Permettre les connexions depuis n'importe quelle interface réseau
            socketio.run(app, 
                        host='0.0.0.0',  # Écouter sur toutes les interfaces réseau
                        port=5000, 
                        debug=True, 
                        allow_unsafe_werkzeug=True,
                        use_reloader=False)  # Désactiver le reloader pour éviter les conflits
            
        except OSError as e:
            if "Errno 10013" in str(e) or "Permission denied" in str(e):
                logger.error(f"Erreur d'accès au port 5000. Essayez d'exécuter en tant qu'administrateur ou utilisez un autre port.")
                print("\n" + "*" * 50)
                print("ERREUR: Impossible d'accéder au port 5000.")
                print("1. Essayez d'exécuter le programme en tant qu'administrateur")
                print("2. Vérifiez qu'aucune autre application n'utilise déjà ce port")
                print("3. Essayez de modifier le port utilisé (ex: 8080)")
                print("*" * 50 + "\n")
            else:
                logger.error(f"Erreur lors du démarrage du serveur: {e}")
                print(f"\nERREUR au démarrage du serveur: {e}\n")
        except KeyboardInterrupt:
            logger.info("Serveur arrêté par l'utilisateur")
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du serveur: {e}")
            print(f"\nERREUR au démarrage du serveur: {e}\n")
        finally:
            pass