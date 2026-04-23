from datetime import datetime, date, time
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator

from src.models import RoleEnum, AttendanceStatusEnum


# ---------- Auth ----------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: RoleEnum
    institution_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MonitoringTokenRequest(BaseModel):
    key: str


# ---------- Batch ----------

class BatchCreate(BaseModel):
    name: str
    institution_id: int


class BatchResponse(BaseModel):
    id: int
    name: str
    institution_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class InviteCreate(BaseModel):
    pass  # batch_id comes from path param


class InviteResponse(BaseModel):
    id: int
    batch_id: int
    token: str
    expires_at: datetime
    used: bool

    class Config:
        from_attributes = True


class JoinBatchRequest(BaseModel):
    token: str


# ---------- Session ----------

class SessionCreate(BaseModel):
    title: str
    date: date
    start_time: time
    end_time: time
    batch_id: int


class SessionResponse(BaseModel):
    id: int
    batch_id: int
    trainer_id: int
    title: str
    date: date
    start_time: time
    end_time: time
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Attendance ----------

class AttendanceMark(BaseModel):
    session_id: int
    status: AttendanceStatusEnum


class AttendanceRecord(BaseModel):
    id: int
    session_id: int
    student_id: int
    status: AttendanceStatusEnum
    marked_at: datetime

    class Config:
        from_attributes = True


class AttendanceWithStudent(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    status: AttendanceStatusEnum
    marked_at: datetime


class SessionAttendanceResponse(BaseModel):
    session_id: int
    session_title: str
    total: int
    records: list[AttendanceWithStudent]


# ---------- Summary ----------

class BatchSummary(BaseModel):
    batch_id: int
    batch_name: str
    total_sessions: int
    total_students: int
    attendance_rate: float


class InstitutionSummary(BaseModel):
    institution_id: int
    institution_name: str
    batches: list[BatchSummary]


class ProgrammeSummary(BaseModel):
    total_institutions: int
    total_batches: int
    total_sessions: int
    total_students: int
    overall_attendance_rate: float
    institutions: list[InstitutionSummary]


# ---------- Monitoring ----------

class MonitoringAttendanceRecord(BaseModel):
    attendance_id: int
    session_id: int
    session_title: str
    batch_id: int
    batch_name: str
    institution_id: int
    institution_name: str
    student_id: int
    student_name: str
    status: AttendanceStatusEnum
    marked_at: datetime
