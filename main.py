from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
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