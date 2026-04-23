from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Session as SessionModel, Batch, BatchTrainer, BatchStudent,
    Attendance, RoleEnum, User,
)
from src.schemas import (
    SessionCreate, SessionResponse,
    SessionAttendanceResponse, AttendanceWithStudent,
)
from src.auth import require_roles

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.trainer)),
):
    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Trainer must be assigned to the batch
    assignment = (
        db.query(BatchTrainer)
        .filter(
            BatchTrainer.batch_id == payload.batch_id,
            BatchTrainer.trainer_id == current_user.id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this batch",
        )

    session = SessionModel(
        batch_id=payload.batch_id,
        trainer_id=current_user.id,
        title=payload.title,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}/attendance", response_model=SessionAttendanceResponse)
def get_session_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.trainer)),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Trainer must own the session
    if session.trainer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")

    records = db.query(Attendance).filter(Attendance.session_id == session_id).all()
    student_records = []
    for r in records:
        student = r.student
        student_records.append(
            AttendanceWithStudent(
                student_id=student.id,
                student_name=student.name,
                student_email=student.email,
                status=r.status,
                marked_at=r.marked_at,
            )
        )

    return SessionAttendanceResponse(
        session_id=session.id,
        session_title=session.title,
        total=len(student_records),
        records=student_records,
    )
