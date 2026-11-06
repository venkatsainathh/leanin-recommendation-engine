# Lean In Recommendation Engine

A locally runnable Circle recommendation service with a member-friendly web interface. It helps members discover relevant, active communities with room to join and explains each suggestion in plain language.

The project uses the supplied synthetic dataset. All members go through the same recommendation rules; the four assignment scenarios are verification cases, not special ranking branches.

**Submission materials:** [Local setup](#quick-start) · [Technical design](DESIGN.md) · [Database schema overview](SCHEMA.md) · [SQL definitions](schema.sql)

## Contents

- [Quick start](#quick-start)
- [Using the interface](#using-the-interface)
- [Project structure](#project-structure)
- [API reference](#api-reference)
- [Recommendation pipeline](#recommendation-pipeline)
- [Database and seed data](#database-and-seed-data)
- [Configuration](#configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Engineering decisions and production path](#engineering-decisions-and-production-path)
- [Publishing the repository](#publishing-the-repository)

## Quick start

### Requirements

- Python 3.11 or newer; locally verified with Python 3.13 on macOS.
- Internet access to install Python dependencies on first setup.
- A modern browser.

No Node.js build, Docker, external database, or API key is required. Windows and Linux instructions are provided, but those platforms have not been verified in this project session. The seed importer uses a same-filesystem hard link for atomic publication; use a local filesystem that supports hard links.

Clone the repository, then run the commands below from the directory containing your clone. If you already opened a terminal inside the project, skip the first `cd` command.

```sh
git clone https://github.com/venkatsainathh/leanin-recommendation-engine.git
```

### macOS / Linux

```sh
cd leanin-recommendation-engine
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If the project is in Downloads, the first command can be `cd ~/Downloads/leanin-recommendation-engine`.

### Windows PowerShell

```powershell
cd leanin-recommendation-engine
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

These Windows commands use the environment's interpreter directly, so activation and PowerShell execution-policy changes are unnecessary. Ensure `py -3` selects Python 3.11 or newer.

Open:

| Page | Address |
|---|---|
| Member interface | [http://127.0.0.1:8000/](http://127.0.0.1:8000/) |
| Interactive API documentation | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| OpenAPI schema | [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json) |

First startup automatically creates `circles.sqlite3` from the bundled JSON files if the database does not exist. Existing databases are preserved. Keep the terminal open; press **Ctrl+C** to stop the server.

For subsequent runs, activate the existing environment and run the Uvicorn command. Add `--reload` for Python development. To use another port, change `--port 8000` to `--port 8001` and open the corresponding address. The frontend uses relative URLs and needs no port-specific edits.

## Using the interface

1. Click **Select or search for a member…**. No member is selected initially.
2. Search by name, member ID, or interest. Results remain sorted by ascending member ID.
3. Click a result, or use the arrow keys and Enter. Escape dismisses the menu.
4. Read the recommended Circle cards: purpose, explanation, meeting format, member count, availability, and joining policy.
5. Filter by **All formats**, **Virtual**, **Hybrid**, or **In person**.
6. Choose **Explore Circle** for details or **Explore more Circles** for additional results.

The frontend requests up to 50 recommendations, initially displays six, and reveals six more at a time. Format filtering operates on those recommendations in the browser; it does not change the ranking engine. Duplicate names are distinguished by member IDs and interests in the search results.

**What the labels mean:**

- **Open to join:** the Circle has an open joining policy.
- **Request to join:** membership requires approval; acceptance is not guaranteed.
- **Places available:** remaining capacity in the data snapshot, not a reservation.
- **No membership cap:** capacity is unspecified, not zero.
- **Meeting location not provided:** the dataset does not contain a Circle location; the interface does not infer it from member locations.

This is a read-only demonstration. Joining, messaging, authentication, and profile editing are not implemented. The **Developer API** button in the header opens the interactive API documentation.

## Project structure

```text
leanin-recommendation-engine/
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI routes, response models, application lifecycle
│   ├── database.py               # SQLite connections and project-relative paths
│   ├── ranking.py                # Eligibility, scoring, diversity, explanations
│   └── static/
│       ├── index.html            # Member interface
│       ├── recommendations.js    # Search, API calls, cards, filters, details
│       └── styles.css            # Responsive presentation
├── data/
│   ├── users.json
│   ├── circles.json
│   ├── memberships.json
│   ├── topics.json
│   └── activity.json
├── schema.sql                    # Tables, constraints, and indexes
├── seed.py                       # Atomic import of the supplied dataset
├── requirements.txt              # Pinned runtime dependencies
├── tests/test_recommendations.py  # Four assignment scenarios
├── DESIGN.md
├── SCHEMA.md
├── .gitignore
└── README.md
```

`.venv/` and `circles.sqlite3` are local runtime artifacts, not required repository contents. Paths are resolved from the source location, so the project can be moved without embedding a user's machine path.

## API reference

### Ranked recommendations

```http
GET /recommendations/{user_id}?limit=10
```

| Parameter | Type | Rules |
|---|---|---|
| `user_id` | Integer path parameter | Positive ID; supplied members have IDs 1–100 |
| `limit` | Integer query parameter | Default 10; minimum 1; maximum 50 |

```sh
curl "http://127.0.0.1:8000/recommendations/7?limit=3"
```

In PowerShell, use `Invoke-RestMethod "http://127.0.0.1:8000/recommendations/7?limit=3"`.

| Status | Meaning |
|---|---|
| `200` | Successful response, including an empty list when nothing qualifies |
| `404` | User does not exist |
| `422` | Invalid user ID or limit |

Each result includes:

| Field | Meaning |
|---|---|
| `rank` | Position after diversity selection |
| `circle_id`, `name`, `description` | Circle identity and purpose |
| `topics` | Human-readable taxonomy labels |
| `format`, `location` | Meeting format and optional location |
| `member_count`, `available_seats` | Snapshot size and remaining capacity; null seats means uncapped |
| `join_policy` | `open` or `request` |
| `explanation` | Deterministic, member-facing reason for the suggestion |
| `base_score` | Weighted score before diversity |
| `diversity_penalty` | Deduction for overlap with earlier selections |
| `score` | Selection score after that deduction |
| `components` | Topic, profile, health, and welcome feature values |

Scores are ranking utilities, **not percentage matches or probabilities**. A diversity-adjusted score can be negative. Components are feature values; their weights depend on the strategy, and not every reported component is used in every strategy.

Metadata reports the algorithm version, evaluation time, clock mode, personalized/discovery strategy, cold-start flag, eligible and returned counts, requested limit, inactivity cutoff, and primary-topic cap. Fewer results than requested is valid.

### Example response

Actual output for `GET /recommendations/7?limit=1` with the supplied snapshot:

```json
{
  "user_id": 7,
  "recommendations": [
    {
      "rank": 1,
      "circle_id": 6,
      "name": "Speak Up Circle",
      "description": "A supportive circle for women focused on public speaking.",
      "format": "in_person",
      "location": null,
      "join_policy": "open",
      "topics": [
        "Leadership skills",
        "Public speaking",
        "Career breaks"
      ],
      "member_count": 9,
      "available_seats": 4,
      "score": 0.75832,
      "base_score": 0.75832,
      "diversity_penalty": 0.0,
      "components": {
        "topic": 0.883333,
        "profile": 0.0,
        "health": 0.761068,
        "welcome": 0.9
      },
      "explanation": "You share interests in Leadership skills and Public speaking. It meets in person; check the meeting location. It is open to new members."
    }
  ],
  "metadata": {
    "algorithm_version": "heuristic-v1",
    "as_of": "2026-09-21T00:00:00Z",
    "clock_mode": "snapshot",
    "strategy": "personalized",
    "cold_start": false,
    "eligible_count": 34,
    "returned_count": 1,
    "requested_limit": 1,
    "inactivity_days": 60,
    "diversity_max_per_primary_topic": 2
  }
}
```

### Demo member directory

```http
GET /demo/members
```

Returns synthetic member IDs, first/last names, and interest labels. The searchable member picker depends on this endpoint; deleting it breaks the picker. It is listed under **Demo** in the API docs. It must be removed or authorized before using real member data.

### Application and assets

`GET /` serves the interface; `/static/` serves CSS and JavaScript. `/docs` and `/openapi.json` provide developer documentation. The service has no dedicated health-check endpoint.

## Recommendation pipeline

```text
Validate request
  → open a consistent database read transaction
  → filter eligible Circles
  → batch-read topics and community profile features
  → calculate relevance and health scores
  → select a diverse ranked list
  → generate factual explanations
  → return validated JSON
```

### 1. Hard eligibility filters

A candidate must meet all of these conditions:

- Public visibility and active lifecycle status.
- The member does not already belong to it.
- Available capacity: no cap, or `member_count < max_members`.
- Last activity within 60 days, inclusive, with no future activity timestamp.
- At least one feed post or at least five chat messages in the supplied 30-day aggregates.

Request-to-join Circles remain eligible. Discovery fallback never relaxes these filters.

### 2. Relevance and profile alignment

Let `T` be topic relevance and `P` be profile alignment:

```text
T = 0.65 × primary-topic match
  + 0.35 × Jaccard(member interests, Circle topics)

P = 0.35 × fraction of Circle members in the same industry
  + 0.25 × mean job-title-token Jaccard similarity
  + 0.20 × exact location match
  + 0.20 × format fit
```

Recognized taxonomy tags are included in Circle topics. Jaccard is intersection size divided by union size, with zero for two empty sets. Job-title tokenization removes a small set of generic words.

Circle location and user format preference are optional schema fields absent from the original data. No locations or preferences are fabricated. Without an explicit format preference, format fit is 1 for virtual, 0.5 for hybrid, and 0 for in-person: a weak accessibility prior. An explicit preference uses exact matching.

### 3. Health and welcoming signals

```text
H = 0.30 × exp(-days since activity / 30)
  + 0.30 × min(feed posts / 12, 1)
  + 0.15 × min(chat messages / 100, 1)
  + 0.15 × member-size fit
  + 0.10 × mean leader profile completeness

W = 0.60 × open-joining indicator
  + 0.40 × min(member count / 12, 1)
```

Size fit is 1 for 6–16 members; 0.5 for 3–5 or 17–30; and 0.2 otherwise. Leader completeness is a small operational proxy, not a certification of quality. Missing leaders contribute zero. Activity and popularity are capped to avoid unlimited boosts for large communities.

### 4. Personalized and discovery strategies

```text
With stated interests:
base = 0.60 T + 0.10 P + 0.30 H

Without stated interests:
base = 0.65 H + 0.20 W + 0.10 format fit + 0.05 P
```

`cold_start` is true when the member has neither interests nor memberships. Any member without stated interests uses discovery scoring, even if they have memberships or a partially completed profile. Existing memberships are used for exclusion and cold-start metadata, not for inferring interests.

### 5. Diversity and explanations

Greedy selection chooses the highest remaining:

```text
base score − 0.22 × maximum similarity to previously selected Circles
```

Similarity is the greater of topic-set Jaccard and a same-primary-topic indicator. At most two Circles per non-null primary topic can be returned. Null topics do not form a single shared category. Ties resolve by ascending Circle ID. The algorithm never pads the list with excluded duplicates to reach the limit.

Explanations reference actual shared topics, meeting format, and joining policy. Without an interest match, copy describes exploring an active community. No sensitive demographic traits, nearby locations, verified leader quality, or guaranteed acceptance are inferred.

## Database and seed data

### Supplied snapshot

| File | Records |
|---|---:|
| `data/users.json` | 100 |
| `data/circles.json` | 40 |
| `data/memberships.json` | 441 |
| `data/topics.json` | 22 |
| `data/activity.json` | 386 |

The source is synthetic and anchored to **September 21, 2026**. JSON records are preserved; import normalizes timestamps and relationships into SQLite.

### Schema

The complete executable DDL is in [schema.sql](schema.sql).

| Table | Purpose |
|---|---|
| `users` | Member profiles and optional meeting-format preference |
| `circles` | Circle details, lifecycle, visibility, capacity, and aggregate activity |
| `memberships` | Unique member/Circle pairs and leader/member roles |
| `topics` | Taxonomy with unique slugs and readable labels |
| `circle_topics` | Unique Circle/topic associations |
| `user_interests` | Unique member/topic associations |
| `activity_logs` | Feed posts, authors, timestamps, and engagement counts |
| `circle_tags` | Raw source tags, including tags outside the taxonomy |
| `dataset_metadata` | Snapshot reference time |

IDs and counters use INTEGER; completeness uses REAL constrained to 0–1; profile fields use nullable TEXT. Timestamps are canonical UTC TEXT at whole-second precision. Constraints enforce enum values, nonnegative counts, positive optional capacity, unique relationships, and foreign keys. A composite activity foreign key requires its author to belong to the Circle. Foreign keys are enabled on every connection.

| Index | Purpose |
|---|---|
| `circles_discovery(access, status, last_activity_at)` | Visibility/status equality followed by activity range filtering |
| Membership primary key `(user_id, circle_id)` | Already-joined exclusion |
| `memberships_circle_role(circle_id, role, user_id)` | Circle membership and leader lookup |
| `circle_topics_topic(topic_id, circle_id)` | Reverse topic lookup for candidate retrieval |
| `user_interests_topic(topic_id, user_id)` | Reverse interest lookup for future feature jobs |
| `activity_circle_time(circle_id, created_at)` | Activity-window queries and future aggregation |

Some indexes support future targeted reads; the current small-data ranker scans topic edges and rosters in batches. Capacity compares columns and is evaluated as a residual predicate.

### Normalization and aggregate authority

Memberships, taxonomy, interests, and activity are normalized. Member counts and activity counters remain denormalized read features. Supplied `member_count` is authoritative for capacity; the sampled membership roster need not contain every member. Supplied activity aggregates are authoritative for ranking; raw posts are retained without double-counting their activity.

The service does not refresh counters or reconcile memberships. The primary topic's association in `circle_topics` is maintained by the importer rather than a cross-table constraint.

### Manual seed and reset

Automatic seeding is sufficient for normal startup. To prepare a separate database:

```sh
python seed.py --db demo.sqlite3
```

Seeding refuses to overwrite an existing file. To reset the default demo, stop the server, back up or rename `circles.sqlite3`, and restart. Editing JSON does not update an existing database automatically. The importer builds a temporary database and atomically publishes it after successful insertion.

## Configuration

| Variable | Default | Behavior |
|---|---|---|
| `DATABASE_PATH` | `circles.sqlite3` in the project root | Alternate database file; relative overrides resolve from the process working directory |
| `CLOCK_MODE` | `snapshot` | `snapshot` uses the stored reference date; `realtime` uses current UTC |

macOS / Linux example:

```sh
DATABASE_PATH=demo.sqlite3 CLOCK_MODE=snapshot python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

PowerShell example:

```powershell
$env:DATABASE_PATH = "demo.sqlite3"
$env:CLOCK_MODE = "snapshot"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**Snapshot versus real time:** snapshot mode deliberately keeps this historical dataset reproducible. Real-time mode advances the activity cutoff, but does not refresh the imported 30-day counters. As the dataset ages, results can become empty. Use refreshed features before treating real-time output as current recommendations.

## Verification

Run the four scenario tests from the project root with `python -m unittest discover -s tests -v`. They build a temporary database from the supplied dataset and require no running server. The runnable smoke check below uses only Python's standard library against a running server. It checks the actual API and four planted scenarios; it is not a load test or a measure of real-member recommendation quality.

| User | Scenario | Expected outcome |
|---:|---|---|
| 42 | No interests, memberships, or completed profile | Nonempty discovery results and `cold_start=true` |
| 7 | Leadership and public speaking | Circles 5 and 6 in the top three |
| 15 | Negotiation and confidence | Negotiation in the top three; no more than two of Circles 10, 11, 12 |
| 23 | Promotion interests | Full Circle 20 and inactive Circle 21 absent; Circle 22 first |

With the server running in snapshot mode on port 8000, paste this into a Python shell or save it outside the application as a temporary verification script:

```python
import json
from urllib.request import urlopen

BASE = "http://127.0.0.1:8000"

def get(path):
    with urlopen(BASE + path, timeout=10) as response:
        return json.load(response)

results = {}
for user_id in range(1, 101):
    path = f"/recommendations/{user_id}?limit=50"
    payload = get(path)
    assert payload["recommendations"], user_id
    assert payload == get(path), f"Unstable result for {user_id}"
    ids = [row["circle_id"] for row in payload["recommendations"]]
    assert len(ids) == len(set(ids)), user_id
    results[user_id] = payload

def ids(user_id):
    return [row["circle_id"] for row in results[user_id]["recommendations"]]

assert results[42]["metadata"]["cold_start"] is True
assert results[42]["metadata"]["strategy"] == "discovery"
assert {5, 6}.issubset(ids(7)[:3])
assert {10, 11, 12}.intersection(ids(15)[:3])
assert 1 <= len({10, 11, 12}.intersection(ids(15))) <= 2
assert not {20, 21}.intersection(ids(23))
assert ids(23)[0] == 22
assert len(get("/demo/members")) == 100
print("All 100 members and four scenarios passed.")
```

Check installed dependency consistency with `python -m pip check`. For manual browser verification, confirm the initially empty picker, ascending IDs, name/interest search, keyboard selection, format filters, Circle details, and load-more behavior.

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `ERR_CONNECTION_REFUSED` | Start Uvicorn and keep its terminal open. Confirm the browser uses the same port. |
| `No module named app` | Run from the project root containing `app/`, not its parent or the `app/` directory itself. |
| `No module named fastapi` or `uvicorn` | Activate `.venv` or use its Python interpreter directly; install `requirements.txt`. |
| Address already in use | An application already occupies that port. Use another port or stop the existing server. |
| Search field is disabled / members unavailable | Check `/demo/members`, server logs, and browser console; reload the page after frontend changes. |
| Old dropdown or styling remains | Hard-refresh the page to reload cached CSS/JavaScript. |
| No recommendations | Confirm `CLOCK_MODE=snapshot`, select a member, and try All formats. Eligibility rules can legitimately produce fewer results. |
| Seed says database already exists | Choose a new `--db` path or stop the server and back up the existing database before resetting. |
| Database/schema errors after changing code | There are no automatic migrations; preserve the database and deliberately recreate the disposable demo from seeds if necessary. |
| In-person Circle has no location | The source does not supply Circle location. The UI asks members to confirm with the organizer. |
| `/favicon.ico` returns 404 | No favicon is supplied; this does not prevent the application from functioning. |

## Engineering decisions and production path

**Stack:** FastAPI supplies validation and OpenAPI; SQLite requires no database service; Python's built-in driver keeps SQL and connection behavior explicit. Plain HTML/CSS/JavaScript avoids a frontend build system. Requests use separate SQLite connections and consistent read transactions. The ranker performs a constant number of database queries, but those queries still read all relevant rosters and topic edges.

**Scope:** deterministic heuristics fit a small synthetic dataset and make decisions inspectable. The weights, size sweet spot, and inactivity threshold are product hypotheses. Industry composition, title tokens, leader completeness, and coarse topic clustering are imperfect proxies. A same-topic cap can suppress distinct communities; popularity can concentrate exposure. No offline relevance benchmark or production load benchmark has established optimality.

Before deploying beyond localhost:

1. Authenticate members and authorize access to each user's recommendations. Remove or restrict the demo member directory.
2. Add migrations, operational logging, monitoring, rate limiting, error handling for infrastructure failures, and automated regression tests.
3. Keep membership counts transactional and recheck capacity when joining; a recommendation does not reserve a seat.
4. Refresh rolling activity features using asynchronous jobs/events and reconcile late or inconsistent data.
5. Move to PostgreSQL as needed; use two-stage retrieval to select a bounded candidate set before ranking.
6. Evaluate pgvector/semantic retrieval only when it improves coverage; collaborative signals require sufficient interaction history.
7. Cache versioned recommendations in Redis with appropriate expiry and membership/profile invalidation; recheck eligibility before serving.
8. Evaluate accepted joins, participation, retention, reports, and exposure across new and established Circles—not clicks alone.

Names and photos are not used to infer demographic characteristics. Sparse member profiles still receive discovery recommendations. The goal is useful, explainable community discovery with realistic availability.

## Publishing the repository

Include the application source, all five JSON datasets, `schema.sql`, `seed.py`, `requirements.txt`, `.gitignore`, and this README. Exclude the virtual environment, local SQLite database, bytecode, Finder metadata, and caches; `.gitignore` covers these generated items. Keep any future credentials out of source control.

The application uses local static assets and relative API URLs. A downloaded copy runs independently after dependency installation and database initialization; it does not depend on the original developer's folders or a specific port.
