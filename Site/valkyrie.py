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
                    elif data.get("command") == "main_mission":
                        
                        result = subprocess.check_output(
                            ["source ~/.bashrc", "venv", "main"], 
                            stderr=subprocess.STDOUT
                        ).decode("utf-8")
                        response = {
                            "type": "status",
                            "command": "main_ack",
                            "source": "Valkyrie",
                            "output": result 
                        }

                        print(result)
                        await websocket.send(json.dumps(response))
                    elif data.get("command") == "git_pull" and data.get("target") == "Valkyrie":
                        
                        try:
                            
                            repo_path = "/home/asgard/Desktop/dassault-helics-2026"
                            result = subprocess.check_output(
                                ["git", "pull"], 
                                cwd=repo_path, 
                                stderr=subprocess.STDOUT
                            ).decode("utf-8")
                            response = {
                                "type": "status",
                                "command": "pull_check",
                                "source": "Valkyrie",
                                "output": result 
                            }

                            print(result)
                            await websocket.send(json.dumps(response))
                        except Exception as e:
                            print(e)
                            await websocket.send(json.dumps({
                                "type": "status",
                                "command": "pull_fail",
                                "source": "Valkyrie",
                                "output": str(e)
                            }))

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e}) ctrl + C pour exit")
            await asyncio.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python Valkyrie.py <IP_DU_PC>")
        sys.exit(1)
    asyncio.run(responder(sys.argv[1]))