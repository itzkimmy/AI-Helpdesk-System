# AI Helpdesk System

A production-grade, secure, self-hosted Final Year Project (FYP4112) IT Helpdesk System.

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
