from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os

# Import our agent logic
from agent_engine import process_user_request

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/debug/api-key-check")
async def check_api_key():
    """Debug endpoint to verify API key is loaded (shows last 4 characters only for security)"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return JSONResponse({
            "status": "error",
            "message": "GOOGLE_API_KEY environment variable is NOT set"
        })
    return JSONResponse({
        "status": "ok",
        "message": "API key is loaded",
        "key_preview": f"...{api_key[-4:]}",
        "key_length": len(api_key)
    })

@app.post("/search")
async def search(
    request: Request,
    query: str = Form(...),
    profile: str = Form(...),
    location: str = Form(...)
):
    # Call the Agent
    results = process_user_request(query, profile, location)
    
    # Return the page with results populated
    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": results,
        "query": query,
        "profile": profile,
        "location": location
    })