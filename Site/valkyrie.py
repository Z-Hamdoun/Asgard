import asyncio
import websockets
import json
import sys
import subprocess # Pour exécuter git pull


def sendfail(socket,failure,e):
    response = {
        "type": "status",
        "command": failure,
        "source": "Valkyrie",
        "output": e 
    }
    return socket.send(json.dumps(response))

def sendack(socket,ack):
    response = {
        "type": "status",
        "command": ack,
        "source": "Valkyrie"
    }
    return socket.send(json.dumps(response))

def sendlog(socket,command,result):
    response = {
        "type": "log",
        "command": command,
        "source": "Valkyrie",
        "output": result 
    }
    return socket.send(json.dumps(response))



async def responder(ip_ordi):
    uri = f"ws://{ip_ordi}:8000/ws"
    
    while True: # Boucle de reconnexion infinie
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connecté à {ip_ordi}")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if data.get("type") == "ping":
                        data["type"] = "pong"
                        data["source"] = "Valkyrie"
                        await websocket.send(json.dumps(data))
                    elif data.get("command") == "main_mission":
                        command = (
                        "source /rootgit/venv/bin/activate && "
                        "cd ~/Desktop/mission/dassault-helics-2026 && "
                        "python -u main.py"
                        )

                        try:
                            process = subprocess.Popen(
                                command,
                                shell=True,
                                executable="/bin/bash",
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, 
                                text=True,
                                bufsize=1 
                            )
                            print(f"--- execution de main ---")
                            
                            await sendack(websocket,"start_main_ack")
                            for line in process.stdout:
                                clean_line = line.strip()
                                if clean_line: 
                                    await sendlog(websocket, "main_log", clean_line)
                                print(clean_line)

                            return_code =process.wait()

                            if return_code != 0:
                                await sendfail(websocket,"main_fail",return_code)
                                print(f"--- Le processus s'est terminé avec l'erreur {return_code} ---")
                            
                        except subprocess.CalledProcessError as e:
                            print(f"Erreur : {e.output}")
                    elif data.get("command") == "git_pull" and data.get("target") == "Valkyrie":
                        
                        try:
                            
                            repo_path = "/home/helics/Desktop/mission/dassault-helics-2026"
                            result = subprocess.check_output(
                                ["git", "pull"], 
                                cwd=repo_path, 
                                stderr=subprocess.STDOUT
                            ).decode("utf-8")
                            await sendlog(websocket,"pull_ack",result)
                            print(result)
                        except Exception as e:
                            print(e)
                            await sendfail(websocket,"pull_fail",str(e))
                            

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e}) ctrl + C pour exit")
            await asyncio.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python Valkyrie.py <IP_DU_PC>")
        sys.exit(1)
    asyncio.run(responder(sys.argv[1]))