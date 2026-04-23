from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Attendance, Session as SessionModel, Batch, Institution, User,
)
from src.schemas import MonitoringAttendanceRecord
from src.auth import get_current_monitoring_user

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# ── 405 guard: reject any non-GET method ────────────────────────────────────
@router.post("/attendance", include_in_schema=False)
@router.put("/attendance", include_in_schema=False)
@router.patch("/attendance", include_in_schema=False)
@router.delete("/attendance", include_in_schema=False)
async def monitoring_method_not_allowed():
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Method Not Allowed. This endpoint only supports GET.",
    )


# ── GET /monitoring/attendance ───────────────────────────────────────────────
@router.get("/attendance", response_model=list[MonitoringAttendanceRecord])
def get_monitoring_attendance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_monitoring_user),
):
    """
    Read-only, programme-wide attendance dump.
    Requires a valid short-lived monitoring-scoped token (not the standard JWT).
    Obtain it via POST /auth/monitoring-token with your API key.
    """
    rows = (
        db.query(
            Attendance.id.label("attendance_id"),
            Attendance.session_id,
            SessionModel.title.label("session_title"),
            SessionModel.batch_id,
            Batch.name.label("batch_name"),
            Batch.institution_id,
            Institution.name.label("institution_name"),
            Attendance.student_id,
            User.name.label("student_name"),
            Attendance.status,
            Attendance.marked_at,
        )
        .join(SessionModel, Attendance.session_id == SessionModel.id)
        .join(Batch, SessionModel.batch_id == Batch.id)
        .join(Institution, Batch.institution_id == Institution.id)
        .join(User, Attendance.student_id == User.id)
        .order_by(Attendance.marked_at.desc())
        .all()
    )

    return [
        MonitoringAttendanceRecord(
            attendance_id=r.attendance_id,
            session_id=r.session_id,
            session_title=r.session_title,
            batch_id=r.batch_id,
            batch_name=r.batch_name,
            institution_id=r.institution_id,
            institution_name=r.institution_name,
            student_id=r.student_id,
            student_name=r.student_name,
            status=r.status,
            marked_at=r.marked_at,
        )
        for r in rows
    ]
