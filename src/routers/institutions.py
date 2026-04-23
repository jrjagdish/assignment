from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Institution, Batch, Session as SessionModel, Attendance, RoleEnum, User
from src.schemas import InstitutionSummary, BatchSummary
from src.auth import require_roles

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("/{institution_id}/summary", response_model=InstitutionSummary)
def get_institution_summary(
    institution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.programme_manager, RoleEnum.institution)),
):
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    batch_summaries = []
    for batch in institution.batches:
        sessions = db.query(SessionModel).filter(SessionModel.batch_id == batch.id).all()
        total_sessions = len(sessions)
        session_ids = [s.id for s in sessions]
        total_students = len(batch.students)

        if total_sessions == 0 or total_students == 0:
            rate = 0.0
        else:
            present_count = (
                db.query(Attendance)
                .filter(
                    Attendance.session_id.in_(session_ids),
                    Attendance.status.in_(["present", "late"]),
                )
                .count()
            )
            rate = round(present_count / (total_sessions * total_students) * 100, 2)

        batch_summaries.append(
            BatchSummary(
                batch_id=batch.id,
                batch_name=batch.name,
                total_sessions=total_sessions,
                total_students=total_students,
                attendance_rate=rate,
            )
        )

    return InstitutionSummary(
        institution_id=institution.id,
        institution_name=institution.name,
        batches=batch_summaries,
    )
