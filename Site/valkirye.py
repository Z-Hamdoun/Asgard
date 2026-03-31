import asyncio
import websockets
import json
import sys

async def responder(ip_ordi):
    uri = f"ws://{ip_ordi}:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Valkyrie prête et à l'écoute...")
            while True:
                # Attend le Ping du serveur ou d'un autre client
                message = await websocket.recv()
                data = json.loads(message)
                
                # Si c'est un ping qui nous est destiné
                if data.get("type") == "ping":
                    data["type"] = "pong"
                    data["source"] = "Valkyrie"
                    await websocket.send(json.dumps(data))
    except Exception as e:
        print(f"Erreur : Impossible de se connecter à {ip_ordi}. {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python Valkyrie.py <IP_DU_PC>")
        sys.exit(1)

    target_ip = sys.argv[1]
    
    asyncio.run(responder(target_ip))
