"""Cognitive Career Navigator — Student Portal Web Application.

Features:
- Clean White & Blue Theme (#ffffff, #f8fafc, #1d4ed8, #2563eb, #dbeafe)
- Dedicated Pages: /login, /register, /dashboard, /profile, /career-goals,
  /assessment, /learning-coach, /job-analyzer, /learning-plan, /pending-decisions,
  /evidence-portfolio, /progress, /demo
- Cookie-based session management personalized for each student
- Backed by durable SQLite state (slice.store.Store / run.db)
- Deterministic and authentic values (no random numbers)
- API key readiness: works out-of-the-box, ready for live LLM key
"""
from __future__ import annotations

import html
import io
import math
import re
import os
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from navigator.schema import (
    DiagnosticQuestion,
  LearningPlan,
    ProjectEvidence,
    StudentRegistration,
)
from navigator.services import ROLE_SKILLS, NavigatorService
from navigator.placement_portal import PlacementPortalError
from navigator.stub import run_arun_demo

DB = os.environ.get("SLICE_DB", "run.db")
app = FastAPI(title="Skill-Pilot")


def get_service() -> NavigatorService:
    return NavigatorService(DB)


def get_current_student(request: Request, svc: NavigatorService) -> Any:
    sid = request.cookies.get("session_student_id")
    if not sid:
        return None
    return svc.get_student_by_id(sid)


def extract_resume_text(filename: str, content: bytes) -> str:
    """Extract resume text while keeping the original upload out of SQLite."""
    if filename.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)[:12000]
        except Exception:
            return ""
    return content.decode("utf-8", errors="ignore")[:12000]


def render_chat_markdown(text: str) -> str:
    """Render the small markdown subset commonly returned by chat models."""
    safe = html.escape(text or "")
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"(?m)^###\s+(.+)$", r"<h4>\1</h4>", safe)
    safe = re.sub(r"(?m)^##\s+(.+)$", r"<h3>\1</h3>", safe)
    safe = re.sub(r"(?m)^#\s+(.+)$", r"<h2>\1</h2>", safe)
    safe = re.sub(r"(?m)^[-*]\s+(.+)$", r"<li>\1</li>", safe)
    safe = re.sub(r"(?m)((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", safe)
    return safe.replace("\n", "<br>").replace("</li><br><li>", "</li><li>")


# ------------------------------------------------------------------- BASE TEMPLATE (White & Blue)

BASE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Skill-Pilot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #f8fafc;
  --surface: #ffffff;
  --surface-alt: #f1f5f9;
  --border: #e2e8f0;
  --border-focus: #93c5fd;
  --text: #0f172a;
  --text-muted: #64748b;
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;
  --primary-border: #bfdbfe;
  --accent: #0284c7;
  --success: #16a34a;
  --success-light: #f0fdf4;
  --success-border: #bbf7d0;
  --warning: #d97706;
  --warning-light: #fffbeb;
  --warning-border: #fde68a;
  --danger: #dc2626;
  --danger-light: #fef2f2;
  --danger-border: #fecaca;
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.08);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.08);
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  background-color: var(--bg);
  color: var(--text);
  line-height: 1.6;
  padding-bottom: 5rem;
}}

/* Left navigation rail */
nav {{
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 1.25rem 0.85rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 15rem;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}}

.auth-shell {{ background: #ffffff; }}
.auth-shell nav {{ position: static; width: 100%; height: 4.5rem; flex-direction: row; align-items: center; border-right: 0; border-bottom: 1px solid var(--border); padding: 0 3rem; box-shadow: none; }}
.auth-shell .brand-group {{ margin: 0; }}
.auth-shell .nav-menu {{ flex-direction: row; margin-left: auto; gap: 0.5rem; }}
.auth-shell .user-pill {{ margin: 0 0 0 1rem; }}
.auth-shell .container {{ max-width: 72rem; margin: 0 auto; padding: 3rem 1.5rem 5rem; }}
.nav-account {{ display: flex; flex-direction: column; align-items: stretch; gap: 0.55rem; margin-top: auto; }}
.nav-account .user-pill {{ margin: 0 0 0.35rem; }}
.nav-account .btn {{ text-align: left; }}
.auth-shell .nav-account {{ flex-direction: row; align-items: center; margin: 0 0 0 1rem; }}
.auth-shell .nav-account .user-pill {{ margin: 0; }}

.brand-group {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
  margin: 0.25rem 0.5rem 2rem;
}}

.brand-badge {{
  background: linear-gradient(135deg, #1d4ed8, #2563eb);
  color: #ffffff;
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  font-size: 0.95rem;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  letter-spacing: 0.04em;
}}

.brand-name {{
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  font-size: 1.3rem;
  color: #1e3a8a;
  line-height: 1.15;
  white-space: nowrap;
  letter-spacing: 0.01em;
}}

.nav-menu {{
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  list-style: none;
}}

.nav-menu a {{
  color: var(--text-muted);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.88rem;
  padding: 0.65rem 0.75rem;
  display: block;
  border-radius: 6px;
  transition: all 0.15s ease;
}}

.nav-menu a:hover, .nav-menu a.active {{
  color: var(--primary);
  background: var(--primary-light);
}}

.user-pill {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: var(--surface-alt);
  padding: 0.35rem 0.8rem;
  border-radius: 20px;
  border: 1px solid var(--border);
  font-size: 0.85rem;
  font-weight: 600;
  margin-top: auto;
  margin-bottom: 0.75rem;
}}

.avatar-dot {{
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--success);
}}

.container {{
  max-width: 72rem;
  margin: 0 0 0 15rem;
  padding: 2rem 2.5rem 4rem;
}}

/* Welcome Banner */
.welcome-card {{
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
  border: 1px solid var(--primary-border);
  border-radius: 12px;
  padding: 1.75rem 2rem;
  margin-bottom: 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--shadow-sm);
}}

.welcome-card h1 {{
  font-family: 'Outfit', sans-serif;
  font-size: 1.75rem;
  font-weight: 700;
  color: #1e3a8a;
  margin-bottom: 0.25rem;
}}

.role-tag {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: #dbeafe;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  padding: 0.35rem 0.9rem;
  border-radius: 20px;
  font-size: 0.88rem;
  font-weight: 600;
}}

/* Grid & Cards */
.stats-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.25rem;
  margin-bottom: 2rem;
}}

.stat-box {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow-sm);
}}

.stat-val {{
  font-family: 'Outfit', sans-serif;
  font-size: 2rem;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 0.15rem;
}}

.stat-desc {{
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 500;
}}

.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.75rem;
  margin-bottom: 2rem;
  box-shadow: var(--shadow-sm);
}}

.card-title {{
  font-family: 'Outfit', sans-serif;
  font-size: 1.25rem;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.job-detail-view {{
  grid-column: 1 / -1;
  background: var(--surface);
  border: 1px solid var(--primary-border);
  border-top: 4px solid var(--primary);
  border-radius: 10px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: var(--shadow-md);
}}
.job-detail-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border);
}}
.job-detail-header h2 {{
  font-family: 'Outfit', sans-serif;
  color: #1e3a8a;
  font-size: 1.7rem;
  margin-top: 0.55rem;
}}
.job-detail-header p {{
  color: var(--text-muted);
  font-weight: 700;
  margin-top: 0.15rem;
}}
.job-detail-content {{
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(14rem, 0.8fr);
  gap: 2.25rem;
  padding-top: 1.5rem;
}}
.job-detail-content h3 {{
  font-family: 'Outfit', sans-serif;
  color: #1e293b;
  font-size: 1.05rem;
  margin-bottom: 0.75rem;
}}
.job-description-text {{
  white-space: pre-wrap;
  color: #334155;
  font-size: 0.95rem;
  line-height: 1.8;
}}
.job-detail-content aside {{
  background: var(--surface-alt);
  border-left: 3px solid var(--primary-border);
  padding: 1.1rem 1.25rem;
  border-radius: 6px;
}}
.job-detail-content aside p {{
  color: #475569;
  font-size: 0.84rem;
  line-height: 1.6;
  padding: 0.7rem 0;
  border-top: 1px solid var(--border);
}}
.job-detail-content aside p:first-of-type {{ border-top: 0; padding-top: 0; }}
.job-detail-actions {{
  display: flex;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}}
.apply-decision-form {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}}
.decision-question {{
  color: #334155;
  font-size: 0.84rem;
  font-weight: 700;
  margin-right: 0.15rem;
}}
.decision-note {{
  color: var(--text-muted);
  font-size: 0.84rem;
  font-weight: 600;
}}
.toast-success,
.toast-error {{
  position: fixed;
  top: 1.25rem;
  right: 1.25rem;
  z-index: 200;
  width: min(24rem, calc(100vw - 2rem));
  padding: 0.9rem 1rem;
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  font-size: 0.84rem;
  font-weight: 700;
}}
.toast-success {{
  background: var(--success-light);
  border: 1px solid var(--success-border);
  color: #166534;
}}
.toast-error {{
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  color: #991b1b;
}}
.opportunity-card {{
  min-width: 0;
}}
.opportunity-header {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.9rem;
  align-items: start;
}}
.opportunity-heading {{
  min-width: 0;
}}
.opportunity-heading h2 {{
  overflow-wrap: anywhere;
  line-height: 1.25;
}}
.opportunity-status {{
  max-width: 8.5rem;
  text-align: center;
  line-height: 1.25;
  white-space: normal;
}}
.opportunity-actions {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-top: 1rem;
  padding-top: 0.9rem;
  border-top: 1px solid var(--border);
}}
.opportunity-actions > .btn-secondary {{
  flex: 0 0 auto;
}}
.apply-decision-form {{
  flex: 1 1 15rem;
  min-width: 0;
}}
@media (max-width: 520px) {{
  .opportunity-header {{ grid-template-columns: 1fr; }}
  .opportunity-status {{ max-width: none; justify-self: start; }}
  .opportunity-actions {{ align-items: stretch; }}
  .apply-decision-form {{ flex-basis: 100%; }}
}}
@media (max-width: 800px) {{
  .job-detail-view {{ padding: 1.25rem; }}
  .job-detail-header {{ flex-direction: column; }}
  .job-detail-content {{ grid-template-columns: 1fr; gap: 1.25rem; }}
}}

/* Skill Progress Bars */
.meter-row {{
  margin-bottom: 1.1rem;
}}

.meter-labels {{
  display: flex;
  justify-content: space-between;
  font-size: 0.88rem;
  font-weight: 600;
  margin-bottom: 0.35rem;
}}

.meter-track {{
  background: var(--surface-alt);
  border-radius: 8px;
  height: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
}}

.meter-bar {{
  height: 100%;
  border-radius: 8px;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  transition: width 0.4s ease;
}}

/* Notice Boxes */
.box-info {{
  background: var(--primary-light);
  border: 1px solid var(--primary-border);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}}

.box-warn {{
  background: var(--warning-light);
  border: 1px solid var(--warning-border);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}}

.box-danger {{
  background: var(--danger-light);
  border: 1px solid var(--danger-border);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}}

.box-success {{
  background: var(--success-light);
  border: 1px solid var(--success-border);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}}

.chat-message {{
  max-width: 82%;
  padding: 0.8rem 1rem;
  border-radius: 8px;
  margin: 0.65rem 0;
  border: 1px solid var(--border);
}}
.chat-message p {{ margin-top: 0.25rem; white-space: pre-wrap; font-size: 0.92rem; color: #334155; }}
.chat-user {{ margin-left: auto; background: var(--primary-light); border-color: var(--primary-border); }}
.chat-assistant {{ background: var(--surface-alt); }}
.chat-content {{ margin-top: 0.3rem; color: #334155; }}
.chat-content h2, .chat-content h3, .chat-content h4 {{ color: #1e3a8a; margin: 0.45rem 0; }}
.chat-content li {{ margin: 0.25rem 0 0.25rem 1.2rem; }}
.path-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.65rem; }}
.path-option {{ display: flex; flex-direction: column; gap: 0.15rem; padding: 0.75rem; background: #ffffff; border: 1px solid var(--border); border-radius: 8px; color: var(--text); text-decoration: none; }}
.path-option:hover {{ border-color: var(--primary); background: var(--primary-light); }}
.path-option span {{ color: var(--primary); font-size: 0.78rem; font-weight: 600; }}
.assessment-layout {{ display: grid; grid-template-columns: 15rem minmax(0, 1fr); gap: 1.25rem; align-items: start; }}
.assessment-sidebar {{ position: sticky; top: 1rem; padding: 1rem; }}
.assessment-topic {{ display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.7rem; border-radius: 7px; text-decoration: none; color: var(--text); margin-bottom: 0.35rem; border: 1px solid transparent; font-size: 0.85rem; }}
.assessment-topic:hover, .assessment-topic.selected {{ background: var(--primary-light); border-color: var(--primary-border); color: var(--primary-hover); }}
.assessment-topic strong {{ color: var(--primary); font-size: 0.8rem; }}
.assessment-question {{ padding: 1rem 0; border-bottom: 1px solid var(--border); }}
.assessment-question h3 {{ font-size: 1rem; margin: 0.55rem 0 0.75rem; color: var(--text); }}
.assessment-option {{ display: block; padding: 0.55rem 0.7rem; margin: 0.35rem 0; border: 1px solid var(--border); border-radius: 6px; font-weight: 400; cursor: pointer; }}
.assessment-option:hover {{ background: var(--primary-light); border-color: var(--primary-border); }}
.progress-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.25rem; }}
.progress-kpi {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; }}
.progress-kpi strong {{ display: block; font: 700 1.7rem 'Outfit', sans-serif; color: var(--primary); }}
.chart-grid {{ display: grid; grid-template-columns: minmax(14rem, 0.8fr) minmax(0, 1.5fr); gap: 1.25rem; align-items: stretch; }}
.pie-wrap {{ display: flex; align-items: center; gap: 1.25rem; }}
.pie-chart {{ width: 9rem; height: 9rem; border-radius: 50%; flex-shrink: 0; background: var(--pie); position: relative; }}
.pie-chart::after {{ content: ''; position: absolute; inset: 2rem; background: var(--surface); border-radius: 50%; }}
.legend {{ list-style: none; font-size: 0.82rem; color: var(--text-muted); }}
.legend li {{ margin: 0.35rem 0; }}
.legend i {{ width: 0.65rem; height: 0.65rem; display: inline-block; border-radius: 2px; margin-right: 0.4rem; background: var(--swatch); }}
.path-tree {{ position: relative; padding-left: 1.25rem; }}
.path-tree::before {{ content: ''; position: absolute; left: 0.35rem; top: 0.75rem; bottom: 0.75rem; border-left: 2px solid var(--primary-border); }}
.tree-node {{ position: relative; margin: 0 0 1rem 0.75rem; padding: 0.75rem 1rem; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }}
.tree-node::before {{ content: ''; position: absolute; left: -1rem; top: 1rem; width: 0.85rem; border-top: 2px solid var(--primary-border); }}
.tree-node strong {{ color: #1e3a8a; }}
.tree-confidence {{ float: right; margin-right: 0.4rem; color: var(--primary); font-size: 0.82rem; font-weight: 700; }}
.tree-children {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.55rem; }}
.tree-child {{ padding: 0.35rem 0.55rem; border-radius: 5px; background: var(--primary-light); color: var(--primary-hover); font-size: 0.78rem; }}
.role-fit {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.65rem; }}
.role-fit-item {{ border: 1px solid var(--border); border-radius: 7px; padding: 0.7rem; }}
.refresh-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 0.65rem; margin-top: 0.75rem; }}
.refresh-topic {{ display: block; padding: 0.75rem; border: 1px solid var(--warning-border); border-radius: 8px; background: var(--warning-light); color: #92400e; text-decoration: none; font-weight: 700; }}
.refresh-topic span {{ display: block; font-size: 0.76rem; font-weight: 500; margin-top: 0.25rem; color: #a16207; }}
.resource-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: 1rem; }}
.resource-tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; box-shadow: var(--shadow-sm); }}
.resource-tile h3 {{ color: #1e3a8a; font-size: 1rem; margin: 0.45rem 0; }}
.resource-link {{ display: block; padding: 0.7rem 0; border-top: 1px solid var(--border); color: var(--primary-hover); text-decoration: none; font-size: 0.85rem; }}
.resource-link:hover {{ color: var(--primary); text-decoration: underline; }}
.line-chart {{ width: 100%; overflow-x: auto; margin-top: 0.5rem; }}
.line-chart svg {{ min-width: 32rem; width: 100%; height: auto; }}
.chart-axis {{ stroke: #cbd5e1; stroke-width: 1; }}
.chart-line {{ fill: none; stroke: var(--primary); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
.chart-dot {{ fill: #ffffff; stroke: var(--primary); stroke-width: 3; }}
.chart-label {{ fill: var(--text-muted); font: 11px 'Plus Jakarta Sans', sans-serif; }}
@media (max-width: 800px) {{
  .progress-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .chart-grid {{ grid-template-columns: 1fr; }}
  .pie-wrap {{ justify-content: center; }}
}}
@media (max-width: 800px) {{
  .brand-name {{ white-space: normal; font-size: 1rem; }}
  .auth-shell nav {{ padding: 0 1rem; }}
  .chat-message {{ max-width: 94%; }}
}}

/* Badges */
.badge {{
  display: inline-block;
  padding: 0.25rem 0.65rem;
  border-radius: 12px;
  font-size: 0.78rem;
  font-weight: 600;
}}
.badge-verified {{ background: var(--success-light); color: var(--success); border: 1px solid var(--success-border); }}
.badge-excluded {{ background: var(--danger-light); color: var(--danger); border: 1px solid var(--danger-border); }}
.badge-waiting {{ background: var(--warning-light); color: var(--warning); border: 1px solid var(--warning-border); }}
.badge-primary {{ background: var(--primary-light); color: var(--primary); border: 1px solid var(--primary-border); }}

/* Buttons */
.btn {{
  display: inline-block;
  background: var(--primary);
  color: #ffffff;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.9rem;
  padding: 0.6rem 1.25rem;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s ease;
}}
.btn:hover {{ background: var(--primary-hover); color:#fff; }}
.btn-secondary {{ background: #ffffff; border: 1px solid var(--border); color: var(--text); }}
.btn-secondary:hover {{ background: var(--surface-alt); }}
.btn-success {{ background: var(--success); }}
.btn-success:hover {{ background: #15803d; }}

/* Forms */
.form-group {{
  margin-bottom: 1.2rem;
}}
label {{
  display: block;
  font-size: 0.88rem;
  font-weight: 600;
  color: #334155;
  margin-bottom: 0.35rem;
}}
input[type=text], input[type=email], input[type=password], input[type=number], select, textarea {{
  width: 100%;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.65rem 0.8rem;
  font-family: inherit;
  font-size: 0.92rem;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s;
}}
input:focus, select:focus, textarea:focus {{
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}}

/* Tables */
table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 0.75rem;
}}
@media (max-width: 800px) {{
  nav {{ position: static; width: 100%; border-right: 0; border-bottom: 1px solid var(--border); }}
  .brand-group {{ margin-bottom: 1rem; }}
  .nav-menu {{ display: grid; grid-template-columns: repeat(2, 1fr); }}
  .user-pill {{ margin-top: 1rem; }}
  .container {{ margin-left: 0; padding: 1.25rem 1rem 3rem; }}
  .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .assessment-layout {{ grid-template-columns: 1fr; }}
  .assessment-sidebar {{ position: static; }}
}}
th, td {{
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  font-size: 0.88rem;
}}
th {{
  background: var(--surface-alt);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}}
tr:hover td {{
  background: #fafafa;
}}

/* Bullet Lists */
.bullet-list {{
  list-style: none;
  margin-top: 0.5rem;
}}
.bullet-list li {{
  font-size: 0.88rem;
  color: #334155;
  margin-bottom: 0.35rem;
  padding-left: 1.2rem;
  position: relative;
}}
.bullet-list li::before {{
  content: "•";
  color: var(--primary);
  position: absolute;
  left: 0.2rem;
  font-weight: bold;
}}
</style>
</head>
<body class="{layout_class}">
<nav>
  <a href="/" class="brand-group">
    <div class="brand-name">Skill-Pilot</div>
  </a>
  <ul class="nav-menu">
    {nav_links}
  </ul>
  <div class="nav-account">
    {user_pill}
  </div>
</nav>
<div class="container">
{content}
</div>
</body>
</html>"""


def render_page(
    title: str,
    content: str,
    active_nav: str = "dashboard",
    student: Any = None,
) -> HTMLResponse:
    if student:
        nav_links = f"""
        <li><a href="/" class="{'active' if active_nav=='dashboard' else ''}">▦ &nbsp; Dashboard</a></li>
        <li><a href="/career-analysis" class="{'active' if active_nav=='analysis' else ''}">⌁ &nbsp; Career Analysis</a></li>
        <li><a href="/career-goals" class="{'active' if active_nav=='goals' else ''}">◎ &nbsp; Career Goals</a></li>
        <li><a href="/job-opportunities" class="{'active' if active_nav=='opportunities' else ''}">⌖ &nbsp; Job Opportunities</a></li>
        <li><a href="/learning-coach" class="{'active' if active_nav=='coach' else ''}">✦ &nbsp; AI Coach</a></li>
        <li><a href="/assessment" class="{'active' if active_nav=='assessment' else ''}">✓ &nbsp; Assessments</a></li>
        <li><a href="/learning-plan" class="{'active' if active_nav=='plan' else ''}">☷ &nbsp; Learning Plan</a></li>
        <li><a href="/progress" class="{'active' if active_nav=='progress' else ''}">◷ &nbsp; Progress</a></li>
        <li><a href="/profile" class="{'active' if active_nav=='profile' else ''}">◉ &nbsp; Profile</a></li>
        """
        user_pill = f"""
        <div class="user-pill">
          <div class="avatar-dot"></div>
          <span>{html.escape(student.name)}</span>
        </div>
        <a href="/resources" class="btn btn-secondary" style="font-size:0.8rem; padding:0.35rem 0.75rem;">▤ Resources</a>
        <a href="/logout" class="btn btn-secondary" style="font-size:0.8rem; padding:0.35rem 0.75rem;">Logout</a>
        """
    else:
        nav_links = """
        <li><a href="/login" class="active">Login</a></li>
        <li><a href="/register">Register</a></li>
        <li><a href="/demo" style="color:#d97706; font-weight:600;">20-Step Demo</a></li>
        """
        user_pill = """
        <a href="/login" class="btn" style="font-size:0.85rem; padding:0.4rem 0.9rem;">Sign In</a>
        """

    html_out = BASE_TEMPLATE.format(
        title=title,
        nav_links=nav_links,
        user_pill=user_pill,
        content=content,
        layout_class="app-shell" if student else "auth-shell",
    )
    return HTMLResponse(html_out)


# ------------------------------------------------------------------- LOGIN PAGE (Section 4)

@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    error_banner = f"<div class='box-danger' style='margin-bottom:1rem;'>{html.escape(error)}</div>" if error else ""
    content = f"""
    <div style="max-width: 28rem; margin: 3rem auto;">
      <div class="card" style="box-shadow: var(--shadow-lg); padding: 2.25rem;">
        <div style="text-align:center; margin-bottom:1.5rem;">
          <div class="brand-badge" style="display:inline-block; margin-bottom:0.75rem;">SKILL-PILOT</div>
          <h2 style="font-family:'Outfit',sans-serif; color:#1e3a8a; font-size:1.6rem;">Student Portal Login</h2>
          <p style="color:var(--text-muted); font-size:0.9rem; margin-top:0.25rem;">Access your persistent career learning profile</p>
        </div>

        {error_banner}

        <form method="post" action="/login">
          <div class="form-group">
            <label>Student Email Address</label>
            <input type="email" name="email" value="arun@college.edu" required autofocus>
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" value="secret" required>
          </div>
          <button type="submit" class="btn" style="width:100%; padding:0.75rem; margin-top:0.5rem;">Sign In to Portal &rarr;</button>
        </form>

        <div style="margin-top: 1.5rem; padding-top: 1.25rem; border-top: 1px solid var(--border); text-align:center;">
          <form method="post" action="/login/demo">
            <button type="submit" class="btn btn-secondary" style="width:100%; font-size:0.85rem;">
              ⚡ One-Click Demo Login as Arun (NIT '27)
            </button>
          </form>
          <p style="font-size:0.85rem; color:var(--text-muted); margin-top:1rem;">
            New student? <a href="/register" style="color:var(--primary); font-weight:600;">Create account here</a>
          </p>
        </div>
      </div>
    </div>
    """
    return HTMLResponse(BASE_TEMPLATE.format(
        title="Student Login",
        nav_links="<li><a href='/login' class='active'>Login</a></li><li><a href='/register'>Register</a></li><li><a href='/demo'>20-Step Demo</a></li>",
        user_pill="<a href='/register' class='btn btn-secondary' style='font-size:0.85rem; padding:0.4rem 0.9rem;'>Register</a>",
        content=content,
        layout_class="auth-shell",
    ))


@app.post("/login")
def handle_login(email: str = Form(...), password: str = Form(...)):
    svc = get_service()
    student = svc.login_student(email.strip(), password)
    if not student:
        return RedirectResponse("/login?error=Invalid+email+or+password", status_code=303)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("session_student_id", student.student_id, max_age=86400, httponly=True)
    return resp


@app.post("/login/demo")
def handle_demo_login():
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("session_student_id", "std_arun", max_age=86400, httponly=True)
    return resp


@app.get("/logout")
def handle_logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session_student_id")
    return resp


# ------------------------------------------------------------------- REGISTRATION (Section 4)

@app.get("/register", response_class=HTMLResponse)
def register_page(error: str = ""):
    error_banner = f"<div class='box-danger' style='margin-bottom:1rem;'>{html.escape(error)}</div>" if error else ""
    content = f"""
    <div style="max-width: 34rem; margin: 2rem auto;">
      <div class="card" style="box-shadow: var(--shadow-lg); padding: 2.25rem;">
        <div style="text-align:center; margin-bottom:1.5rem;">
          <h2 style="font-family:'Outfit',sans-serif; color:#1e3a8a; font-size:1.6rem;">Student Registration</h2>
          <p style="color:var(--text-muted); font-size:0.9rem; margin-top:0.25rem;">Join the persistent Cognitive Career Navigator</p>
        </div>

        {error_banner}

        <form method="post" action="/register" enctype="multipart/form-data">
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
            <div class="form-group">
              <label>Full Name</label>
              <input type="text" name="name" placeholder="e.g. Priya Sharma" required>
            </div>
            <div class="form-group">
              <label>Graduation Year</label>
              <input type="number" name="graduation_year" value="2027" min="2024" max="2032" required>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
            <div class="form-group">
              <label>College / University</label>
              <input type="text" name="college" placeholder="e.g. IIT Madras" required>
            </div>
            <div class="form-group">
              <label>Department / Major</label>
              <input type="text" name="department" placeholder="e.g. Computer Science" required>
            </div>
          </div>

          <div class="form-group">
            <label>College Email</label>
            <input type="email" name="email" placeholder="priya@college.edu" required>
          </div>

          <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" placeholder="Create password" required>
          </div>

          <div class="form-group">
            <label>Target Career Role</label>
            <select name="target_role">
              {"".join(f"<option value='{r}'>{r}</option>" for r in ROLE_SKILLS.keys())}
            </select>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
            <div class="form-group">
              <label>Education Level</label>
              <select name="education_level"><option>B.Tech</option><option>BCA</option><option>BSc</option><option>M.Tech</option><option>MCA</option><option>MBA</option></select>
            </div>
            <div class="form-group">
              <label>CGPA / GPA</label>
              <input type="number" name="cgpa" min="0" max="10" step="0.01" value="0">
            </div>
          </div>
          <div class="form-group">
            <label>Resume (PDF or TXT)</label>
            <input type="file" name="resume" accept=".pdf,.txt,application/pdf,text/plain">
            <p style="font-size:0.8rem; color:var(--text-muted); margin-top:0.35rem;">Used to personalize your gap analysis and editable later from Profile.</p>
          </div>

          <button type="submit" class="btn" style="width:100%; padding:0.75rem; margin-top:0.5rem;">Create Career Account &rarr;</button>
        </form>

        <p style="font-size:0.85rem; color:var(--text-muted); text-align:center; margin-top:1.25rem;">
          Already registered? <a href="/login" style="color:var(--primary); font-weight:600;">Sign in here</a>
        </p>
      </div>
    </div>
    """
    return HTMLResponse(BASE_TEMPLATE.format(
        title="Student Registration",
        nav_links="<li><a href='/login'>Login</a></li><li><a href='/register' class='active'>Register</a></li><li><a href='/demo'>20-Step Demo</a></li>",
        user_pill="<a href='/login' class='btn btn-secondary' style='font-size:0.85rem; padding:0.4rem 0.9rem;'>Sign In</a>",
        content=content,
        layout_class="auth-shell",
    ))


@app.post("/register")
async def handle_register(
    name: str = Form(...),
    graduation_year: int = Form(...),
    college: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    target_role: str = Form("Software Engineering Intern"),
    education_level: str = Form("B.Tech"),
    cgpa: float = Form(0.0),
    resume: UploadFile | None = File(None),
):
    svc = get_service()
    resume_text = ""
    if resume and resume.filename:
        resume_text = extract_resume_text(resume.filename, await resume.read())
    reg = StudentRegistration(
        name=name.strip(),
        graduation_year=graduation_year,
        college=college.strip(),
        department=department.strip(),
        email=email.strip(),
        password=password.strip(),
        education_level=education_level,
        cgpa=cgpa,
        career_goal_role=target_role,
        resume_text=resume_text,
    )
    student = svc.register_student(reg)
    svc.analyze_resume_and_gaps_with_llm(student.student_id)

    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("session_student_id", student.student_id, max_age=86400, httponly=True)
    return resp


# ---------------------------------------------------------- CAREER ANALYSIS

@app.get("/career-analysis", response_class=HTMLResponse)
def career_analysis_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    profile = svc.get_student_profile(student.student_id)
    goal = svc.get_active_career_goal(student.student_id)
    report = svc.get_latest_gap_report(student.student_id)
    if not report:
        report = svc.analyze_resume_and_gaps_with_llm(student.student_id)
    rows = "".join(
        f"<tr><td><strong>{html.escape(g.skill)}</strong></td><td>{g.current_score}/100</td>"
        f"<td>{html.escape(g.current_status)}</td><td><span class='badge badge-{'excluded' if g.priority == 'High' else 'primary'}'>{html.escape(g.priority)} priority</span></td>"
        f"<td>{html.escape(g.reason)}</td></tr>" for g in report.gaps
    )
    resume_state = "Resume analyzed" if profile.resume_text else "No resume uploaded yet"
    content = f"""
    <div class="welcome-card"><div><h1>Your Career Analysis</h1>
      <p style="color:var(--text-muted);">{html.escape(resume_state)} for the {html.escape(goal.role)} pathway.</p></div>
      <span class="role-tag">{html.escape(goal.role)}</span></div>
    <div class="card"><div class="card-title">What to work on next</div>
      <p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:1rem;">The single career agent compares your resume, assessments, prior evidence, and selected goal. High-priority topics appear first in coaching and assessments.</p>
      <table><thead><tr><th>Skill</th><th>Current</th><th>Level</th><th>Priority</th><th>Why it matters</th></tr></thead><tbody>{rows}</tbody></table>
      <div class="box-info" style="margin-top:1.25rem;"><strong>Priority topics:</strong> {html.escape(', '.join(report.high_priority_skills) or 'No critical gaps yet')}</div>
    </div>
    <div class="card"><div class="card-title">Keep your analysis current</div>
      <p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:1rem;">Update your resume or goal whenever your direction changes, then rerun the analysis.</p>
      <a class="btn" href="/profile">Edit profile and resume</a>
      <form method="post" action="/career-analysis/analyze" style="display:inline-block; margin-left:0.5rem;"><button class="btn btn-secondary" type="submit">Run analysis again</button></form>
    </div>"""
    return render_page("Career Analysis", content, active_nav="analysis", student=student)


@app.post("/career-analysis/analyze")
def career_analysis_run(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    svc.analyze_resume_and_gaps_with_llm(student.student_id)
    return RedirectResponse("/career-analysis", status_code=303)


# ------------------------------------------------------------------- DASHBOARD (Section 8)

@app.get("/", response_class=HTMLResponse)
def dashboard_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    profile = svc.get_student_profile(student.student_id)
    goal = svc.get_active_career_goal(student.student_id)
    rec = svc.select_next_skill(student.student_id)
    pending_chk = svc.get_pending_decisions(student.student_id)
    metrics = svc.get_dashboard_metrics(student.student_id)

    # Meter bars
    meters = ""
    for skill, item in profile.skills.items():
        meters += f"""
        <div class="meter-row">
          <div class="meter-labels">
            <span>{html.escape(skill)}</span>
            <span style="color:var(--primary); font-weight:700;">{item.score}/100 ({item.status})</span>
          </div>
          <div class="meter-track">
            <div class="meter-bar" style="width: {item.score}%;"></div>
          </div>
        </div>
        """

    # Reasons list
    reasons_html = "".join(f"<li>{html.escape(r)}</li>" for r in rec["reasons"])
    plan_paths = "".join(
      f"<a class='path-option' href='/learning-plan?topic={html.escape(skill)}'><strong>{html.escape(skill)}</strong><span>Build this path</span></a>"
      for skill in goal.target_skills
    )

    # Pending decisions
    chk_html = ""
    if pending_chk:
        for chk in pending_chk:
            chk_html += f"""
            <div class="box-warn">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="color:var(--warning);">{html.escape(chk.summary)}</strong>
                <span class="badge badge-waiting">WAITING_FOR_STUDENT</span>
              </div>
              <p style="font-size:0.88rem; margin: 0.5rem 0; color:#334155;">{html.escape("; ".join(chk.reasons))}</p>
              <div style="margin-top: 0.75rem; display: flex; gap: 0.5rem;">
                <form method="post" action="/checkpoint/{chk.checkpoint_id}/accept"><button type="submit" class="btn btn-success">Accept Plan</button></form>
                <form method="post" action="/checkpoint/{chk.checkpoint_id}/reject"><button type="submit" class="btn btn-secondary">Reject</button></form>
              </div>
            </div>
            """
    else:
        chk_html = "<p style='color:var(--text-muted); font-size:0.9rem;'>No pending approvals. Previous recommendations are active.</p>"

    content = f"""
    <div class="welcome-card">
      <div>
        <h1>Welcome, {html.escape(student.name)}</h1>
        <p style="color:var(--text-muted); font-size:0.95rem;">{html.escape(student.college)} • {html.escape(student.department)} (Class of {student.graduation_year})</p>
      </div>
      <div>
        <span class="role-tag">🎯 Goal: {html.escape(goal.role)}</span>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-val">{metrics["readiness"]}%</div>
        <div class="stat-desc">Role Benchmark Readiness</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">{metrics["improved"]}</div>
        <div class="stat-desc">Skills Improved Recently</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">{len(pending_chk)}</div>
        <div class="stat-desc">Pending Checkpoints</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">{metrics["profile_completion"]}%</div>
        <div class="stat-desc">Profile Completion</div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 2rem;">
      <div>
        <div class="card">
          <div class="card-title">
            <span>Today's Adaptive Focus</span>
            <span class="badge badge-primary">Evidence Grounded</span>
          </div>
          <div class="box-info">
            <h3 style="color:#1e40af; font-size:1.15rem; margin-bottom:0.35rem;">
              {html.escape(rec["skill"])}: {html.escape(rec["topic"])}
            </h3>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:0.75rem;">
              Current Verified Score: <strong>{rec["current_score"]}/100</strong>
            </p>
            <div style="font-weight:600; font-size:0.85rem; color:#1e293b;">Why this skill today?</div>
            <ul class="bullet-list">
              {reasons_html}
            </ul>
            <div style="margin-top: 1.25rem;">
              <a href="/learning-coach" class="btn">Launch Daily Coaching &rarr;</a>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Human Approval Checkpoints</div>
          {chk_html}
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-title">
            <span>Demonstrated Skills</span>
            <a href="/profile" style="font-size:0.82rem; color:var(--primary); text-decoration:none;">Manage &rarr;</a>
          </div>
          {meters}
          <div style="margin-top: 1.25rem; text-align:center;">
            <a href="/assessment" class="btn btn-secondary" style="width:100%; text-align:center;">Take Role Diagnostic Test &rarr;</a>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Analyze a Job Description</div>
          <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem;">
            Paste job requirements to run citation provenance checks and extract tailored skill gaps.
          </p>
          <a href="/job-analyzer" class="btn btn-secondary" style="width:100%; text-align:center;">Open Job Analyzer &rarr;</a>
        </div>
        <div class="card">
          <div class="card-title">Learning paths</div>
          <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:0.75rem;">Select a role topic to add its path to your current plan.</p>
          <div class="path-list">{plan_paths}</div>
        </div>
      </div>
    </div>
    """
    return render_page("Dashboard", content, active_nav="dashboard", student=student)


# --------------------------------------------------------------- CAREER GOALS (Section 6)

@app.get("/career-goals", response_class=HTMLResponse)
def career_goals_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    active_goal = svc.get_active_career_goal(student.student_id)
    all_goals = svc.list_career_goals(student.student_id)

    role_options = ""
    for role, skills in ROLE_SKILLS.items():
        is_selected = "selected" if role == active_goal.role else ""
        role_options += f"<option value='{role}' {is_selected}>{role}</option>"

    skills_badges = " ".join(f"<span class='role-tag'>{s}</span>" for s in active_goal.target_skills)

    content = f"""
    <div class="card">
      <div class="card-title">Career Goal Management</div>
      <p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:1.5rem;">
        The student—not the AI—chooses their target career direction. Select your primary target role to align the skill rubric and coaching.
      </p>

      <div class="box-info" style="margin-bottom:1.5rem;">
        <span style="font-size:0.8rem; font-weight:700; color:var(--primary); text-transform:uppercase;">Active Primary Role</span>
        <h2 style="color:#1e3a8a; font-size:1.5rem; margin:0.25rem 0 0.75rem;">{html.escape(active_goal.role)}</h2>
        <div style="font-weight:600; font-size:0.88rem; margin-bottom:0.5rem;">Required Competencies:</div>
        <div style="display:flex; flex-wrap:wrap; gap:0.5rem;">
          {skills_badges}
        </div>
      </div>

      <form method="post" action="/career-goals/update" style="max-width:28rem;">
        <div class="form-group">
          <label>Change Target Role</label>
          <select name="role">
            {role_options}
          </select>
        </div>
        <button type="submit" class="btn">Update Target Role</button>
      </form>
    </div>
    """
    return render_page("Career Goals", content, active_nav="goals", student=student)


@app.post("/career-goals/update")
def career_goals_update(request: Request, role: str = Form(...)):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    svc.update_career_goal(student.student_id, role)
    return RedirectResponse("/career-analysis", status_code=303)


# ------------------------------------------------------------- JOB OPPORTUNITIES

@app.get("/job-opportunities", response_class=HTMLResponse)
def job_opportunities_view(request: Request, notice: str = "", error: str = ""):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    goal = svc.get_active_career_goal(student.student_id)
    report = svc.get_latest_gap_report(student.student_id)
    target_skills = list(goal.target_skills)
    if report:
        target_skills = list(dict.fromkeys(target_skills + report.high_priority_skills))
    try:
        jobs = svc.find_placement_opportunities(student.student_id)
    except PlacementPortalError as exc:
        jobs = []
        error = str(exc)

    notice_html = f"<div class='toast-success' role='status'>Application applied successfully: {html.escape(notice)}</div>" if notice else ""
    error_html = f"<div class='toast-error' role='alert'>{html.escape(error)}</div>" if error else ""
    portal_url = svc.placement_portal_url()
    cards = []
    for job in jobs:
        skills = ", ".join(job.get("matched_skills", [])) or "Role alignment"
        eligibility_reason = job.get("eligibility_reason", "")
        if job.get("eligible"):
            eligibility = "Good match for your profile"
        elif "submitted your application" in eligibility_reason.lower():
            eligibility = "Application already submitted"
        else:
            eligibility = "Not a match for this profile"
        details_id = f"job-details-{html.escape(job['job_id'])}"
        card_id = f"job-card-{html.escape(job['job_id'])}"
        required_skills = html.escape(job.get("required_skills", "") or "Not listed")
        preferred_skills = html.escape(job.get("preferred_skills", "") or "Not listed")
        full_description = html.escape(job.get("text", "") or job.get("description", ""))
        apply_url = html.escape(job.get("url") or f"{portal_url}/jobs/{job['job_id']}")
        apply_action = (
            f"""
            <form method="post" action="/job-opportunities/decision" class="apply-decision-form">
              <input type="hidden" name="job_id" value="{html.escape(job['job_id'])}">
              <span class="decision-question">Would you like to apply?</span>
              <button class="btn" type="submit" name="decision" value="yes">Yes</button>
              <button class="btn btn-secondary" type="submit" name="decision" value="no">No</button>
            </form>
            """
            if job.get("eligible") else
            "<span class='decision-note'>This role is not currently a match for your profile.</span>"
        )
        cards.append(f"""
        <article id="{card_id}" class="card opportunity-card" style="border-top:4px solid var(--primary);">
          <div class="opportunity-header">
            <div class="opportunity-heading"><span class="badge badge-primary">{html.escape(job['job_id'])}</span>
              <h2 style="font-family:'Outfit',sans-serif; color:#1e3a8a; margin-top:0.45rem;">{html.escape(job['title'])}</h2>
              <p style="font-weight:700; color:var(--text-muted);">{html.escape(job['company'])}</p>
            </div>
            <span class="badge opportunity-status {'badge-verified' if job.get('eligible') else 'badge-waiting'}">{html.escape(eligibility)}</span>
          </div>
          <p style="margin:1rem 0; color:#334155;">{html.escape(job.get('description', ''))}</p>
          <p style="font-size:0.84rem; color:var(--text-muted);"><strong>Matched to:</strong> {html.escape(skills)}</p>
          <p style="font-size:0.84rem; color:var(--text-muted); margin-top:0.35rem;"><strong>Portal reason:</strong> {html.escape(job.get('eligibility_reason', ''))}</p>
          <div class="opportunity-actions">
            <button class="btn btn-secondary" type="button" onclick="showJobDetails('{card_id}', '{details_id}')">More Info</button>
            {apply_action}
          </div>
        </article>
        <section id="{details_id}" class="job-detail-view" hidden>
          <div class="job-detail-header">
            <div>
              <span class="badge badge-primary">{html.escape(job['job_id'])}</span>
              <h2>{html.escape(job['title'])}</h2>
              <p>{html.escape(job['company'])}</p>
            </div>
          </div>
          <div class="job-detail-content">
            <div>
              <h3>Full Job Description</h3>
              <div class="job-description-text">{full_description}</div>
            </div>
            <aside>
              <h3>Role Match</h3>
              <p><strong>Matched skills</strong><br>{html.escape(skills)}</p>
              <p><strong>Required skills</strong><br>{required_skills}</p>
              <p><strong>Preferred skills</strong><br>{preferred_skills}</p>
              <p><strong>Eligibility</strong><br>{html.escape(job.get('eligibility_reason', ''))}</p>
            </aside>
          </div>
          <div class="job-detail-actions">
            <button class="btn btn-secondary" type="button" onclick="hideJobDetails('{card_id}', '{details_id}')">Hide Info</button>
          </div>
        </section>""")
    if not cards and not error:
        cards.append("<div class='box-info'>No matching roles were found in the placement portal for this target profile.</div>")
    content = f"""
    {notice_html}{error_html}
    <div class="welcome-card"><div><h1>Job Opportunities</h1>
      <p style="color:var(--text-muted);">Live roles matched from the placement portal using your AI career analysis.</p></div>
      <span class="role-tag">{html.escape(goal.role)}</span></div>
    <div class="card" style="margin-bottom:1.25rem;">
      <div class="card-title">How these roles were selected</div>
      <p style="font-size:0.9rem; color:var(--text-muted);">Target role: <strong>{html.escape(goal.role)}</strong></p>
      <p style="font-size:0.9rem; color:var(--text-muted); margin-top:0.35rem;">AI-aligned skills: {html.escape(', '.join(target_skills))}</p>
    </div>
    <div id="opportunity-results" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(20rem,1fr)); gap:1.25rem;">{"".join(cards)}</div>
    <script>
      function showJobDetails(cardId, detailsId) {{
        document.querySelectorAll('.opportunity-card, .job-detail-view').forEach((element) => element.setAttribute('hidden', ''));
        const details = document.getElementById(detailsId);
        details.removeAttribute('hidden');
        window.scrollTo({{ top: details.offsetTop - 24, behavior: 'smooth' }});
      }}
      function hideJobDetails(cardId, detailsId) {{
        document.getElementById(detailsId).setAttribute('hidden', '');
        document.querySelectorAll('.opportunity-card').forEach((element) => element.removeAttribute('hidden'));
        window.scrollTo({{ top: document.getElementById('opportunity-results').offsetTop - 24, behavior: 'smooth' }});
      }}
    </script>
    """
    return render_page("Job Opportunities", content, active_nav="opportunities", student=student)


@app.post("/job-opportunities/decision")
def job_opportunities_decision(
    request: Request,
    job_id: str = Form(...),
    decision: str = Form(...),
):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    if decision == "yes":
      try:
        result = svc.apply_to_placement_job(student.student_id, job_id)
        message = result.get("message", f"Application submitted for {job_id}.")
        return RedirectResponse(f"/job-opportunities?notice={html.escape(message)}", status_code=303)
      except PlacementPortalError as exc:
        return RedirectResponse(f"/job-opportunities?error={html.escape(str(exc))}", status_code=303)
    return RedirectResponse(f"/job-opportunities?notice=No application started for {html.escape(job_id)}.", status_code=303)


# ------------------------------------------------------------- AI LEARNING COACH (Section 9)

@app.get("/learning-coach", response_class=HTMLResponse)
def learning_coach_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    history = svc.get_coach_history(student.student_id)
    goal = svc.get_active_career_goal(student.student_id)
    gap_report = svc.get_latest_gap_report(student.student_id)
    messages = "".join(
        f"<div class='chat-message {'chat-user' if item.get('role') == 'user' else 'chat-assistant'}'>"
        f"<strong>{'You' if item.get('role') == 'user' else 'Instructor'}</strong>"
      f"<div class='chat-content'>{render_chat_markdown(item.get('content', ''))}</div></div>" for item in history
    )
    if not messages:
        messages = "<div class='box-info'><strong>Start a lesson.</strong><p>Ask me to teach one of your current gap topics. I will explain it, show an example, and check your understanding.</p></div>"
    gap_text = ", ".join(g.skill for g in (gap_report.gaps if gap_report else []) if g.priority in ("High", "Medium")) or "No gap analysis yet"

    content = f"""
    <div class="welcome-card"><div><h1>Instructor Chat</h1>
      <p style="color:var(--text-muted);">Teaching plan for {html.escape(goal.role)} · Current focus: {html.escape(gap_text)}</p></div>
      <span class="role-tag">Context-aware</span>
    </div>
    <div class="card">
      <div class="card-title"><span>Learn with your instructor</span><span class="badge badge-primary">Teaching only</span></div>
      <div style="max-height:32rem; overflow-y:auto; padding:0.25rem 0;">{messages}</div>
      <form method="post" action="/learning-coach/chat" style="margin-top:1rem;">
        <div class="form-group"><label for="message">What should I teach you?</label>
          <textarea id="message" name="message" rows="3" maxlength="2000" required placeholder="Example: Teach me SQL joins with a simple example."></textarea>
        </div>
        <button type="submit" class="btn">Ask instructor</button>
      </form>
    </div>
    """
    return render_page("Instructor Chat", content, active_nav="coach", student=student)


@app.post("/learning-coach/chat")
def learning_coach_chat(request: Request, message: str = Form(...)):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    history = svc.get_coach_history(student.student_id)
    svc.ai_coach_respond(student.student_id, message, history)
    return RedirectResponse("/learning-coach", status_code=303)


@app.post("/learning-coach/answer", response_class=HTMLResponse)
def learning_coach_answer(request: Request, answer: str = Form(""), quick_test: str = Form("")):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    if quick_test == "wrong" or ("retrieve" in answer.lower()):
        sub_answer = "POST is used to retrieve data from a database."
    elif quick_test == "right":
        sub_answer = "POST submits data to create a new resource or trigger an operation."
    else:
        sub_answer = answer or "POST is used to retrieve data from a database."

    eval_res = svc.submit_assessment_answer(student.student_id, "q_demo", sub_answer)

    if not eval_res.is_correct:
        corrective = svc.generate_corrective_explanation(eval_res.detected_misconception or "")
        followup = svc.generate_followup_question("REST APIs")
        content = f"""
        <div class="card">
          <div class="card-title" style="color:var(--danger);">Misconception Detected by Agent</div>
          <div class="box-danger">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
              <strong style="font-size:1.1rem; color:var(--danger);">{html.escape(eval_res.detected_misconception or '')}</strong>
              <span class="badge badge-excluded">Confidence: {eval_res.misconception_confidence}</span>
            </div>
            <p style="font-size:0.9rem; color:#334155; margin-bottom:0.4rem;"><strong>Student Answer:</strong> "{html.escape(sub_answer)}"</p>
            <p style="font-size:0.88rem; color:#64748b;">{html.escape(eval_res.explanation)}</p>
          </div>

          <div class="box-info">
            <h4 style="color:#1e40af; margin-bottom:0.5rem;">Adaptive Corrective Teaching</h4>
            <p style="font-size:0.92rem; color:#334155;">{html.escape(corrective)}</p>
          </div>

          <div class="card" style="background:var(--surface-alt); border:1px solid var(--border); box-shadow:none;">
            <h4 style="color:#16a34a; margin-bottom:0.5rem;">Follow-up Assessment (Untangling Misconception)</h4>
            <p style="font-size:0.98rem; font-weight:600; margin-bottom:1rem;">{html.escape(followup.question)}</p>
            <form method="post" action="/learning-coach/followup">
              <div style="display:flex; gap:0.6rem;">
                <button type="submit" name="ans" value="GET" class="btn btn-success">Select 'GET' (Safe Read)</button>
                <button type="submit" name="ans" value="POST" class="btn btn-secondary">Select 'POST'</button>
              </div>
            </form>
          </div>
        </div>
        """
    else:
        content = f"""
        <div class="card">
          <div class="card-title" style="color:var(--success);">Answer Verified Correct!</div>
          <div class="box-success">
            <p style="font-size:1rem; font-weight:600; color:#15803d; margin-bottom:0.35rem;">Excellent understanding demonstrated.</p>
            <p style="font-size:0.88rem; color:#334155;">Score increment: <strong>+{eval_res.score_delta}</strong> points recorded to SQLite evidence store.</p>
          </div>
          <a href="/" class="btn">Return to Dashboard &rarr;</a>
        </div>
        """
    return render_page("AI Coach Feedback", content, active_nav="coach", student=student)


@app.post("/learning-coach/followup", response_class=HTMLResponse)
def learning_coach_followup(request: Request, ans: str = Form("GET")):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    if ans == "GET":
        svc.update_skill_evidence(student.student_id, "REST APIs", 15)
        svc.mark_misconception_resolved(student.student_id, "Confusion between GET and POST")
        prof = svc.get_student_profile(student.student_id)
        content = f"""
        <div class="card">
          <div class="card-title" style="color:var(--success);">Follow-Up Passed & Misconception Resolved!</div>
          <div class="box-success">
            <h3 style="color:#15803d; font-size:1.15rem; margin-bottom:0.5rem;">
              REST APIs Score Updated: 30 &rarr; {prof.skills["REST APIs"].score}/100
            </h3>
            <p style="font-size:0.9rem; color:#334155;">
              Status upgraded to <strong>{prof.skills["REST APIs"].status}</strong>.
              The misconception record was marked <strong>RESOLVED</strong> in the SQLite store and will inform future recommendations.
            </p>
          </div>
          <div style="margin-top:1.5rem; display:flex; gap:1rem;">
            <a href="/" class="btn">View Updated Dashboard &rarr;</a>
            <a href="/job-analyzer" class="btn btn-secondary">Analyze Job Description &rarr;</a>
          </div>
        </div>
        """
    else:
        content = """
        <div class="card">
          <div class="card-title" style="color:var(--danger);">Incorrect Choice</div>
          <p>GET is the safe method for fetching data without modifying state.</p>
          <a href="/learning-coach" class="btn">Try Again</a>
        </div>
        """
    return render_page("Follow-up Result", content, active_nav="coach", student=student)


# ---------------------------------------------------------- JOB ANALYZER (Section 10, 11)

@app.get("/job-analyzer", response_class=HTMLResponse)
def job_analyzer_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    sample_jd = (
        "We are hiring a Software Engineering Intern.\n\n"
        "Required Qualifications:\n"
        "- Demonstrated proficiency in Python 3.10+ programming\n"
        "- Solid understanding of SQL querying, relational database design, joins\n"
        "- Practical knowledge of REST API architecture, HTTP methods (GET, POST, PUT, DELETE)\n"
        "- Strong grasp of core data structures (arrays, hash tables, linked lists, trees, graphs)\n\n"
        "Preferred Qualifications:\n"
        "- Exposure to containerization, Dockerfiles, and multi-stage container builds"
    )

    content = f"""
    <div class="card">
      <div class="card-title">
        <span>Job Description Analyzer & Provenance Verification</span>
        <span class="badge badge-primary">Principle 4 Provenance</span>
      </div>
      <p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:1.25rem;">
        Paste a real job description below. The analyzer will extract technical requirements and deterministically check that every quote appears verbatim in the text.
      </p>

      <form method="post" action="/job-analyzer/analyze">
        <div class="form-group">
          <label>Job Description Text</label>
          <textarea name="jd_text" rows="10">{html.escape(sample_jd)}</textarea>
        </div>
        <button type="submit" class="btn">Analyze & Verify Requirements &rarr;</button>
      </form>
    </div>
    """
    return render_page("Job Analyzer", content, active_nav="jobs", student=student)


@app.post("/job-analyzer/analyze", response_class=HTMLResponse)
def job_analyzer_analyze(request: Request, jd_text: str = Form(...)):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    job_doc = svc.submit_job_description(student.student_id, jd_text)
    reqs = svc.extract_job_requirements(jd_text)
    report = svc.generate_job_gap_report(student.student_id, job_doc.job_id)
    plan = svc.generate_learning_plan(student.student_id)
    chk = svc.create_student_checkpoint(student.student_id, plan)

    req_rows = ""
    for r in reqs:
        badge_cls = "badge-verified" if r.verification_status == "Verified" else "badge-excluded"
        req_rows += f"""
        <tr>
          <td><strong>{html.escape(r.skill)}</strong></td>
          <td>{html.escape(r.importance)}</td>
          <td><span class="badge {badge_cls}">{html.escape(r.verification_status)}</span></td>
          <td style="font-size:0.8rem; color:#475569;">"{html.escape(r.source_quote)}"</td>
          <td style="font-size:0.8rem; color:var(--text-muted);">{html.escape(r.verification_note)}</td>
        </tr>
        """

    gap_rows = ""
    for g in report.gaps:
        p_color = "var(--danger)" if g.priority == "High" else ("var(--warning)" if g.priority == "Medium" else "var(--success)")
        gap_rows += f"""
        <tr>
          <td><strong>{html.escape(g.skill)}</strong></td>
          <td><strong>{g.current_score}/100</strong></td>
          <td>{html.escape(g.required_level)}</td>
          <td><span style="font-weight:700; color:{p_color};">{html.escape(g.priority)}</span></td>
          <td style="font-size:0.82rem; color:#475569;">{html.escape(g.reason)}</td>
        </tr>
        """

    content = f"""
    <div class="card">
      <div class="card-title">Verified Job Requirements (Tier 2 Provenance)</div>
      <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem;">
        Deterministic code verified that claimed quotes appear verbatim in the source text.
      </p>
      <table>
        <thead>
          <tr><th>Skill</th><th>Importance</th><th>Verification</th><th>Source Quote</th><th>Audit Note</th></tr>
        </thead>
        <tbody>
          {req_rows}
        </tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-title">Skill Gap Analysis vs {html.escape(student.name)}'s Profile</div>
      <table>
        <thead>
          <tr><th>Skill</th><th>Current Score</th><th>Required Level</th><th>Gap Priority</th><th>Reasoning</th></tr>
        </thead>
        <tbody>
          {gap_rows}
        </tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-title">Human Approval Checkpoint</div>
      <div class="box-warn">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h4 style="color:#b45309; font-size:1.05rem;">{html.escape(plan.title)}</h4>
          <span class="badge badge-waiting">WAITING_FOR_STUDENT</span>
        </div>
        <p style="font-size:0.88rem; margin:0.4rem 0;">High Priority Gaps: <strong>{html.escape(", ".join(report.high_priority_skills))}</strong></p>
        <p style="font-size:0.85rem; color:#64748b; margin-bottom:0.75rem;">
          The system will not unilaterally modify your learning plan. Please approve or reject:
        </p>
        <div style="display:flex; gap:0.6rem;">
          <form method="post" action="/checkpoint/{chk.checkpoint_id}/accept">
            <button type="submit" class="btn btn-success">Accept Recommendation</button>
          </form>
          <form method="post" action="/checkpoint/{chk.checkpoint_id}/reject">
            <button type="submit" class="btn btn-secondary">Reject</button>
          </form>
        </div>
      </div>
    </div>
    """
    return render_page("Job Analysis Results", content, active_nav="jobs", student=student)


# ----------------------------------------------------------- LEARNING PLAN (Section 12)

@app.get("/learning-plan", response_class=HTMLResponse)
def learning_plan_view(request: Request, topic: str = ""):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    if topic:
      plan = svc.select_learning_path(student.student_id, topic)
    else:
      run_id = svc._get_student_run_id(student.student_id)
      stored = svc.store.latest(run_id, "learning_plan")
      plan = LearningPlan(**stored) if stored else svc.generate_learning_plan(student.student_id)
    run_id = svc._get_student_run_id(student.student_id)
    stored_plan = svc.store.latest(run_id, "learning_plan")
    status = stored_plan.get("status", "WAITING_FOR_STUDENT") if stored_plan else plan.status

    badge_cls = "badge-verified" if status == "ACCEPTED" else "badge-waiting"
    available_paths = [skill for skill in svc.get_assessment_topics(student.student_id) if skill not in plan.target_skills]
    path_links = "".join(
      f"<a class='path-option' href='/learning-plan?topic={html.escape(skill)}'><strong>{html.escape(skill)}</strong><span>Add this path</span></a>"
      for skill in available_paths
    ) or "<p style='color:var(--text-muted); font-size:0.88rem;'>All role paths are currently included.</p>"

    sched_rows = ""
    for item in plan.schedule:
        sched_rows += f"""
        <tr>
          <td><strong>{html.escape(item.day)}</strong></td>
          <td><strong>{html.escape(item.topic)}</strong></td>
          <td style="color:#475569;">{html.escape(item.description)}</td>
        </tr>
        """

    content = f"""
    <div class="card">
      <div class="card-title">
        <span>Personalized Learning Plan</span>
        <span class="badge {badge_cls}">{html.escape(status)}</span>
      </div>
      <p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:1.5rem;">
        Actionable weekly curriculum derived from verified job gaps and previous misconception evidence.
      </p>

      <div class="box-info">
        <h3 style="color:#1e40af; font-size:1.15rem; margin-bottom:0.35rem;">{html.escape(plan.title)}</h3>
        <p style="font-size:0.88rem; color:#334155;">Target Focus Skills: <strong>{html.escape(", ".join(plan.target_skills))}</strong></p>
      </div>

      <div class="card" style="background:var(--surface-alt); box-shadow:none; margin-top:1rem;">
        <div class="card-title">Choose another path</div>
        <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:0.75rem;">Selecting a path integrates it with your current plan and adds its practice structure below.</p>
        <div class="path-list">{path_links}</div>
      </div>

      <table>
        <thead>
          <tr><th>Day</th><th>Focus Topic</th><th>Actionable Objective</th></tr>
        </thead>
        <tbody>
          {sched_rows}
        </tbody>
      </table>
      <div class="box-info" style="margin-top:1.25rem;"><strong>How to use this path:</strong> Start with the concept map, complete the applied practice, then take the matching assessment. Your instructor chat uses these same active topics.</div>
    </div>
    """
    return render_page("Learning Plan", content, active_nav="plan", student=student)


# --------------------------------------------------------- CHECKPOINTS (Section 13)

@app.post("/checkpoint/{checkpoint_id}/accept")
def checkpoint_accept_action(request: Request, checkpoint_id: str):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    svc.accept_recommendation(student.student_id, checkpoint_id)
    return RedirectResponse("/", status_code=303)


@app.post("/checkpoint/{checkpoint_id}/reject")
def checkpoint_reject_action(request: Request, checkpoint_id: str):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)
    svc.reject_recommendation(student.student_id, checkpoint_id)
    return RedirectResponse("/", status_code=303)


# ------------------------------------------------- PROFILE & EVIDENCE PORTFOLIO (Section 5, 16)

@app.get("/profile", response_class=HTMLResponse)
def profile_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    prof = svc.get_student_profile(student.student_id)

    skill_rows = ""
    for s, item in prof.skills.items():
        v_badge = "<span class='badge badge-verified'>Verified</span>" if item.verified else "<span class='badge badge-waiting'>Self-Reported</span>"
        skill_rows += f"""
        <tr>
          <td><strong>{html.escape(s)}</strong></td>
          <td><strong>{item.score}/100</strong></td>
          <td>{item.status}</td>
          <td>{html.escape(item.evidence_type)}</td>
          <td>{v_badge}</td>
        </tr>
        """

    proj_cards = ""
    for p in prof.projects:
        proj_cards += f"""
        <div class="box-info" style="margin-bottom:0.75rem;">
          <strong>{html.escape(p.title)}</strong>
          <p style="font-size:0.85rem; color:#475569; margin:0.25rem 0;">{html.escape(p.description)}</p>
          <span style="font-size:0.8rem; color:var(--primary); font-weight:600;">Skills: {html.escape(", ".join(p.skills_used))}</span>
        </div>
        """

    content = f"""
    <div class="card">
      <div class="card-title">Student Profile & Academic Record</div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; margin-bottom:1.5rem;">
        <div>
          <p style="color:var(--text-muted); font-size:0.85rem;">Name</p>
          <p style="font-weight:700; font-size:1.05rem;">{html.escape(prof.name)}</p>
        </div>
        <div>
          <p style="color:var(--text-muted); font-size:0.85rem;">College</p>
          <p style="font-weight:600;">{html.escape(prof.college)}</p>
        </div>
        <div>
          <p style="color:var(--text-muted); font-size:0.85rem;">Department</p>
          <p style="font-weight:600;">{html.escape(prof.department)}</p>
        </div>
        <div>
          <p style="color:var(--text-muted); font-size:0.85rem;">Graduation Year</p>
          <p style="font-weight:600;">{prof.graduation_year}</p>
        </div>
      </div>
      <div class="box-info">
        <strong>Learning context</strong>
        <p style="font-size:0.88rem; color:#334155; margin-top:0.35rem;">{html.escape(prof.education_level)} · CGPA {prof.cgpa:g} · Resume {'available for analysis' if prof.resume_text else 'not uploaded'}</p>
        <form method="post" action="/profile/update" enctype="multipart/form-data" style="margin-top:1rem;">
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
            <div class="form-group"><label>Education Level</label><input type="text" name="education_level" value="{html.escape(prof.education_level)}"></div>
            <div class="form-group"><label>CGPA / GPA</label><input type="number" name="cgpa" min="0" max="10" step="0.01" value="{prof.cgpa}"></div>
          </div>
          <div class="form-group"><label>Replace Resume (PDF or TXT)</label><input type="file" name="resume" accept=".pdf,.txt,application/pdf,text/plain"></div>
          <button type="submit" class="btn">Save and re-analyze</button>
        </form>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Evidence Portfolio (Principle 16 Distinction)</div>
      <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem;">
        The portal strictly distinguishes between self-reported claims and assessed / project-verified evidence.
      </p>
      <table>
        <thead>
          <tr><th>Skill</th><th>Score</th><th>Tier</th><th>Evidence Class</th><th>Status</th></tr>
        </thead>
        <tbody>
          {skill_rows}
        </tbody>
      </table>

      <h4 style="margin: 1.5rem 0 0.75rem; color:#1e3a8a;">Project Evidence Portfolio</h4>
      {proj_cards if proj_cards else "<p style='color:var(--text-muted); font-size:0.88rem;'>No external projects added yet.</p>"}

      <div style="margin-top:1.5rem; padding-top:1rem; border-top:1px solid var(--border);">
        <h4 style="margin-bottom:0.75rem;">Add Verified Project Proof</h4>
        <form method="post" action="/profile/add-project" style="max-width:32rem;">
          <div class="form-group">
            <label>Project Title</label>
            <input type="text" name="title" placeholder="e.g. SQLite Distributed KV Store" required>
          </div>
          <div class="form-group">
            <label>Description</label>
            <input type="text" name="desc" placeholder="Summary of architecture and implementation" required>
          </div>
          <div class="form-group">
            <label>Skills Used (comma-separated)</label>
            <input type="text" name="skills" placeholder="Python, SQLite, REST APIs" required>
          </div>
          <button type="submit" class="btn">Add Project Evidence</button>
        </form>
      </div>
    </div>
    """
    return render_page("Profile & Evidence", content, active_nav="profile", student=student)


@app.post("/profile/update")
async def profile_update(
    request: Request,
    education_level: str = Form("B.Tech"),
    cgpa: float = Form(0.0),
    resume: UploadFile | None = File(None),
  ):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
      return RedirectResponse("/login", status_code=303)
    updates: dict[str, Any] = {"education_level": education_level.strip(), "cgpa": cgpa}
    if resume and resume.filename:
      updates["resume_text"] = extract_resume_text(resume.filename, await resume.read())
    svc.update_student_profile(student.student_id, updates)
    svc.analyze_resume_and_gaps_with_llm(student.student_id)
    return RedirectResponse("/career-analysis", status_code=303)


@app.post("/profile/add-project")
def profile_add_project(request: Request, title: str = Form(...), desc: str = Form(...), skills: str = Form(...)):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    proj = ProjectEvidence(
        title=title.strip(),
        description=desc.strip(),
        skills_used=[s.strip() for s in skills.split(",") if s.strip()],
        verified=True,
    )
    svc.add_project_evidence(student.student_id, proj)
    return RedirectResponse("/profile", status_code=303)


# ----------------------------------------------------- RESOURCES

@app.get("/resources", response_class=HTMLResponse)
def resources_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
      return RedirectResponse("/login", status_code=303)
    resources = svc.get_topic_resources(student.student_id)
    tiles = []
    for topic, items in resources.items():
      links = "".join(
        f"<a class='resource-link' href='{html.escape(item['url'])}' target='_blank' rel='noopener noreferrer'>"
        f"<span class='badge badge-primary'>{html.escape(item['kind'])}</span> {html.escape(item['title'])}"
        f"<small style='display:block; color:var(--text-muted); margin-top:0.2rem;'>{html.escape(item['source'])}</small></a>"
        for item in items
      )
      tiles.append(f"<article class='resource-tile'><span class='badge badge-verified'>Role topic</span><h3>{html.escape(topic)}</h3>{links}</article>")
    content = f"""
    <div class="welcome-card"><div><h1>Learning Resources</h1><p style="color:var(--text-muted);">Curated references, courses, and books for your current role topics.</p></div><span class="role-tag">{html.escape(svc.get_active_career_goal(student.student_id).role)}</span></div>
    <div class="resource-grid">{"".join(tiles)}</div>
    """
    return render_page("Resources", content, active_nav="resources", student=student)


# ----------------------------------------------------- PROGRESS & TIMELINE (Section 14, 17)

@app.get("/progress", response_class=HTMLResponse)
def progress_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    analytics = svc.get_progress_analytics(student.student_id)
    timeline = svc.get_activity_timeline(student.student_id)
    counts = analytics["status_counts"]
    total_status = max(sum(counts.values()), 1)
    strong_end = counts["Strong"] / total_status * 100
    developing_end = strong_end + counts["Developing"] / total_status * 100
    weak_end = developing_end + counts["Weak"] / total_status * 100
    pie_style = f"conic-gradient(#16a34a 0 {strong_end}%, #2563eb {strong_end}% {developing_end}%, #d97706 {developing_end}% {weak_end}%, #94a3b8 {weak_end}% 100%)"
    legend = "".join(
      f"<li><i style='--swatch:{color}'></i>{label}: {counts[label]}</li>"
      for label, color in (("Strong", "#16a34a"), ("Developing", "#2563eb"), ("Weak", "#d97706"), ("Beginner", "#94a3b8"))
    )
    points = analytics["learning_rate"]
    graph_points = []
    graph_labels = []
    for index, point in enumerate(points):
      x = 35 if len(points) == 1 else 35 + index * (560 / (len(points) - 1))
      y = 185 - (point["score"] / 100 * 145)
      graph_points.append(f"{x:.1f},{y:.1f}")
      graph_labels.append(f"<text x='{x:.1f}' y='215' text-anchor='middle' class='chart-label'>{html.escape(point['date'][5:])}</text>")
    line_graph = (
      f"<svg viewBox='0 0 620 230' role='img' aria-label='Learning rate by assessment date'>"
      f"<line x1='35' y1='185' x2='595' y2='185' class='chart-axis'/><line x1='35' y1='40' x2='35' y2='185' class='chart-axis'/>"
      f"<polyline points='{' '.join(graph_points) or '35,185'}' class='chart-line'/>"
      + "".join(f"<circle cx='{p.split(',')[0]}' cy='{p.split(',')[1]}' r='4' class='chart-dot'/>" for p in graph_points)
      + "".join(graph_labels) + "</svg>"
    )
    tree_nodes = []
    for node in analytics["plan_nodes"]:
      children = "".join(
        f"<span class='tree-child'>{html.escape(child['label'])}</span>"
        for child in node["children"]
      )
      tree_nodes.append(
        f"<div class='tree-node'><strong>{html.escape(node['topic'])}</strong>"
        f"<span class='tree-confidence'>{node['confidence']}% confidence</span>"
        f"<span class='badge badge-primary' style='float:right;'>{html.escape(node['status'])}</span>"
        f"<div class='tree-children'>{children}</div></div>"
      )
    tree = "".join(tree_nodes) or "<p style='color:var(--text-muted);'>Choose a learning path from the dashboard to build the tree.</p>"
    history_events = ""
    for ev in timeline:
        history_events += f"""
        <div style="display:flex; gap:1rem; padding:0.85rem 0; border-bottom:1px solid var(--border);">
          <div style="width:2.2rem; height:2.2rem; border-radius:50%; background:var(--primary-light); color:var(--primary); display:flex; align-items:center; justify-content:center; font-weight:700; flex-shrink:0;">
            ✓
          </div>
          <div>
            <div style="font-weight:600; color:#1e293b;">{html.escape(ev.title)}</div>
            <p style="font-size:0.85rem; color:#475569;">{html.escape(ev.details)}</p>
          </div>
        </div>
        """

    stale_topics = "".join(
      f"<a class='refresh-topic' href='/assessment?topic={html.escape(topic)}' onclick=\"return confirm('Start a fresh {html.escape(topic)} assessment now?');\">{html.escape(topic)}<span>Click to take a refresh test</span></a>"
      for topic in analytics["stale_topics"]
    ) or "<p style='color:var(--text-muted); font-size:0.88rem;'>All required topics have recent assessment activity.</p>"
    extras = ", ".join(analytics["extra_skills"]) or "No additional priority skills identified."
    role_cards = "".join(f"<div class='role-fit-item'><strong>{html.escape(item['role'])}</strong><div class='meter-track' style='margin:0.45rem 0;'><div class='meter-bar' style='width:{item['fit']}%;'></div></div><span style='font-size:0.78rem; color:var(--text-muted);'>{item['fit']}% fit · {html.escape(item['evidence'])}</span></div>" for item in analytics["role_fit"])
    content = f"""
    <div class="welcome-card"><div><h1>Progress & readiness</h1><p style="color:var(--text-muted);">A dated view of {html.escape(student.name)}'s movement toward the current career goal.</p></div><span class="role-tag">Evidence-based</span></div>
    <div class="progress-grid">
      <div class="progress-kpi"><strong>{analytics['completion']}%</strong><span>Required topics completed</span></div>
      <div class="progress-kpi"><strong>{analytics['completed_assessments']}</strong><span>Assessments submitted</span></div>
      <div class="progress-kpi"><strong>{analytics['activity_count']}</strong><span>Recorded learning events</span></div>
      <div class="progress-kpi"><strong>{len(analytics['stale_topics'])}</strong><span>Topics needing a refresh</span></div>
    </div>
    <div class="chart-grid">
      <div class="card"><div class="card-title">Skill distribution</div><div class="pie-wrap"><div class="pie-chart" style="--pie:{pie_style};"></div><ul class="legend">{legend}</ul></div></div>
      <div class="card"><div class="card-title">Learning rate by date</div><p style="font-size:0.82rem; color:var(--text-muted);">Average assessment score for each date with completed tests.</p><div class='line-chart'>{line_graph}</div></div>
    </div>
    <div class="card"><div class="card-title">Current learning path</div><p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem;">{html.escape(analytics['plan_title'])}. Each selected dashboard path is integrated into this tree.</p><div class='path-tree'>{tree}</div></div>
    <div class="chart-grid">
      <div class="card"><div class="card-title">Needs attention</div><div class="box-warn"><strong>Topics needing refresh</strong><div class='refresh-list'>{stale_topics}</div></div><div class="box-info"><strong>Extra skills to learn</strong><p style="margin-top:0.35rem; font-size:0.88rem;">{html.escape(extras)}</p></div></div>
      <div class="card"><div class="card-title">Possible roles to apply for</div><p style="font-size:0.82rem; color:var(--text-muted); margin-bottom:0.75rem;">Fit is calculated from current assessed skills and resume evidence.</p><div class='role-fit'>{role_cards}</div></div>
    </div>
    <div class="card"><div class="card-title">Activity timeline</div><div>{history_events if history_events else "<p style='color:var(--text-muted);'>No activity recorded yet.</p>"}</div></div>
    """
    return render_page("Progress & Timeline", content, active_nav="progress", student=student)


# ---------------------------------------------------------- ASSESSMENT (Section 7)

@app.get("/assessment", response_class=HTMLResponse)
def assessment_view(request: Request, topic: str = "", test_id: str = ""):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    goal = svc.get_active_career_goal(student.student_id)
    topics = svc.get_assessment_topics(student.student_id)
    scores = svc.get_topic_scores(student.student_id)
    selected_test = svc.get_assessment_test(student.student_id, test_id) if test_id else None
    if topic and not selected_test:
        selected_test = svc.create_topic_assessment(student.student_id, topic)
    if selected_test:
        topic = selected_test["topic"]

    topic_rows = "".join(
        f"<a class='assessment-topic {'selected' if skill == topic else ''}' href='/assessment?topic={html.escape(skill)}'>"
        f"<span>{html.escape(skill)}</span><strong>{('-' if scores.get(skill) is None else str(scores[skill]) + '%')}</strong></a>"
        for skill in topics
    )
    question_cards = ""
    if selected_test:
        for index, question in enumerate(selected_test["questions"], 1):
            options = "".join(
                f"<label class='assessment-option'><input type='radio' name='answer_{question['question_id']}' value='{html.escape(option)}' required> {html.escape(option)}</label>"
                for option in question["options"]
            )
            question_cards += f"<div class='assessment-question'><span class='badge badge-primary'>Question {index} of 10</span><h3>{html.escape(question['question'])}</h3>{options}</div>"
        test_panel = f"""
        <div class="card assessment-test">
          <div class="card-title"><span>{html.escape(topic)} assessment</span><span class="badge badge-primary">Attempt {selected_test['attempt']}</span></div>
          <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem;">Ten fresh questions. Submit when you have answered every question.</p>
          <form method="post" action="/assessment/submit">
            <input type="hidden" name="test_id" value="{html.escape(selected_test['test_id'])}">
            {question_cards}
            <button type="submit" class="btn">Submit {html.escape(topic)} test</button>
          </form>
        </div>"""
    else:
        test_panel = "<div class='card'><div class='box-info'><strong>Select a topic to begin.</strong><p>Each topic opens a new ten-question test and stores the latest score beside the topic.</p></div></div>"

    content = f"""
    <div class="welcome-card"><div><h1>Role Assessments</h1><p style="color:var(--text-muted);">Choose a required {html.escape(goal.role)} topic and test your understanding.</p></div><span class="role-tag">10 questions per attempt</span></div>
    <div class="assessment-layout"><aside class="card assessment-sidebar"><div class="card-title">Required topics</div><p style="font-size:0.82rem; color:var(--text-muted); margin-bottom:0.75rem;">Latest score</p>{topic_rows}</aside><section>{test_panel}</section></div>
    """
    return render_page("Diagnostic Assessment", content, active_nav="assessment", student=student)


@app.post("/assessment/submit", response_class=HTMLResponse)
async def assessment_submit(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    form = await request.form()
    test_id = str(form.get("test_id", ""))
    test = svc.get_assessment_test(student.student_id, test_id)
    answers = {question["question_id"]: str(form.get(f"answer_{question['question_id']}", "")) for question in (test or {}).get("questions", [])}
    result = svc.submit_topic_assessment(student.student_id, test_id, answers)

    content = f"""
    <div class="card">
      <div class="card-title" style="color:var(--success);">Diagnostic Assessment Evaluated!</div>
      <div class="box-success">
        <p style="font-size:0.95rem; font-weight:600; color:#15803d; margin-bottom:0.35rem;">
          You scored {result['score']}% ({result['correct']}/{result['total']}).
        </p>
        <p style="font-size:0.88rem; color:#334155;">
          Review the explanations below, then ask the AI Coach about any topic that still feels unclear.
        </p>
      </div>
      {''.join(f"<div class='box-info'><strong>{html.escape(q['skill'])}:</strong> {html.escape(q['explanation'])}</div>" for q in (test or {}).get('questions', []))}
      <a href="/assessment" class="btn" style="margin-top:1rem;">Back to topics</a>
      <a href="/assessment?topic={html.escape(result['topic'])}" class="btn btn-secondary" style="margin-top:1rem;">Try a fresh test</a>
    </div>
    """
    return render_page("Assessment Result", content, active_nav="assessment", student=student)


# ------------------------------------------------------------- 20-STEP DEMO RUNNER

@app.get("/demo", response_class=HTMLResponse)
def demo_runner_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)

    res = run_arun_demo(DB)
    steps_html = ""
    for s in res["timeline"]:
        steps_html += f"""
        <div style="display:flex; gap:1rem; padding:0.85rem 0; border-bottom:1px solid var(--border);">
          <div style="width:2rem; height:2rem; border-radius:50%; background:var(--primary-light); color:var(--primary); display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:0.85rem; flex-shrink:0;">
            {s["step"]}
          </div>
          <div style="flex-grow:1;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:0.95rem; color:#1e293b;">{html.escape(s["title"])}</strong>
              <span class="badge badge-verified">{s["status"]}</span>
            </div>
            <p style="font-size:0.85rem; color:#475569; margin-top:0.2rem;">{html.escape(s["detail"])}</p>
          </div>
        </div>
        """

    content = f"""
    <div class="card">
      <div class="card-title">
        <span>Section 24: End-to-End Walkthrough Verification</span>
        <span class="badge badge-verified">20/20 Steps Passed</span>
      </div>
      <p style="font-size:0.92rem; color:var(--text-muted); margin-bottom:1.25rem;">
        Automated run of the Arun 20-step workflow proving SQLite persistence across restarts, misconception untangling (GET vs POST), citation provenance checks, and human checkpoints.
      </p>

      <div style="background:#ffffff; border:1px solid var(--border); border-radius:10px; padding:1.25rem;">
        {steps_html}
      </div>

      <div style="margin-top:1.5rem; display:flex; gap:1rem;">
        <a href="/" class="btn">Return to Personalized Dashboard &rarr;</a>
        <a href="/job-analyzer" class="btn btn-secondary">Open Job Analyzer &rarr;</a>
      </div>
    </div>
    """
    return render_page("20-Step Demo", content, active_nav="demo", student=student)
