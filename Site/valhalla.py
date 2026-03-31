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
                        data["source"] = "Valhalla"
                        await websocket.send(json.dumps(data))
                    
                    elif data.get("command") == "git_pull" and data.get("target") == "Valhalla":
                        
                        try:
                            
                            repo_path = "/home/helics/Desktop/mission/dassault-helics-2026"
                            result = subprocess.check_output(
                                ["git", "pull"], 
                                cwd=repo_path, 
                                stderr=subprocess.STDOUT
                            ).decode("utf-8")
                            response = {
                                "type": "status",
                                "command": "pull_check",
                                "source": "Valhalla",
                                "output": result 
                            }

                            print(result)
                            await websocket.send(json.dumps(response))
                        except Exception as e:
                            print(e)
                            await websocket.send(json.dumps({
                                "type": "status",
                                "command": "pull_fail",
                                "source": "Valhalla",
                                "output": str(e)
                            }))

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e}) ctrl + C pour exit")
            await asyncio.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python Valhalla.py <IP_DU_PC>")
        sys.exit(1)
    asyncio.run(responder(sys.argv[1]))