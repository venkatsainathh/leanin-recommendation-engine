# Lean In Circle Recommendation Engine

## System overview

FastAPI reads members, Circles, topics, and activity from SQLite. A deterministic pipeline filters candidates, scores them, adds variety, and explains each recommendation.

The website (`/static/index.html`, also served at `/`) helps nontechnical stakeholders search member profiles and browse readable recommendations. The top-right **Developer API** button opens `/docs`, where engineers can call `/recommendations/{user_id}` and inspect JSON and scoring details. Browser network tools show request timing.

## Recommendations and edge cases

The engine excludes already-joined, full, unlisted, archived, and inactive Circles. Activity must fall within 60 days, with at least one post or five chat messages in the supplied 30-day window.

Personalized ranking balances interests (60%), profile alignment (10%), and community health (30%). Signals include industry, meeting format, recent posts, and chat volume. Missing locations are not guessed. Without stated interests, discovery favors healthy, open communities; leader completeness provides a small boost. Topic-overlap penalties and a two-per-topic cap limit repetition. Each result includes a factual, plain-language explanation.

**Why 10 results?** It gives a manageable shortlist and limits response size. Clients can request 1–50. All eligible candidates are still scored, so this does not guarantee sub-50ms latency. The website displays six results at a time.

## Tradeoffs

For a 3–4 hour scope, weighted rules offer straightforward setup, debugging, and explanations without training data or model infrastructure. Request-time scoring avoids maintaining cached feeds and reflects committed capacity changes. Activity counters remain static; the demo uses the dataset’s September 21, 2026 reference date for repeatable results.

## Production scale

- Move to PostgreSQL. Retrieve roughly 200 candidates using indexed filters and evaluated pgvector or Elasticsearch search, then rerank. Benchmark latency rather than assume sub-10ms retrieval.
- Cache onboarding candidates and features in Redis. Use Kafka/SQS workers to refresh activity and membership data.
- Add authentication, regression tests, monitoring, and transactional capacity checks when joining.
- Track accepted joins and sustained participation; tune weights through A/B tests while monitoring community exposure.
