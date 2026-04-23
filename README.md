# SkillBridge Attendance API

A fully role-based REST API for the **SkillBridge** state-level skilling programme. Built with FastAPI + PostgreSQL (Neon), secured with JWT-based RBAC, and deployed on Render.

---

## 1. Live API Base URL

```
https://skillbridge-api.onrender.com
```

> **Note:** Render free tier spins down after inactivity — the first request may take 30–60 s to cold-start.

### Working curl against live deployment

```bash
curl -s -X POST https://skillbridge-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student01@skillbridge.dev","password":"student@1234"}' | python -m json.tool
```

---

## 2. Local Setup (from scratch)

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd assignment

# 2. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
#    Edit .env and set DATABASE_URL to your Neon (or local) PostgreSQL connection string

# 5. Seed the database
python seed.py

# 6. Start the development server
uvicorn src.main:app --reload --port 8000
```

Open the interactive docs at http://localhost:8000/docs

---

## 3. Test Accounts (all roles)

| Role | Email | Password |
|---|---|---|
| Student | `student01@skillbridge.dev` | `student@1234` |
| Trainer | `trainer.alpha1@skillbridge.dev` | `trainer@1234` |
| Institution | `admin.alpha@skillbridge.dev` | `admin@1234` |
| Programme Manager | `pm@skillbridge.dev` | `pm@1234` |
| Monitoring Officer | `monitor@skillbridge.dev` | `monitor@1234` |

---

## 4. Sample curl Commands

Replace `BASE` with `http://localhost:8000` locally or the live URL above.

### Auth

```bash
# Signup
curl -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane Doe","email":"jane@test.dev","password":"pass1234","role":"student"}'

# Login – returns standard JWT
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student01@skillbridge.dev","password":"student@1234"}'

# Step 1: Login as Monitoring Officer to obtain standard token
STANDARD_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"monitor@skillbridge.dev","password":"monitor@1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 2: Exchange standard token + API key for scoped monitoring token
MONITOR_TOKEN=$(curl -s -X POST $BASE/auth/monitoring-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $STANDARD_TOKEN" \
  -d '{"key":"skillbridge-monitor-secret-2024"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Batches

```bash
# Create batch (trainer or institution)
TRAINER_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"trainer.alpha1@skillbridge.dev","password":"trainer@1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST $BASE/batches \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"New Batch","institution_id":1}'

# Generate invite link (trainer assigned to batch)
curl -X POST $BASE/batches/1/invite \
  -H "Authorization: Bearer $TRAINER_TOKEN"

# Student joins via invite token
STUDENT_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student01@skillbridge.dev","password":"student@1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST $BASE/batches/join \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"<invite-token-here>"}'

# Batch summary (institution or programme_manager)
INST_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin.alpha@skillbridge.dev","password":"admin@1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl $BASE/batches/1/summary \
  -H "Authorization: Bearer $INST_TOKEN"
```

### Sessions

```bash
# Create session (trainer)
curl -X POST $BASE/sessions \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Intro to SQL","date":"2024-09-01","start_time":"09:00:00","end_time":"11:00:00","batch_id":1}'

# Get session attendance (trainer)
curl $BASE/sessions/1/attendance \
  -H "Authorization: Bearer $TRAINER_TOKEN"
```

### Attendance

```bash
# Student marks attendance
curl -X POST $BASE/attendance/mark \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"status":"present"}'
```

### Institution & Programme

```bash
# Institution summary (programme_manager or institution)
PM_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pm@skillbridge.dev","password":"pm@1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl $BASE/institutions/1/summary -H "Authorization: Bearer $PM_TOKEN"

# Programme-wide summary (programme_manager only)
curl $BASE/programme/summary -H "Authorization: Bearer $PM_TOKEN"
```

### Monitoring Officer

```bash
# Use the scoped MONITOR_TOKEN from the Auth section above
curl $BASE/monitoring/attendance \
  -H "Authorization: Bearer $MONITOR_TOKEN"
```

---

## 5. Schema Decisions

### `batch_trainers` (many-to-many junction)
A batch can have multiple trainers, and a trainer can work across multiple batches. A simple junction table with a composite primary key (`batch_id`, `trainer_id`) handles this cleanly without an extra surrogate key.

### `batch_invites` — token-based enrollment
Rather than having an admin directly enrol students, trainers generate single-use URL tokens. This reflects real-world workflows (WhatsApp links, QR codes) and keeps the signup flow self-service. Tokens have a 7-day TTL and are marked `used = true` on first redemption, preventing replay.

### Dual-token approach for Monitoring Officer
The Monitoring Officer role uses a **two-factor token flow**:
1. **Standard JWT** (24 h) — obtained via normal login; proves identity.
2. **Scoped monitoring token** (1 h) — obtained by presenting the standard JWT _plus_ a hardcoded API key via `POST /auth/monitoring-token`. This token has `scope: "monitoring"` in its payload and is the only credential accepted by `GET /monitoring/attendance`.

This separation ensures that:
- Even a stolen standard JWT cannot access monitoring data without the API key.
- Monitoring access can be revoked independently by rotating the API key.

### JWT Payload Structure

**Standard token** (all roles except monitoring scoped):
```json
{
  "sub": "42",
  "role": "trainer",
  "iat": 1713000000,
  "exp": 1713086400
}
```

**Monitoring scoped token**:
```json
{
  "sub": "7",
  "role": "monitoring_officer",
  "scope": "monitoring",
  "iat": 1713000000,
  "exp": 1713003600
}
```

### Token Rotation / Revocation (production approach)
- Store a `token_version` integer on each `User` row.
- Embed `token_version` in the JWT payload at issue time.
- On each request, fetch the user and assert `payload.token_version == user.token_version`.
- Increment `token_version` to instantly invalidate all existing tokens for that user.
- For the monitoring API key, store it in a secrets manager (AWS Secrets Manager / Doppler) and support multiple valid keys to allow zero-downtime rotation.

### One Known Security Issue
**The API key is hardcoded in `.env` with no server-side list of issued monitoring tokens.** If a monitoring token is stolen within its 1-hour window, there is no way to revoke it short of changing the `SECRET_KEY` (which would invalidate all tokens). Fix: maintain a short-lived Redis allowlist of issued monitoring token JTI values and check it on every monitoring request, with the ability to delete a JTI to revoke mid-session.

---

## 6. Status

| Task | Status |
|---|---|
| Task 1 – Data model & all endpoints | ✅ Complete |
| Task 2 – JWT auth + dual-token monitoring | ✅ Complete |
| Task 3 – Validation, error handling, 7 pytest tests | ✅ Complete |
| Task 4 – Deployment (Render + Neon) | ✅ Deployed |
| Task 5 – README | ✅ This document |

**What is partially done / skipped:**
- Alembic migration files are not included — `create_all` is called at startup instead (acceptable for a prototype).
- No rate-limiting on `/auth/login` (would add with `slowapi` in production).

---

## 7. One Thing I'd Do Differently

I would introduce **Alembic migrations from day one** rather than relying on `Base.metadata.create_all`. Even in a prototype, schema drift between local dev and the deployed database caused several debugging sessions. Proper migrations give a reliable, reproducible upgrade path and make the schema history reviewable in code review.

---

## Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | FastAPI 0.111 | Async-ready, automatic OpenAPI docs, native Pydantic v2 |
| Database | Neon (PostgreSQL) | Free tier, serverless scaling, standard SQL |
| ORM | SQLAlchemy 2.0 | Mature, explicit, great relationship support |
| Auth | python-jose + passlib[bcrypt] | Well-maintained, standard JOSE implementation |
| Deployment | Render | Free tier, GitHub auto-deploy, env var management |
