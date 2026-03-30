import asyncio
import websockets
import json
import time

async def heartbeat():
    uri = "ws://10.113.231.244:8000/ws" 
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("Connecté à la Station au Sol")
                while True:
                    # Envoi du heartbeat avec le timestamp actuel
                    payload = json.dumps({
                        "source": "Valkyrie",
                        "client_send_time": int(time.time() * 1000)
                    })
                    await websocket.send(payload)
                    
                    # Attendre la réponse (echo) si nécessaire
                    response = await websocket.recv()
                    
                    await asyncio.sleep(1) # Attendre 1 seconde
        except Exception as e:
            print(f"Erreur de connexion : {e}. Nouvel essai dans 3s...")
            await asyncio.sleep(3)

asyncio.run(heartbeat())