from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import (
    Institution, Batch, Session as SessionModel,
    BatchStudent, Attendance, RoleEnum, User,
)
from src.schemas import ProgrammeSummary, InstitutionSummary, BatchSummary
from src.auth import require_roles

router = APIRouter(prefix="/programme", tags=["programme"])


@router.get("/summary", response_model=ProgrammeSummary)
def get_programme_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.programme_manager)),
):
    institutions = db.query(Institution).all()
    total_sessions_global = 0
    total_students_global = 0
    total_present_global = 0
    institution_summaries = []

    for institution in institutions:
        batch_summaries = []
        for batch in institution.batches:
            sessions = db.query(SessionModel).filter(SessionModel.batch_id == batch.id).all()
            total_sessions = len(sessions)
            session_ids = [s.id for s in sessions]
            total_students = len(batch.students)

            if total_sessions == 0 or total_students == 0:
                rate = 0.0
                present_count = 0
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

            total_sessions_global += total_sessions
            total_students_global += total_students
            total_present_global += present_count

            batch_summaries.append(
                BatchSummary(
                    batch_id=batch.id,
                    batch_name=batch.name,
                    total_sessions=total_sessions,
                    total_students=total_students,
                    attendance_rate=rate,
                )
            )

        institution_summaries.append(
            InstitutionSummary(
                institution_id=institution.id,
                institution_name=institution.name,
                batches=batch_summaries,
            )
        )

    denominator = total_sessions_global * total_students_global
    overall_rate = round(total_present_global / denominator * 100, 2) if denominator else 0.0

    return ProgrammeSummary(
        total_institutions=len(institutions),
        total_batches=sum(len(i.batches) for i in institutions),
        total_sessions=total_sessions_global,
        total_students=total_students_global,
        overall_attendance_rate=overall_rate,
        institutions=institution_summaries,
    )
