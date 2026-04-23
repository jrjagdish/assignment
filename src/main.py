from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError,OperationalError
import sqlalchemy

from src.database import Base, engine
from src.routers import auth, batches, sessions, attendance, institutions, programme, monitoring



# Create all tables (idempotent – skips existing ones)
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="SkillBridge Attendance API",
    version="1.0.0",
    description="Role-based attendance management system for the SkillBridge skilling programme.",
)

@app.exception_handler(OperationalError)
def handle_operational_error(request: Request, exc: OperationalError):
    return JSONResponse(
        status_code=500,
        content={"detail": "An operational error occurred."}
    )

@app.exception_handler(sqlalchemy.exc.InternalError)
def handle_internal_error(request: Request, exc: sqlalchemy.exc.InternalError):
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal database error occurred."}
    )

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(attendance.router)
app.include_router(institutions.router)
app.include_router(programme.router)
app.include_router(monitoring.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["meta"])
def health():
    return {"status": "ok", "service": "SkillBridge API"}