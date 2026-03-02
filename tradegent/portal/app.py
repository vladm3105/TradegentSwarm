#!/usr/bin/env python3
"""
Tradegent Portal - Unified Trading Dashboard
============================================
Embeds Metabase dashboards with navigation to other services.

Run: cd tradegent && python portal/app.py
Opens: http://localhost:8000
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
from pathlib import Path

app = FastAPI(title="Tradegent Portal", version="1.0.0")

# Templates directory
PORTAL_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(PORTAL_DIR / "templates"))

# Configuration
CONFIG = {
    "metabase_url": os.getenv("METABASE_URL", "http://localhost:3001"),
    "metabase_public_uuid": os.getenv("METABASE_PUBLIC_UUID", "487f5bab-e24a-414c-9dd1-622ea6c72305"),
    "streamlit_url": os.getenv("STREAMLIT_URL", "http://localhost:8501"),
    "neo4j_url": os.getenv("NEO4J_URL", "http://localhost:7475"),
    "ib_vnc_url": os.getenv("IB_VNC_URL", "http://localhost:5902"),
}

# Navigation items
NAV_ITEMS = [
    {"id": "dashboard", "name": "Dashboard", "icon": "📊", "type": "metabase"},
    {"id": "analyses", "name": "Analyses", "icon": "📈", "type": "metabase_question", "question_id": None},
    {"id": "trades", "name": "Trades", "icon": "💹", "type": "metabase_question", "question_id": None},
    {"id": "streamlit", "name": "Custom Views", "icon": "🔬", "type": "external", "url": CONFIG["streamlit_url"]},
    {"id": "graph", "name": "Knowledge Graph", "icon": "🕸️", "type": "external", "url": CONFIG["neo4j_url"]},
    {"id": "gateway", "name": "IB Gateway", "icon": "🖥️", "type": "external", "url": CONFIG["ib_vnc_url"]},
]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main portal page with embedded Metabase dashboard."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "config": CONFIG,
        "nav_items": NAV_ITEMS,
        "active_page": "dashboard",
        "embed_url": f"{CONFIG['metabase_url']}/public/dashboard/{CONFIG['metabase_public_uuid']}",
    })


@app.get("/page/{page_id}", response_class=HTMLResponse)
async def page(request: Request, page_id: str):
    """Dynamic page routing."""
    nav_item = next((item for item in NAV_ITEMS if item["id"] == page_id), None)

    if not nav_item:
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)

    if nav_item["type"] == "external":
        embed_url = nav_item["url"]
    elif nav_item["type"] == "metabase":
        embed_url = f"{CONFIG['metabase_url']}/public/dashboard/{CONFIG['metabase_public_uuid']}"
    elif nav_item["type"] == "metabase_question" and nav_item.get("question_id"):
        embed_url = f"{CONFIG['metabase_url']}/public/question/{nav_item['question_id']}"
    else:
        embed_url = f"{CONFIG['metabase_url']}/public/dashboard/{CONFIG['metabase_public_uuid']}"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "config": CONFIG,
        "nav_items": NAV_ITEMS,
        "active_page": page_id,
        "embed_url": embed_url,
    })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "tradegent-portal"}


if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║  Tradegent Portal                        ║")
    print("║  http://localhost:8000                   ║")
    print("╚══════════════════════════════════════════╝")
    uvicorn.run(app, host="0.0.0.0", port=8000)
