# Beyond2U AI-Powered IT Helpdesk Ticket System

A production-grade, secure, self-hosted Final Year Project (FYP4112) IT Helpdesk System built for **Beyond2U Sdn Bhd**.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green)
![Security](https://img.shields.io/badge/Security-Argon2id%20%7C%20CSRF%20%7C%20CSP-red)
![License](https://img.shields.io/badge/License-Proprietary-lightgrey)

---

## Key Features

- **AI-Powered Ticket Triage:** Automated ML classification for Category and Priority with confidence scores.
- **Deterministic Technician Assignment:** Skill-based routing based on workload, proficiency, and assignment history.
- **Tamper-Evident Audit Ledger:** Cryptographic SHA-256 hash-chained event timeline for all ticket actions.
- **SLA Management & Automated Alerts:** Real-time tracking of SLA deadlines (`Healthy` → `Approaching` → `Breached`) with background scanner.
- **Role-Based Access Control (RBAC):** Strict separation of Client, Technician, and Administrator roles with CSRF protection and rate limiting.
- **Admin Dashboard & Analytics:** Interactive Chart.js visualisations, KPI cards, and CSV export.
- **Accessible & Responsive Design:** WCAG AAA contrast, ARIA landmarks, mobile-optimized design token CSS system.

---

## Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Installation
```bash
# Clone repository
git clone https://github.com/beyond2u/helpdesk.git
cd helpdesk

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup
```bash
cp .env.example .env
```

### 4. Database Setup & Seed
```bash
# Apply database migrations
python -m flask db upgrade

# Seed default organization, SLA policies, skills, and users
python -m flask seed

# Train initial ML classification models
python -m flask train-models
```

### 5. Running the Application
```bash
# Run Flask web server
python wsgi.py

# In a separate terminal, run the SLA Background Scheduler
python scheduler.py
```
Open your browser at `http://127.0.0.1:5000`.

---

## Default Seed Credentials

| Role | Username | Email | Password |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin@beyond2u.com` | `AdminPassword123!` |
| **Technician (Hardware)** | `tech_hw` | `tech_hw@beyond2u.com` | `TechPassword123!` |
| **Technician (Network)** | `tech_net` | `tech_net@beyond2u.com` | `TechPassword123!` |
| **Technician (Software)** | `tech_sw` | `tech_sw@beyond2u.com` | `TechPassword123!` |
| **Client User** | `client_user` | `client@beyond2u.com` | `ClientPassword123!` |

---

## Docker Deployment (Production)

Deploy the full stack (Web App, Background Scheduler) with a single command:

```bash
docker-compose up -d --build
```
Access point:
- **Helpdesk Web Application:** `http://localhost:5000`

---

## CLI Management Commands

```bash
# Seed database with reference data and demo tickets
python -m flask seed

# Train/retrain ML classification models
python -m flask train-models

# Verify SHA-256 audit chain integrity across all tickets
python -m flask verify-audit
```

---

## Security Architecture

- **Password Hashing:** Argon2id via `argon2-cffi`.
- **CSRF Protection:** Flask-WTF CSRF tokens on all state-changing POST forms.
- **Content Security Policy (CSP):** Strict `default-src 'self'`, `frame-ancestors 'none'`, `X-Frame-Options: DENY`.
- **Rate Limiting:** Flask-Limiter enforcing 10 attempts/min on login endpoints.
- **Tamper-Evident Ledger:** Every ticket action creates a SHA-256 hash incorporating the previous event's hash (`0*64` genesis).

---

## Project Structure

```
Helpdesk/
├── app/
│   ├── blueprints/         # Role-based controllers (auth, client, technician, admin, main, kb)
│   ├── ml/                 # Trained ML models and classification pipeline
│   ├── models/             # SQLAlchemy ORM models & state machines
│   ├── services/           # Core business logic (tickets, audit, assignment, SLA, classification)
│   ├── static/             # CSS design tokens, Bootstrap 5, Chart.js, branding
│   ├── templates/          # Jinja2 HTML templates
│   ├── config.py           # Multi-environment configuration
│   ├── extensions.py       # Centrally initialized Flask extensions
│   └── __init__.py         # Application factory
├── instance/               # SQLite database storage & file uploads
├── migrations/             # Alembic database migrations
├── scripts/                # Seed, ML training, and audit verification CLI scripts
├── Dockerfile              # Container definition
├── docker-compose.yml      # Multi-container orchestrator
├── scheduler.py            # Dedicated background SLA state worker
├── wsgi.py                 # WSGI entry point
└── requirements.txt        # Python dependencies
```

---

## License

Copyright &copy; 2024 Beyond2U Sdn Bhd. All Rights Reserved.
