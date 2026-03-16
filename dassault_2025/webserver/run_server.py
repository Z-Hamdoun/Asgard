"""
Script de démarrage alternatif pour le serveur.
Utilise le module uvicorn comme alternative à evenlet si nécessaire.
"""

import os
import sys
import logging
import argparse
import subprocess

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('server_launcher')

def check_port_availability(port):
    """Vérifie si le port est disponible"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

def run_with_app_py():
    """Exécute le serveur avec app.py directement"""
    print("Démarrage du serveur via app.py...")
    try:
        import app
        # Le serveur devrait démarrer automatiquement
    except KeyboardInterrupt:
        print("\nServeur arrêté par l'utilisateur.")
    except Exception as e:
        print(f"Erreur au démarrage du serveur: {e}")
        return False
    return True

def run_with_flask():
    """Exécute le serveur avec la commande Flask"""
    print("Démarrage du serveur via Flask CLI...")
    try:
        os.environ["FLASK_APP"] = "app.py"
        subprocess.run([sys.executable, "-m", "flask", "run", "--host=0.0.0.0"], check=True)
    except KeyboardInterrupt:
        print("\nServeur arrêté par l'utilisateur.")
    except subprocess.CalledProcessError:
        print("Erreur lors de l'exécution de Flask.")
        return False
    return True

def run_with_uvicorn():
    """Exécute le serveur avec uvicorn (alternative à eventlet)"""
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn n'est pas installé. Installation en cours...")
        subprocess.run([sys.executable, "-m", "pip", "install", "uvicorn"], check=True)
        import uvicorn
    
    print("Démarrage du serveur via Uvicorn...")
    try:
        # Adaptez cette configuration selon vos besoins
        uvicorn.run("app:app", host="0.0.0.0", port=5000, log_level="info")
    except KeyboardInterrupt:
        print("\nServeur arrêté par l'utilisateur.")
    except Exception as e:
        print(f"Erreur au démarrage d'uvicorn: {e}")
        return False
    return True

def run_with_manual_python():
    """Exécute le serveur en utilisant Python directement"""
    print("Démarrage du serveur via Python...")
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
        print("\nServeur arrêté par l'utilisateur.")
    except subprocess.CalledProcessError:
        print("Erreur lors de l'exécution de Python.")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Script de démarrage du serveur avec différentes méthodes")
    parser.add_argument('--method', '-m', choices=['app', 'flask', 'uvicorn', 'python'], 
                       default='app', help='Méthode de démarrage')
    parser.add_argument('--port', '-p', type=int, default=5000, 
                       help='Port sur lequel démarrer le serveur')
    
    args = parser.parse_args()
    
    # Vérifier si le port est disponible
    if not check_port_availability(args.port):
        print(f"ATTENTION: Le port {args.port} est déjà utilisé!")
        response = input("Voulez-vous essayer un autre port? (y/n): ")
        if response.lower() == 'y':
            for port in range(5001, 5100):
                if check_port_availability(port):
                    args.port = port
                    print(f"Utilisation du port {port} à la place")
                    break
            else:
                print("Aucun port libre trouvé entre 5001 et 5100.")
                return
        else:
            print(f"Tentative de démarrage sur le port {args.port} malgré son utilisation...")
    
    os.environ["PORT"] = str(args.port)
    
    # Essayer la méthode spécifiée
    if args.method == 'app':
        success = run_with_app_py()
    elif args.method == 'flask':
        success = run_with_flask()
    elif args.method == 'uvicorn':
        success = run_with_uvicorn()
    elif args.method == 'python':
        success = run_with_manual_python()
    
    # Si la méthode échoue, essayer les autres méthodes
    if not success:
        print("\nLa méthode sélectionnée a échoué. Essai des autres méthodes...")
        methods = ['app', 'flask', 'uvicorn', 'python']
        methods.remove(args.method)
        
        for method in methods:
            print(f"\nEssai avec la méthode '{method}'...")
            if method == 'app':
                if run_with_app_py():
                    break
            elif method == 'flask':
                if run_with_flask():
                    break
            elif method == 'uvicorn':
                if run_with_uvicorn():
                    break
            elif method == 'python':
                if run_with_manual_python():
                    break
        else:
            print("\nToutes les méthodes ont échoué. Vérifiez votre installation.")

if __name__ == "__main__":
    main()
