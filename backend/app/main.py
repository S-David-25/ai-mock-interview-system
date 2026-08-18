import logging
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from app.config import CORS_ORIGINS
from app.database.base import init_db
from app.routes.auth import router as auth_router
from app.routes.interview import router as interview_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_mock_interview")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="AI Mock Interview System API",
    description="Backend API for AI-powered virtual interview coach and placement prep",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory if it exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Startup event
@app.on_event("startup")
def on_startup():
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Database initialized successfully.")

# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err.get("loc", [])])
        msg = err.get("msg", "Validation error")
        errors.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Input validation failed",
            "errors": errors
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred. Please try again."}
    )

# Include Routers
app.include_router(auth_router)
app.include_router(interview_router)

@app.get("/health")
def health():
    return {"status": "healthy"}

# Serve Frontend App at root
@app.get("/")
def serve_app():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "system": "AI Mock Interview System API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }
