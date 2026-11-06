# Lean In Circle Recommendation Engine — Technical Design

## How the service works

FastAPI reads a member’s interests, memberships and Circle activity from SQLite. The demo at `/static/index.html` lets reviewers select a member and see why each Circle ranks. The top-right **Developer API** button opens Swagger at `/docs`. Run `GET /recommendations/{user_id}` there to inspect each rank, score breakdown and member-facing explanation.

## How a Circle makes the list

1. **Check eligibility.** Keep public, active Circles with room to join. Exclude existing memberships. A Circle needs activity within 60 days **and** either at least one post or at least five chat messages in the supplied 30-day window. A perfect topic match can still fail this check.
2. **Score the fit.** I chose **60% topic match, 10% profile fit and 30% community health** as starting weights. Members’ stated interests are the clearest signal: matching a Circle’s primary topic counts more than matching a secondary topic. Recent activity, posts and chat volume help distinguish active groups. Industry, job role and meeting format carry less weight because profiles can be incomplete. The engine never guesses a missing location.
3. **Handle cold start.** Without stated interests, favor healthy Circles with open enrollment and an established group. Leader profile completeness adds a small health boost. Exact score ties go to the lower Circle ID, so repeated requests give the same order for the same data and reference date.
4. **Add variety and explain.** As each Circle is selected, similar topics receive a penalty. A separate cap allows at most two results per primary topic. Each explanation names shared interests when available and tells the member how the Circle meets and how to join.

The API defaults to `limit=10` for a manageable shortlist and a small response. Clients can request 1–50 results. Every eligible Circle is scored. The website displays six cards at a time.

## Engineering tradeoffs

For this short assignment, explicit rules make each result easy to explain and test without training data or model inference. Scoring on request reflects saved seat counts without maintaining feeds. Activity totals come from a snapshot: the demo measures recency against September 21, 2026, so reviewers can reproduce the results later.

## What I would add for production scale

- Use indexed PostgreSQL filters and pgvector or Elasticsearch to retrieve about 200 eligible Circles before ranking. Benchmark latency and compare results with the full ranking to catch missed matches.
- Cache onboarding lists, topics and health scores in Redis. Process post, chat and join events through Kafka or SQS workers. At join time, reserve a seat in the membership transaction with a conditional update to prevent overbooking.
- A/B test weight changes against join conversion and participation after 30 and 90 days. Track which Circles receive exposure.
