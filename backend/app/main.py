from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.api import auth, teams, items
from backend.app.core.config import settings

app = FastAPI(
    title="Newtonite Operations API",
    description="High-reliability work item operations management with atomic concurrency and team authorization",
    version="1.0.0",
)

# CORS setup for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core routers
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(items.router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
