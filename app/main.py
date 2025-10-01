# app/main.py
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes import reports
from app.config import settings
from datetime import datetime

# Create application directories if they don't exist
os.makedirs("app/static/uploads", exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="Security Report Wizard",
    description="A wizard for generating security reports from various data sources",
    version="1.0.0"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Include routes
app.include_router(reports.router)

# Root route - redirect to wizard
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    year = datetime.now().year
    return templates.TemplateResponse(
        "report_wizard.html",
        {"request": request, "step": 1, "year": year}
    )

# Error handlers
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def server_error_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)