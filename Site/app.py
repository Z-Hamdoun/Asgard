from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import time

app = FastAPI()

# 1. On "monte" le dossier static pour qu'il soit accessible via /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. On configure le moteur de templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html"
    )
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json({"server_time": int(time.time() * 1000)})
        await asyncio.sleep(1)
