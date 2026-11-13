# SMSES — Smart Medical Sales & Engineering System

منصة سحابية لإدارة الوكالة والتوزيع والمبيعات والمشتريات والمخزون والمحاسبة والهندسة الطبية وخدمة ما بعد البيع.
المرجع: `SMSES-MES-001 v2.0` (انظر `docs/`).

## البنية (ADR-039)
| الطبقة | التقنية |
|---|---|
| Backend | Python 3.12 + Django 5 + DRF — Modular Monolith (`backend/apps/*`) |
| Frontend | React + TypeScript + Vite — PWA، RTL/LTR (`frontend/`) |
| DB | PostgreSQL 17 |
| Jobs | Celery + Redis |
| API | REST `/api/v1/` + OpenAPI (`/api/schema/`, `/api/docs/`) |

## التشغيل المحلي
```powershell
# Backend
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_rbac
.\.venv\Scripts\python.exe manage.py runserver

# Tests
.\.venv\Scripts\python.exe -m pytest

# Frontend
cd frontend
npm.cmd install
npm.cmd run dev
```
انسخ `backend/.env.example` إلى `backend/.env` وعدّل القيم.

## المبادئ غير القابلة للتفاوض
- الملكية ≠ الحيازة ≠ الموقع (OwnershipRecord / CustodyRecord / Location).
- الرصيد المخزني مشتق من الحركات؛ القيود المرحّلة لا تُحذف ولا تُعدَّل، بل تُعكس.
- كل تغيير حساس يُسجَّل في `AuditEvent`.
- الذكاء الاصطناعي مساعد استخراج فقط، لا جهة اعتماد.
- لا قيم ضريبية/قانونية ثابتة في الكود؛ كلها إعدادات مؤرخة.

الخطة: `docs/ROADMAP.md` · القرارات: `docs/adr/` · التقدم: `docs/PROGRESS.md`.
