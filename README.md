# IBSALA — Classroom Schedule System

> A web platform for real-time classroom, schedule, and professor lookup — built for **IBMEC BH**.
> Live at: **[ibsala.com.br](https://ibsala.com.br)**

---

## What is it

IBSALA automatically captures the institution's official daily schedule spreadsheet and makes it available to all students in a fast, organized interface — no login required for public queries.

Registered students get a personal dashboard with their day's classes and receive automatic email notifications 30 minutes before each class with the room, time, and professor.

---

## Features

### Public (no login)
- **Instant lookup** — browse by category (morning, afternoon, night) or free-text search
- **Free rooms by shift** — toggle shows unoccupied rooms for each of the 6 daily shifts; current shift highlighted with a `NOW` badge
- **About** — platform documentation accessible from the main menu

### Registered student
- **Today's classes** — dashboard after login with room, time, and professor for each class of the day
- **All subjects** — full list of registered subjects
- **Settings** — email notification toggle and subject management by weekday and shift
- **Username recovery** — sends username to registered email
- **Welcome email** — automatically sent on registration

### Admin panel
- Permanent subject database (add, edit, delete)
- Student database (create, edit, block, delete)
- Send today's schedule email to one or all students
- Manually re-fetch the spreadsheet at any time
- Lock/unlock the entire site with one click
- Automated monitoring alerts per shift

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 · Flask · SQLite |
| Frontend | Plain HTML/CSS/JS (single-page, no framework) |
| Email | Resend API |
| Spreadsheet | Google Sheets API + public CSV fallback |
| Scheduler | APScheduler |
| Server | Nginx (reverse proxy, HTTPS, rate limiting) |
| Infrastructure | Google Cloud Compute Engine (e2-standard-2) |
| Certificate | Let's Encrypt (auto-renewal) |

---

## Architecture

```
ibsala.com.br
     │
     ▼
  [ Nginx ]  ← HTTPS, rate limiting, www → canonical redirect
     │
     ▼
  [ Gunicorn + Flask :5000 ]
     ├── GET  /                         → index.html (SPA)
     ├── GET  /api/status               → date, today's records, totals
     ├── POST /api/buscar               → free-text search filtered by today
     ├── GET  /api/categoria            → records by category
     ├── GET  /api/salas-livres-slots   → free rooms per shift
     ├── POST /api/login                → student access by username
     ├── POST /api/cadastrar            → new student registration
     ├── POST /api/minhas-aulas         → logged-in student's classes today
     ├── POST /api/materias             → list student subjects
     ├── POST /api/adicionar-materia    → add subject
     ├── POST /api/remover-materia      → remove subject
     ├── POST /api/configuracoes        → toggle email notifications
     ├── POST /api/recuperar-username   → send username by email
     └── POST /api/adm/*               → admin panel (authenticated)

  [ SQLite ]
     ├── alunos                (id, username, email, criado, bloqueado, receber_email)
     ├── materias              (aluno_id, dia, turma, disciplina, professor, slot)
     └── disciplinas_historico (id, turma, disciplina, professor, codigo)

  [ Scheduler ] — separate systemd service (APScheduler)
     ├── 07:00 → fetch spreadsheet + notify 1st Morning (07:30)
     ├── 09:20 → notify 2nd Morning (09:50)
     ├── 12:30 → notify 1st Afternoon (13:00)
     ├── 13:30 → notify 2nd Afternoon (14:00)
     ├── 17:30 → notify 1st Evening (18:00)
     └── 18:30 → notify 2nd Evening (19:00)
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Google account with access to the schedule spreadsheet
- [Resend](https://resend.com) account for transactional email

### Installation

```bash
git clone https://github.com/joshazze/app-salas.git
cd app-salas
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Fill in your values
```

| Variable | Description |
|---|---|
| `ADM_PASSWORD` | Admin panel password |
| `DB_PATH` | Path to SQLite database (defaults to `./alunos.db`) |
| `RESEND_API_KEY` | Your Resend API key |
| `ADMIN_EMAIL` | Email address for monitoring alerts |

For Google Sheets access, place your `credentials.json` (service account) in the project root.

### Running

```bash
# Web server
python3 server.py

# Scheduler (separate process)
python3 scheduler.py
```

Access at `http://localhost:5000`

---

## Security

- Rate limiting via Nginx: 20 req/min on auth routes, 60 req/min general
- Admin password via environment variable (never committed)
- Google credentials excluded from repository (`.gitignore`)
- HSTS enabled, forced HTTPS redirect
- Students identified by username only — no password stored
- C1 character cleanup and NFC normalization on all spreadsheet data

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

Built by **Joshua Azze** for IBtech (IBMEC) · [salas.ibtech@gmail.com](mailto:salas.ibtech@gmail.com)
