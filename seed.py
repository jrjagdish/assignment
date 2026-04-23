"""
seed.py – Populate the SkillBridge database with realistic demo data.

Run:  python seed.py

Creates:
  - 2 institutions
  - 1 programme_manager, 1 monitoring_officer
  - 4 trainers (2 per institution)
  - 15 students
  - 3 batches
  - 8 sessions
  - Attendance records for every session
"""

import os
import sys
from datetime import date, time, datetime, timedelta, timezone

# Allow running from project root without installing as a package
sys.path.insert(0, os.path.dirname(__file__))

# Load .env before importing any src module
from dotenv import load_dotenv
load_dotenv()

from src.database import Base, engine, SessionLocal
from src.models import (
    User, Institution, Batch, BatchTrainer, BatchStudent,
    BatchInvite, Session as SessionModel, Attendance,
    RoleEnum, AttendanceStatusEnum,
)
from src.auth import hash_password

import secrets

db = SessionLocal()


def wipe():
    """Drop and recreate all tables (fresh seed)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✓ Tables re-created")


def run():
    wipe()

    # ── Institutions ────────────────────────────────────────────────────────
    inst1 = Institution(name="Alpha Polytechnic")
    inst2 = Institution(name="Beta Vocational Institute")
    db.add_all([inst1, inst2])
    db.flush()
    print(f"✓ Institutions: {inst1.name} (id={inst1.id}), {inst2.name} (id={inst2.id})")

    # ── Programme Manager ────────────────────────────────────────────────────
    pm = User(
        name="Programme Manager",
        email="pm@skillbridge.dev",
        hashed_password=hash_password("pm@1234"),
        role=RoleEnum.programme_manager,
    )
    db.add(pm)

    # ── Monitoring Officer ───────────────────────────────────────────────────
    mo = User(
        name="Monitoring Officer",
        email="monitor@skillbridge.dev",
        hashed_password=hash_password("monitor@1234"),
        role=RoleEnum.monitoring_officer,
    )
    db.add(mo)
    db.flush()
    print(f"✓ Programme Manager (id={pm.id}), Monitoring Officer (id={mo.id})")

    # ── Trainers (2 per institution) ─────────────────────────────────────────
    trainers_inst1 = []
    trainers_inst2 = []
    for i in range(1, 3):
        t = User(
            name=f"Trainer Alpha {i}",
            email=f"trainer.alpha{i}@skillbridge.dev",
            hashed_password=hash_password("trainer@1234"),
            role=RoleEnum.trainer,
            institution_id=inst1.id,
        )
        trainers_inst1.append(t)
        db.add(t)

    for i in range(1, 3):
        t = User(
            name=f"Trainer Beta {i}",
            email=f"trainer.beta{i}@skillbridge.dev",
            hashed_password=hash_password("trainer@1234"),
            role=RoleEnum.trainer,
            institution_id=inst2.id,
        )
        trainers_inst2.append(t)
        db.add(t)

    db.flush()
    all_trainers = trainers_inst1 + trainers_inst2
    print(f"✓ Trainers: {[t.email for t in all_trainers]}")

    # ── Institution accounts ─────────────────────────────────────────────────
    inst1_user = User(
        name="Alpha Admin",
        email="admin.alpha@skillbridge.dev",
        hashed_password=hash_password("admin@1234"),
        role=RoleEnum.institution,
        institution_id=inst1.id,
    )
    inst2_user = User(
        name="Beta Admin",
        email="admin.beta@skillbridge.dev",
        hashed_password=hash_password("admin@1234"),
        role=RoleEnum.institution,
        institution_id=inst2.id,
    )
    db.add_all([inst1_user, inst2_user])
    db.flush()

    # ── Students (15 total) ──────────────────────────────────────────────────
    students = []
    for i in range(1, 16):
        s = User(
            name=f"Student {i:02d}",
            email=f"student{i:02d}@skillbridge.dev",
            hashed_password=hash_password("student@1234"),
            role=RoleEnum.student,
        )
        students.append(s)
        db.add(s)
    db.flush()
    print(f"✓ Students: {len(students)} created")

    # ── Batches ──────────────────────────────────────────────────────────────
    batch_a = Batch(name="Batch Alpha-2024", institution_id=inst1.id)
    batch_b = Batch(name="Batch Beta-2024", institution_id=inst2.id)
    batch_c = Batch(name="Batch Gamma-2024", institution_id=inst1.id)
    db.add_all([batch_a, batch_b, batch_c])
    db.flush()
    print(f"✓ Batches: {batch_a.name}(id={batch_a.id}), {batch_b.name}(id={batch_b.id}), {batch_c.name}(id={batch_c.id})")

    # Assign trainers to batches
    db.add_all([
        BatchTrainer(batch_id=batch_a.id, trainer_id=trainers_inst1[0].id),
        BatchTrainer(batch_id=batch_a.id, trainer_id=trainers_inst1[1].id),
        BatchTrainer(batch_id=batch_b.id, trainer_id=trainers_inst2[0].id),
        BatchTrainer(batch_id=batch_b.id, trainer_id=trainers_inst2[1].id),
        BatchTrainer(batch_id=batch_c.id, trainer_id=trainers_inst1[0].id),
    ])

    # Enroll students: first 6 in batch_a, next 5 in batch_b, last 4 in batch_c
    for s in students[:6]:
        db.add(BatchStudent(batch_id=batch_a.id, student_id=s.id))
    for s in students[6:11]:
        db.add(BatchStudent(batch_id=batch_b.id, student_id=s.id))
    for s in students[11:15]:
        db.add(BatchStudent(batch_id=batch_c.id, student_id=s.id))

    db.flush()

    # ── Batch Invites (one per batch, pre-used for seed purposes) ────────────
    for batch, trainer in [(batch_a, trainers_inst1[0]), (batch_b, trainers_inst2[0]), (batch_c, trainers_inst1[0])]:
        db.add(BatchInvite(
            batch_id=batch.id,
            token=secrets.token_urlsafe(32),
            created_by=trainer.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            used=False,
        ))

    db.flush()

    # ── Sessions (8 total) ───────────────────────────────────────────────────
    base_date = date(2024, 6, 1)
    sessions = []

    session_defs = [
        # (batch, trainer, title, day_offset)
        (batch_a, trainers_inst1[0], "Python Basics", 0),
        (batch_a, trainers_inst1[0], "Data Structures", 3),
        (batch_a, trainers_inst1[1], "OOP Concepts", 6),
        (batch_b, trainers_inst2[0], "Web Fundamentals", 0),
        (batch_b, trainers_inst2[0], "HTML & CSS", 3),
        (batch_b, trainers_inst2[1], "JavaScript Intro", 7),
        (batch_c, trainers_inst1[0], "Networking Basics", 1),
        (batch_c, trainers_inst1[0], "Linux CLI", 5),
    ]

    for batch, trainer, title, day_offset in session_defs:
        s = SessionModel(
            batch_id=batch.id,
            trainer_id=trainer.id,
            title=title,
            date=base_date + timedelta(days=day_offset),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        db.add(s)
        sessions.append((s, batch))

    db.flush()
    print(f"✓ Sessions: {len(sessions)} created")

    # ── Attendance Records ───────────────────────────────────────────────────
    attendance_count = 0
    statuses = [
        AttendanceStatusEnum.present,
        AttendanceStatusEnum.present,
        AttendanceStatusEnum.present,
        AttendanceStatusEnum.late,
        AttendanceStatusEnum.absent,
    ]

    # Map batches to their students
    batch_students = {
        batch_a.id: students[:6],
        batch_b.id: students[6:11],
        batch_c.id: students[11:15],
    }

    for sess_obj, batch in sessions:
        enrolled = batch_students[batch.id]
        for idx, student in enumerate(enrolled):
            status = statuses[idx % len(statuses)]
            db.add(Attendance(
                session_id=sess_obj.id,
                student_id=student.id,
                status=status,
                marked_at=datetime.now(timezone.utc) - timedelta(hours=48 - idx),
            ))
            attendance_count += 1

    db.commit()
    print(f"✓ Attendance records: {attendance_count} created")

    print("\n✅ Seed complete!\n")
    print("Test accounts (password shown):")
    print(f"  student01@skillbridge.dev          / student@1234")
    print(f"  trainer.alpha1@skillbridge.dev     / trainer@1234")
    print(f"  admin.alpha@skillbridge.dev        / admin@1234")
    print(f"  pm@skillbridge.dev                 / pm@1234")
    print(f"  monitor@skillbridge.dev            / monitor@1234")


if __name__ == "__main__":
    try:
        run()
    finally:
        db.close()
