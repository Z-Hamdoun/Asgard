import asyncio
import websockets
import json
import sys
import subprocess # Pour exécuter git pull

async def responder(ip_ordi):
    uri = f"ws://{ip_ordi}:8000/ws"
    
    while True: # Boucle de reconnexion infinie
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connecté à {ip_ordi}")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Logique du Ping-Pong
                    if data.get("type") == "ping":
                        data["type"] = "pong"
                        data["source"] = "Valkyrie"
                        await websocket.send(json.dumps(data))
                    
                    elif data.get("command") == "git_pull" and data.get("target") == "Valkyrie":
                        try:
                            # Exécute la commande et récupère le résultat
                            result = subprocess.check_output(["pull"]).decode("utf-8")
                            print(result)
                        except Exception as e:
                            print(f"Erreur git : {e}")

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e}) ctrl + C pour exit")
            await asyncio.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python Valkyrie.py <IP_DU_PC>")
        sys.exit(1)
    asyncio.run(responder(sys.argv[1]))