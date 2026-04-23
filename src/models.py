import enum
from datetime import datetime, date, time

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Time,
    ForeignKey, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship

from src.database import Base


class RoleEnum(str, enum.Enum):
    student = "student"
    trainer = "trainer"
    institution = "institution"
    programme_manager = "programme_manager"
    monitoring_officer = "monitoring_officer"


class AttendanceStatusEnum(str, enum.Enum):
    present = "present"
    absent = "absent"
    late = "late"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleEnum), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    institution = relationship("Institution", back_populates="users")
    trainer_batches = relationship("BatchTrainer", back_populates="trainer")
    student_batches = relationship("BatchStudent", back_populates="student")
    sessions_created = relationship("Session", back_populates="trainer")
    attendance_records = relationship("Attendance", back_populates="student")
    invites_created = relationship("BatchInvite", back_populates="creator")


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="institution")
    batches = relationship("Batch", back_populates="institution")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    institution = relationship("Institution", back_populates="batches")
    trainers = relationship("BatchTrainer", back_populates="batch")
    students = relationship("BatchStudent", back_populates="batch")
    sessions = relationship("Session", back_populates="batch")
    invites = relationship("BatchInvite", back_populates="batch")


class BatchTrainer(Base):
    __tablename__ = "batch_trainers"

    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    trainer_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    batch = relationship("Batch", back_populates="trainers")
    trainer = relationship("User", back_populates="trainer_batches")


class BatchStudent(Base):
    __tablename__ = "batch_students"

    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    batch = relationship("Batch", back_populates="students")
    student = relationship("User", back_populates="student_batches")


class BatchInvite(Base):
    __tablename__ = "batch_invites"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    token = Column(String(512), unique=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)

    batch = relationship("Batch", back_populates="invites")
    creator = relationship("User", back_populates="invites_created")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    batch = relationship("Batch", back_populates="sessions")
    trainer = relationship("User", back_populates="sessions_created")
    attendance = relationship("Attendance", back_populates="session")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(AttendanceStatusEnum), nullable=False)
    marked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )

    session = relationship("Session", back_populates="attendance")
    student = relationship("User", back_populates="attendance_records")
