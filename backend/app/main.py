from app.config import BACKEND_ROOT
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json
import os
import tempfile

from app.api import investigations, sprays, drift, research, toxicity, locations, realtime, weather, history, farmers

# Background task for spray simulation
spray_simulator_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start the spray simulator
    global spray_simulator_task
    spray_simulator_task = asyncio.create_task(realtime.spray_simulator()) if os.getenv("GEO_ENABLE_LEGACY_SIMULATOR") == "1" else None
    if spray_simulator_task:
        print("Started DEMO spray simulator")
    yield
    # Shutdown: cancel simulator
    if spray_simulator_task:
        spray_simulator_task.cancel()

app = FastAPI(
    title="AskGaia API",
    description="Real-time pesticide drift monitoring for California",
    version="0.1.0",
    lifespan=lifespan
)

# The historical PUR tables are tens of millions of rows and never change between runs,
# so the heavy read-only aggregates are answered once and then served from a cache.
CACHE_FILE = os.path.join(tempfile.gettempdir(), "geo_api_cache.json")
CACHED_PREFIXES = ("/api/sprays/", "/api/research/", "/api/history/")
try:
    with open(CACHE_FILE) as f:
        _cache = json.load(f)
except (OSError, ValueError):
    _cache = {}


@app.middleware("http")
async def cache_historical_reads(request: Request, call_next):
    key = request.url.path + "?" + request.url.query
    if request.method != "GET" or not request.url.path.startswith(CACHED_PREFIXES):
        return await call_next(request)
    if key in _cache:
        return Response(content=_cache[key], media_type="application/json")

    response = await call_next(request)
    if response.status_code != 200:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    _cache[key] = body.decode()
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f)
    except OSError:
        pass
    return Response(content=body, media_type="application/json")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sprays.router, prefix="/api", tags=["sprays"])
app.include_router(drift.router, prefix="/api", tags=["drift"])
app.include_router(research.router, prefix="/api", tags=["research"])
app.include_router(toxicity.router, prefix="/api", tags=["toxicity"])
app.include_router(locations.router, prefix="/api", tags=["locations"])
app.include_router(realtime.router, prefix="/api", tags=["realtime"])
app.include_router(weather.router, prefix="/api", tags=["weather"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(farmers.router, prefix="/api", tags=["farmers"])

app.include_router(investigations.router, prefix="/api", tags=["investigations"])

@app.get("/health")
def health():
    return {"status": "healthy"}

# Production preview: API routes take priority; static assets are mounted last.
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
FRONTEND_DIST = BACKEND_ROOT.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    @app.get("/explorer", include_in_schema=False)
    def explorer_page():
        return FileResponse(FRONTEND_DIST / "index.html")
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "AskGaia API. Start the frontend on port 5173, or build it to enable the single-server preview.", "version": "0.2.0"}
