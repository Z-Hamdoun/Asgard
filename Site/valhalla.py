import asyncio
import websockets
import json
import sys
import subprocess

# --- Fonctions utilitaires inchangées ---
def sendfail(socket, failure, e):
    response = {"type": "status", "command": failure, "source": "Valhalla", "output": e}
    return socket.send(json.dumps(response))

def sendack(socket, ack):
    response = {"type": "status", "command": ack, "source": "Valhalla"}
    return socket.send(json.dumps(response))

def sendlog(socket, command, result):
    response = {"type": "log", "command": command, "source": "Valhalla", "output": result}
    return socket.send(json.dumps(response))

# --- Nouvelle fonction pour gérer l'exécution en parallèle ---
async def responder(ip_ordi):
    uri = f"ws://{ip_ordi}:8000/ws"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connecté à {ip_ordi}")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    # 1. Gestion du PING
                    if data.get("type") == "ping":
                        sent_at = data.get("sent_at") 
                        await websocket.send(json.dumps({
                            "type": "pong", 
                            "source": "Valhalla", 
                            "sent_at": sent_at
                        }))
                    elif data.get("command") == "print_log" and data.get("target") == "Valhalla":
                        print("envoi des logs")
                        f=open("log_test_valh.txt")
                        log_txt=f.read()
                        f.close()
                        await sendlog(websocket, "log_ack",log_txt)
                    # 4. GIT PULL
                    elif data.get("command") == "git_pull" and data.get("target") == "Valhalla":
                        # (Ton code git pull peut rester ici ou passer en asynchrone aussi)
                        try:
                            repo_path = "/home/asgard/Desktop/dassault-helics-2026"
                            result = subprocess.check_output(["git", "pull"], cwd=repo_path).decode("utf-8")
                            await sendlog(websocket, "pull_ack", result)
                        except Exception as e:
                            await sendfail(websocket, "pull_fail", str(e))

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e})")
            await asyncio.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    asyncio.run(responder(sys.argv[1]))