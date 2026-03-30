import asyncio
import websockets
import json

async def responder():
    uri = "ws://10.113.231.244:8000/ws"
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

asyncio.run(responder())