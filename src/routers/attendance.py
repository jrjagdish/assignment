from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Session as SessionModel, BatchStudent, Attendance,
    AttendanceStatusEnum, RoleEnum, User,
)
from src.schemas import AttendanceMark, AttendanceRecord
from src.auth import require_roles

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/mark", response_model=AttendanceRecord, status_code=status.HTTP_201_CREATED)
def mark_attendance(
    payload: AttendanceMark,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.student)),
):
    session = db.query(SessionModel).filter(SessionModel.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Student must be enrolled in the batch
    enrollment = (
        db.query(BatchStudent)
        .filter(
            BatchStudent.batch_id == session.batch_id,
            BatchStudent.student_id == current_user.id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this session's batch",
        )

    # No duplicate marking
    existing = (
        db.query(Attendance)
        .filter(
            Attendance.session_id == payload.session_id,
            Attendance.student_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already marked for this session",
        )

    record = Attendance(
        session_id=payload.session_id,
        student_id=current_user.id,
        status=payload.status,
        marked_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── 405 guard: reject non-GET on /monitoring/attendance ──────────────────────
# (also implemented in the monitoring router; kept here for completeness)
