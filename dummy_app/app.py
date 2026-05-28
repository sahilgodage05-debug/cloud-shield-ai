from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import requests
import time

app = FastAPI(title="Dummy Customer App")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Serves the main interactive control screen for generating fake logs"""
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/trigger")
def trigger_action(action: dict):
    """Triggers specific types of mock logs and posts them to backend server"""
    action_type = action.get("type")
    ip = action.get("ip", "192.168.1.100")
    timestamp = time.strftime("%d/%b/%Y:%H:%M:%S")
    
    if action_type == "normal":
        log_line = f'{ip} - - [{timestamp}] "GET /index.html" 200 5120'
    elif action_type == "login_fail":
        log_line = f'{ip} - - [{timestamp}] "POST /login" 401 256'
    elif action_type == "error_500":
        log_line = f'{ip} - - [{timestamp}] "GET /checkout" 500 0'
    elif action_type == "download_10mb":
        log_line = f'{ip} - - [{timestamp}] "GET /downloads/file-10mb.zip" 200 10485760'
    elif action_type == "download_20mb":
        log_line = f'{ip} - - [{timestamp}] "GET /downloads/file-20mb.zip" 200 20971520'
    elif action_type == "download_100mb":
        log_line = f'{ip} - - [{timestamp}] "GET /downloads/file-100mb.zip" 200 104857600'
    elif action_type == "cpu_spike":
        cpu = action.get("cpu", 90)
        latency = action.get("latency", 500)
        log_line = f'{ip} - - [{timestamp}] "POST /api/checkout-process" 200 4096 [CPU:{cpu}%] [LATENCY:{latency}ms]'
    else:
        return {"error": f"Unknown action type: {action_type}"}
        
    # Send log line to Backend S3 synced log database
    try:
        res = requests.post("http://127.0.0.1:8000/api/log", json={"log_line": log_line, "ip": ip})
        return res.json()
    except Exception as e:
        return {"status": "error", "message": f"Could not sync log to backend API: {str(e)}"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
