# Kenya Airways Virtual Assistant

An NLP-based conversational agent for airline customer support, built for
ICS Project II. It handles four support domains: **flight status**,
**baggage policy**, **check-in** and **booking management** (new, change,
cancel). It escalates to a human agent when it can't help.

## Architecture

```
Web portal        frontend/        home, login, My bookings, staff dashboard + chat widget (WCAG 2.1 AA)
        │  REST (JSON)
FastAPI gateway   backend/          :8000   session tokens, validation, conversation logging
        │  REST channel
Rasa server       config.yml        :5005   BERT + DIET NLU, forms, Rule/TED policies
        │  webhook
Action server     actions/          :5055   form validation and transactions
        │  SQL
PostgreSQL        database/         :5432   users, flights, bookings, conversations
```

## Project structure

| Path | Contents |
|---|---|
| `data/nlu.yml` | Intent and entity training data, regexes, lookup table, synonyms |
| `data/rules.yml`, `data/stories.yml` | Dialogue rules (forms, FAQs, fallback) and multi-turn stories |
| `domain.yml` | Intents, entities, slots, forms and responses |
| `config.yml` | NLU pipeline and dialogue policies |
| `actions/` | Custom actions: `forms.py` (validation), `actions.py` (tasks), `repository.py` (SQL), `parsing.py` (dates, references) |
| `frontend/` | Web portal pages (`index`, `login`, `account`, `admin`), shared `site.css`/`site.js`/`api.js`, and the chat widget (`chat.js`, `voice.js`, `styles.css`). Put the logo in `frontend/assets/logo.png` |
| `backend/` | FastAPI gateway; also serves the widget |
| `database/` | `schema.sql`, `seed.sql`, `init_db.py` |
| `tests/` | pytest unit tests, Rasa end-to-end test stories, the held-out NLU test set and browser tests (`tests/e2e/`) |
| `docs/` | Evaluation reports |

## Setup

Requires Python 3.10 and PostgreSQL 16.

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env           # then set DB_PASSWORD
python database\init_db.py       # creates tables and loads sample data
rasa train
```

The first `rasa train` downloads `bert-base-uncased` (about 440 MB) from
Hugging Face. If the download stalls, download the model files in a browser
and place them in the Hugging Face cache.

## Running

Use three terminals, each with the venv active:

```powershell
rasa run actions                 # 1. action server   :5055
rasa run --enable-api            # 2. Rasa server     :5005 (--enable-api is needed for conversation logging)
uvicorn backend.main:app --port 8000   # 3. API gateway :8000, docs at http://127.0.0.1:8000/docs
```

Then open **http://127.0.0.1:8000**. The portal has:

| Page | What it does |
|---|---|
| **Home** | Flight status search, "ask the assistant" shortcuts, baggage and check-in information |
| **Log in / Create account** | Passenger registration and login; staff log in here too |
| **My bookings** (passengers) | Your bookings with flight details and one-click buttons that ask the assistant to change, cancel or check them |
| **Staff dashboard** (admin, FR-06) | Conversation statistics, the conversation log with a status filter, transcripts, and "Mark resolved" for chats escalated to an agent |

The **Chat with us** button opens the assistant on every passenger page. When you're logged in, it
offers your own bookings as buttons instead of asking you to type a reference. It also has quick
replies, voice input and read-aloud replies (Chrome or Edge), a high-contrast theme, full keyboard
use, and a conversation that survives a page reload.

Demo accounts (sample data only; set different passwords with `DEMO_PASSWORD` and
`DEMO_ADMIN_PASSWORD` before running `init_db.py`):

| Role | Email | Password |
|---|---|---|
| Passenger (booking BK001) | `john@email.com` | `Passenger@2026` |
| Staff | `admin@kq-demo.local` | `Admin@2026` |

The other sample passengers (`amina@`, `peter@`, `grace@`, `david@`, `mary@email.com`) use the passenger password.

**Logo:** save the official Kenya Airways logo as `frontend/assets/logo.png` and it appears in the
header automatically (see `frontend/assets/README.md`). Until then a "KQ" mark is shown. The footer
states that this is a student project not affiliated with Kenya Airways, so keep the portal local or
private rather than hosting it publicly.

To chat in the terminal, keep the action server running and use `rasa shell`
**instead of** `rasa run` (terminal 2). Both start a Rasa server on port 5005,
so running them together fails with `[Errno 10048] ... ('0.0.0.0', 5005)`.
To keep the full stack running as well, give the shell its own port:

```powershell
rasa shell --port 5006
```

Sample data: booking references `BK001`–`BK006` and flight numbers `KQ101`,
`KQ202`, `KQ305`, `KQ450`, `KQ505`, `KQ601`, `KQ702`, `KQ789`. Departures
are relative to the day the seed was loaded. Re-run `python database\init_db.py`
to reset bookings and refresh dates.

Example conversation:

```
You: I want to change my flight
Bot: Please provide your booking reference (e.g. BK001).
You: BK002
Bot: What date would you like to move your flight to? (e.g. 25 October)
You: tomorrow
Bot: There's no available KQ202 flight on Thu 15 Oct 2026. It operates on: Fri 23 Oct 2026. Which date would you like?
You: the 23rd
Bot: Booking BK002 (KQ202 Nairobi to Dubai): Current: Wed 21 Oct 22:00 / New: Fri 23 Oct 22:00. Shall I confirm this change?
You: yes
Bot: Done! Booking BK002 is now on KQ202 departing Fri 23 Oct 2026 at 22:00.
```

## Testing

```powershell
pytest                                                   # unit + integration tests (creates airline_db_test)
rasa data validate                                       # domain and training data consistency
rasa test nlu --nlu tests\nlu_test_data.yml              # held-out NLU evaluation
rasa test core --stories tests\test_stories.yml          # end-to-end conversation tests

# Browser tests for the portal and widget (needs Node.js 18+, Chrome and the running stack)
python database\init_db.py
cd tests\e2e; npm install; npm test
```

Current results (16 Oct 2026):

| Check | Result | Target |
|---|---|---|
| Held-out intent accuracy | 96.4% | ≥ 85% (NFR-01) |
| Entity weighted F1 | 0.87 | |
| End-to-end test stories | 8 / 8 (40 / 40 actions) | |
| API response time | 0.5–0.9 s | ≤ 2 s (NFR-01) |
| Unit + integration tests (pytest) | 80 passed | |
| Browser checks: widget / portal | 28 / 28 and 44 / 44 | |
| Accessibility (axe-core) | 0 violations across 11 page states | WCAG 2.1 AA (NFR-03) |

See [docs/nlu-evaluation.md](docs/nlu-evaluation.md) for the detailed NLU report.

## Progress

Tracked with [GitHub milestones](https://github.com/JoshuaBaraka24/airline-chatbot/milestones) that follow the project Gantt chart:

| Milestone | Gantt period | Status |
|---|---|---|
| M1: Data Collection & Preprocessing | Jun–Jul 2026 | Done |
| M2: NLU Model Training | Jul–Aug 2026 | Done |
| M3: Dialogue Manager Development | Jul–Sep 2026 | Done |
| M4: Backend API & Database | Aug–Sep 2026 | Done |
| M5: Chat Widget (Frontend) | Sep–Oct 2026 | Done |
| M6: System Integration & Testing | Oct–Nov 2026 | In progress (web portal and DB integration tests done) |
| M7: User Acceptance Testing | Nov 2026 | Not started |
| M8: Report Writing & Final Submission | Oct–Dec 2026 | Not started |

## Contributing

Work happens on short-lived branches (`feat/…`, `fix/…`, `data/…`, `docs/…`)
merged into `main` through pull requests linked to a milestone. Commit
messages follow `type(scope): summary`, with types `feat`, `fix`, `data`,
`config`, `test`, `docs`, `perf`, `refactor` and `chore`.
