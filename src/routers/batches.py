import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Batch, BatchInvite, BatchStudent, BatchTrainer,
    Institution, RoleEnum, User,
)
from src.schemas import (
    BatchCreate, BatchResponse,
    InviteResponse, JoinBatchRequest,
    BatchSummary,
)
from src.auth import require_roles, get_current_user

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.trainer, RoleEnum.institution)),
):
    institution = db.query(Institution).filter(Institution.id == payload.institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    batch = Batch(name=payload.name, institution_id=payload.institution_id)
    db.add(batch)
    db.flush()

    # Auto-assign trainer to batch if caller is a trainer
    if current_user.role == RoleEnum.trainer:
        bt = BatchTrainer(batch_id=batch.id, trainer_id=current_user.id)
        db.add(bt)

    db.commit()
    db.refresh(batch)
    return batch


@router.post("/{batch_id}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_invite(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.trainer)),
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Ensure trainer belongs to this batch
    assignment = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == batch_id, BatchTrainer.trainer_id == current_user.id)
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this batch",
        )

    token = secrets.token_urlsafe(32)
    invite = BatchInvite(
        batch_id=batch_id,
        token=token,
        created_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        used=False,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.post("/join", status_code=status.HTTP_200_OK)
def join_batch(
    payload: JoinBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.student)),
):
    invite = db.query(BatchInvite).filter(BatchInvite.token == payload.token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite token not found")
    if invite.used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token already used")
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token has expired")

    existing = (
        db.query(BatchStudent)
        .filter(BatchStudent.batch_id == invite.batch_id, BatchStudent.student_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled in this batch")

    bs = BatchStudent(batch_id=invite.batch_id, student_id=current_user.id)
    db.add(bs)
    invite.used = True
    db.commit()
    return {"message": "Joined batch successfully", "batch_id": invite.batch_id}


@router.get("/{batch_id}/summary", response_model=BatchSummary)
def get_batch_summary(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.institution, RoleEnum.programme_manager)),
):
    from src.models import Session as SessionModel, Attendance

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    sessions = db.query(SessionModel).filter(SessionModel.batch_id == batch_id).all()
    total_sessions = len(sessions)
    session_ids = [s.id for s in sessions]

    student_ids = [bs.student_id for bs in batch.students]
    total_students = len(student_ids)

    if total_sessions == 0 or total_students == 0:
        attendance_rate = 0.0
    else:
        present_count = (
            db.query(Attendance)
            .filter(
                Attendance.session_id.in_(session_ids),
                Attendance.status.in_(["present", "late"]),
            )
            .count()
        )
        attendance_rate = round(present_count / (total_sessions * total_students) * 100, 2)

    return BatchSummary(
        batch_id=batch.id,
        batch_name=batch.name,
        total_sessions=total_sessions,
        total_students=total_students,
        attendance_rate=attendance_rate,
    )
