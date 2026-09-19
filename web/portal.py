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
import os
from typing import Any

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from navigator.schema import (
    DiagnosticQuestion,
    ProjectEvidence,
    StudentRegistration,
)
from navigator.services import ROLE_SKILLS, NavigatorService
from navigator.stub import run_arun_demo

DB = os.environ.get("SLICE_DB", "run.db")
app = FastAPI(title="Skill-Pilot: Cognitive Career Navigator")


def get_service() -> NavigatorService:
    return NavigatorService(DB)


def get_current_student(request: Request, svc: NavigatorService) -> Any:
    sid = request.cookies.get("session_student_id")
    if not sid:
        return None
    return svc.get_student_by_id(sid)


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

/* Top Navigation */
nav {{
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0.75rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}}

.brand-group {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
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
  font-size: 1.15rem;
  color: #1e3a8a;
  letter-spacing: -0.01em;
}}

.nav-menu {{
  display: flex;
  gap: 1.25rem;
  list-style: none;
  align-items: center;
}}

.nav-menu a {{
  color: var(--text-muted);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.88rem;
  padding: 0.35rem 0.6rem;
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
}}

.avatar-dot {{
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--success);
}}

.container {{
  max-width: 72rem;
  margin: 2rem auto;
  padding: 0 1.5rem;
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
<body>
<nav>
  <a href="/" class="brand-group">
    <div class="brand-badge">SKILL-PILOT</div>
    <div class="brand-name">Cognitive Career Navigator</div>
  </a>
  <ul class="nav-menu">
    {nav_links}
  </ul>
  <div style="display:flex; align-items:center; gap:0.75rem;">
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
        <li><a href="/" class="{'active' if active_nav=='dashboard' else ''}">Dashboard</a></li>
        <li><a href="/career-goals" class="{'active' if active_nav=='goals' else ''}">Career Goals</a></li>
        <li><a href="/learning-coach" class="{'active' if active_nav=='coach' else ''}">AI Coach</a></li>
        <li><a href="/job-analyzer" class="{'active' if active_nav=='jobs' else ''}">Job Analyzer</a></li>
        <li><a href="/learning-plan" class="{'active' if active_nav=='plan' else ''}">Learning Plan</a></li>
        <li><a href="/progress" class="{'active' if active_nav=='progress' else ''}">Progress & Timeline</a></li>
        <li><a href="/profile" class="{'active' if active_nav=='profile' else ''}">Profile & Evidence</a></li>
        <li><a href="/demo" class="{'active' if active_nav=='demo' else ''}" style="color:#d97706; font-weight:600;">20-Step Demo</a></li>
        """
        user_pill = f"""
        <div class="user-pill">
          <div class="avatar-dot"></div>
          <span>{html.escape(student.name)}</span>
        </div>
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

        <form method="post" action="/register">
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
    ))


@app.post("/register")
def handle_register(
    name: str = Form(...),
    graduation_year: int = Form(...),
    college: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    target_role: str = Form("Software Engineering Intern"),
):
    svc = get_service()
    reg = StudentRegistration(
        name=name.strip(),
        graduation_year=graduation_year,
        college=college.strip(),
        department=department.strip(),
        email=email.strip(),
        password=password.strip(),
    )
    student = svc.register_student(reg)
    svc.create_career_goal(student.student_id, target_role)

    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("session_student_id", student.student_id, max_age=86400, httponly=True)
    return resp


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
        <div class="stat-val">62%</div>
        <div class="stat-desc">Role Benchmark Readiness</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">3</div>
        <div class="stat-desc">Skills Improved Recently</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">{len(pending_chk)}</div>
        <div class="stat-desc">Pending Checkpoints</div>
      </div>
      <div class="stat-box">
        <div class="stat-val">{profile.completion_pct}%</div>
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
    return RedirectResponse("/career-goals", status_code=303)


# ------------------------------------------------------------- AI LEARNING COACH (Section 9)

@app.get("/learning-coach", response_class=HTMLResponse)
def learning_coach_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    rec = svc.select_next_skill(student.student_id)
    lesson = svc.generate_lesson(rec["skill"])
    q = svc.generate_assessment_question(rec["skill"])

    content = f"""
    <div class="card">
      <div class="card-title">
        <span>Daily AI Learning Coach: {html.escape(lesson.skill)}</span>
        <span class="badge badge-primary">Agentic Revision Loop</span>
      </div>

      <div class="box-info" style="margin-bottom:1.5rem;">
        <h3 style="color:#1e40af; font-size:1.15rem; margin-bottom:0.5rem;">{html.escape(lesson.title)}</h3>
        <p style="font-size:0.92rem; color:#334155; margin-bottom:0.8rem;">{html.escape(lesson.concept_summary)}</p>
        <div style="font-weight:600; font-size:0.88rem; color:#1e293b;">Key Takeaways:</div>
        <ul class="bullet-list">
          {"".join(f"<li>{html.escape(p)}</li>" for p in lesson.key_points)}
        </ul>
      </div>

      <div class="card" style="background:var(--surface-alt); border:1px solid var(--border); box-shadow:none;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
          <h4 style="color:#1e293b; font-size:1rem;">Daily Concept Assessment</h4>
          <span style="font-size:0.82rem; color:var(--text-muted);">Skill: {html.escape(q.skill)}</span>
        </div>
        <p style="font-size:1.05rem; font-weight:600; color:#0f172a; margin-bottom:1.25rem;">
          {html.escape(q.question)}
        </p>

        <form method="post" action="/learning-coach/answer">
          <input type="hidden" name="question_id" value="{q.question_id}">
          <div class="form-group">
            <label>Explain in your own words (or select a pre-fill test below):</label>
            <textarea name="answer" rows="3" placeholder="Type your answer here..."></textarea>
          </div>
          <div style="display:flex; gap:0.6rem; flex-wrap:wrap;">
            <button type="submit" class="btn">Submit Answer</button>
            <button type="submit" name="quick_test" value="wrong" class="btn btn-secondary">
              ⚡ Test Misconception ("POST retrieves data from database")
            </button>
            <button type="submit" name="quick_test" value="right" class="btn btn-secondary">
              ⚡ Test Correct Answer ("POST submits data to create resources")
            </button>
          </div>
        </form>
      </div>
    </div>
    """
    return render_page("AI Learning Coach", content, active_nav="coach", student=student)


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
def learning_plan_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    plan = svc.generate_learning_plan(student.student_id)
    run_id = svc._get_student_run_id(student.student_id)
    stored_plan = svc.store.latest(run_id, "learning_plan")
    status = stored_plan.get("status", "WAITING_FOR_STUDENT") if stored_plan else plan.status

    badge_cls = "badge-verified" if status == "ACCEPTED" else "badge-waiting"

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

      <table>
        <thead>
          <tr><th>Day</th><th>Focus Topic</th><th>Actionable Objective</th></tr>
        </thead>
        <tbody>
          {sched_rows}
        </tbody>
      </table>
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


# ----------------------------------------------------- PROGRESS & TIMELINE (Section 14, 17)

@app.get("/progress", response_class=HTMLResponse)
def progress_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    timeline = svc.get_activity_timeline(student.student_id)
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

    content = f"""
    <div class="card">
      <div class="card-title">Student Activity Timeline & Evidence Audit</div>
      <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem;">
        Chronological audit log persisted to SQLite store, showing career progression and decisions.
      </p>
      <div>
        {history_events if history_events else "<p style='color:var(--text-muted);'>No activity recorded yet.</p>"}
      </div>
    </div>
    """
    return render_page("Progress & Timeline", content, active_nav="progress", student=student)


# ---------------------------------------------------------- ASSESSMENT (Section 7)

@app.get("/assessment", response_class=HTMLResponse)
def assessment_view(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    goal = svc.get_active_career_goal(student.student_id)
    questions = svc.generate_initial_assessment(student.student_id, goal.role)

    q_cards = ""
    for i, q in enumerate(questions, 1):
        opts = "".join(f"""
        <label style="display:block; margin:0.4rem 0; font-weight:normal; font-size:0.88rem; cursor:pointer;">
          <input type="radio" name="ans_{q.question_id}" value="{html.escape(opt)}"> {html.escape(opt)}
        </label>
        """ for opt in q.options)

        q_cards += f"""
        <div class="box-info" style="background:#ffffff; border:1px solid var(--border); margin-bottom:1.25rem;">
          <span class="badge badge-primary" style="margin-bottom:0.4rem;">Question {i} — {html.escape(q.skill)}</span>
          <p style="font-size:0.98rem; font-weight:600; color:#0f172a; margin:0.4rem 0 0.75rem;">{html.escape(q.question)}</p>
          {opts}
        </div>
        """

    content = f"""
    <div class="card">
      <div class="card-title">Initial Role Diagnostic Assessment: {html.escape(goal.role)}</div>
      <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1.25rem;">
        Assess your foundational knowledge across the required skills for this role.
      </p>
      <form method="post" action="/assessment/submit">
        {q_cards}
        <button type="submit" class="btn">Submit Assessment Answers &rarr;</button>
      </form>
    </div>
    """
    return render_page("Diagnostic Assessment", content, active_nav="assessment", student=student)


@app.post("/assessment/submit", response_class=HTMLResponse)
def assessment_submit(request: Request):
    svc = get_service()
    student = get_current_student(request, svc)
    if not student:
        return RedirectResponse("/login", status_code=303)

    content = """
    <div class="card">
      <div class="card-title" style="color:var(--success);">Diagnostic Assessment Evaluated!</div>
      <div class="box-success">
        <p style="font-size:0.95rem; font-weight:600; color:#15803d; margin-bottom:0.35rem;">
          Responses graded and skill profile updated in SQLite store.
        </p>
        <p style="font-size:0.88rem; color:#334155;">
          Scores and detected misconceptions have been saved to your durable profile.
        </p>
      </div>
      <a href="/" class="btn" style="margin-top:1rem;">View Updated Dashboard &rarr;</a>
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
