# EventGenie AI 🎉✨

> A GenAI-powered event planning assistant built with Python, Flask, and Google Gemini AI.

EventGenie AI helps you plan weddings, birthdays, college events, and community celebrations with AI-generated plans, smart budget breakdowns, preparation timelines, vendor checklists, and a conversational planning assistant.

---

## 🚀 Features

| Feature | Description |
|---|---|
| 🤖 AI Event Planner | Gemini-powered personalized event plans |
| 💰 Smart Budget Planner | Category-wise allocation, live edits, Chart.js visualization |
| 📅 Preparation Timeline | Phase-by-phase task checklist |
| 📆 Event-Day Schedule | Time-based itinerary |
| ✅ Vendor Checklist | Category-wise vendor tasks |
| 🎨 Creative Ideas | Themes, colors, menus, entertainment, budget tips |
| 💬 AI Chat Assistant | Conversational refinement with memory |
| 📋 Task Management | Add, edit, delete, complete tasks |
| 💾 Persistent Storage | SQLite via SQLAlchemy |
| 📱 Responsive UI | Works on desktop, tablet, mobile |

---

## 🛠️ Technology Stack

**Frontend:** HTML5, CSS3 (custom design system), Vanilla JavaScript, Chart.js, Lucide icons  
**Backend:** Python 3.10+, Flask 3.0, Flask-SQLAlchemy, Flask-CORS  
**AI:** Google Gemini API via `google-genai` SDK  
**Database:** SQLite (via SQLAlchemy)  
**Testing:** Pytest, pytest-flask, mocked Gemini calls  

---

## ⚡ Quick Start (Windows PowerShell)

### 1. Clone / Open the Project

```powershell
cd c:\EventPlanner
code .
```

### 2. Create and Activate Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
# If execution policy blocks this:
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Install Dependencies

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Configure Environment

Copy and edit `.env`:

```powershell
copy .env.example .env
notepad .env
```

Add your Gemini API key:
```
GEMINI_API_KEY=your_actual_key_here
```

Get a free key at: https://aistudio.google.com/app/apikey

### 5. Start the Flask Server

```powershell
.\venv\Scripts\python.exe app.py
```

Or using Flask CLI:
```powershell
$env:FLASK_APP = "app.py"; .\venv\Scripts\flask.exe run
```

### 6. Open in Browser

```
http://localhost:5000
```

---

## 🧪 Running Tests

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Tests use an in-memory SQLite database and mock all Gemini API calls — no real API key needed for tests.

### Expected Output

```
tests/test_app.py::test_health_endpoint PASSED
tests/test_app.py::test_create_event_success PASSED
tests/test_app.py::test_budget_calculation PASSED
tests/test_app.py::test_complete_task PASSED
tests/test_app.py::test_generate_plan_mocked PASSED
... (all tests pass)
```

---

## 🌐 API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check + API status |
| POST | `/api/events` | Create event |
| GET | `/api/events` | List all events |
| GET | `/api/events/<id>` | Get event with plans |
| PUT | `/api/events/<id>` | Update event |
| DELETE | `/api/events/<id>` | Delete event |
| POST | `/api/events/<id>/generate-plan` | Generate AI plan |
| POST | `/api/events/<id>/chat` | Chat with AI assistant |
| GET | `/api/events/<id>/budget` | Get budget items |
| PUT | `/api/events/<id>/budget` | Update budget items |
| GET | `/api/events/<id>/tasks` | Get tasks |
| POST | `/api/events/<id>/tasks` | Create task |
| PUT | `/api/tasks/<id>` | Update task |
| DELETE | `/api/tasks/<id>` | Delete task |

### Example: Create Event

```powershell
Invoke-WebRequest -Uri "http://localhost:5000/api/events" `
  -Method POST `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"name":"Priya Wedding","event_type":"wedding","budget":500000,"guest_count":300}'
```

---

## 🗂️ Project Structure

```
EventPlanner/
├── app.py              # Flask app factory
├── config.py           # Configuration (dev/prod/test)
├── ai_service.py       # All Gemini AI calls
├── extensions.py       # SQLAlchemy instance
├── requirements.txt
├── .env                # Secrets (git-ignored)
├── .env.example        # Template
├── .gitignore
├── README.md
├── models/
│   └── __init__.py     # Event, EventPlan, BudgetItem, Task, ChatMessage
├── routes/
│   ├── events.py       # Event CRUD, plan generation, chat, budget
│   └── tasks.py        # Task update/delete
├── services/
│   └── budget_service.py  # Python budget arithmetic (not AI)
├── templates/
│   └── index.html      # SPA frontend
├── static/
│   ├── css/style.css   # Design system
│   └── js/app.js       # Application logic
├── tests/
│   └── test_app.py     # 20+ automated tests
└── instance/
    └── eventgenie.db   # SQLite database (auto-created)
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `FLASK_SECRET_KEY` | *(change this)* | Flask session secret |
| `FLASK_ENV` | `development` | Environment mode |
| `FLASK_DEBUG` | `true` | Debug mode |

---

## 🚀 Deployment

### Render.com (Recommended Free Tier)

1. Push code to GitHub (ensure `.env` is in `.gitignore`)
2. Create new Web Service on Render
3. Build command: `pip install -r requirements.txt`
4. Start command: `python app.py`
5. Add environment variables in Render dashboard

### Railway / Fly.io

Similar setup — provide environment variables in the dashboard.

---

## ⚠️ Limitations & Disclaimers

- All AI-generated budget figures are **estimates only** — not confirmed vendor quotes.
- The app does **not** create real bookings or contact vendors.
- Single-user SQLite database — not multi-user ready without authentication.
- Gemini API costs apply beyond the free quota.
- Plan generation may take 30–60 seconds depending on API load.

---

## 🔮 Future Improvements

- User authentication and multi-user support
- PDF export of plans and budgets
- Real vendor directory integration
- Email/WhatsApp reminders for tasks
- Collaborative event planning (multiple planners)
- Offline mode with service workers

---

## 📄 Resume Description

**EventGenie AI** — Full-Stack GenAI Event Planning Web Application  
- Built a Python/Flask REST API integrated with **Google Gemini AI** to generate personalized wedding, birthday, and community event plans including structured budgets, preparation timelines, and vendor checklists  
- Implemented **SQLite/SQLAlchemy** persistence for events, generated plans, budget allocations, tasks, and conversation history with proper relational schema  
- Designed a responsive **premium SaaS-style frontend** using HTML5/CSS3/Vanilla JS with Chart.js budget visualizations, real-time task management, and a conversational AI assistant interface  
- Engineered a **Python budget calculation service** to validate and correct AI-generated expense allocations, ensuring totals match user budgets without relying on the language model for arithmetic  
- Wrote **20+ automated tests** using Pytest with mocked Gemini API calls, covering CRUD operations, budget logic, error handling, and AI failure modes

---

*Built for Google Gemini AI Hackathon — EventGenie AI v1.0*
