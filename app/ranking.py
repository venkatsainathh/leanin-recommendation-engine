"""Deterministic, inspectable ranking without inferred sensitive attributes."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import math
import re
import sqlite3

VERSION = 'heuristic-v1'
INACTIVITY_DAYS = 60


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps must include a timezone')
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def jaccard(left: set, right: set) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def role_tokens(title: str | None) -> set[str]:
    return set(re.findall(r'[a-z]+', (title or '').lower())) - {'senior', 'junior', 'the', 'of'}


def normalized(value: str | None) -> str:
    return (value or '').strip().casefold()


def recommend(db: sqlite3.Connection, user_id: int, limit: int,
              as_of: datetime) -> dict:
    user_row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if user_row is None:
        raise KeyError(user_id)
    user = dict(user_row)
    interests = {r[0] for r in db.execute(
        'SELECT topic_id FROM user_interests WHERE user_id=?', (user_id,))}
    membership_count = db.execute('SELECT COUNT(*) FROM memberships WHERE user_id=?',
                                  (user_id,)).fetchone()[0]
    cold_start = not interests and membership_count == 0
    # No stated interests => discovery weights, even if the profile is partly filled.
    strategy = 'discovery' if not interests else 'personalized'
    cutoff = iso(as_of - timedelta(days=INACTIVITY_DAYS))
    candidates = [dict(r) for r in db.execute('''
        SELECT c.* FROM circles c
        WHERE c.access='public' AND c.status='active'
          AND c.last_activity_at >= ? AND c.last_activity_at <= ?
          AND (c.feed_posts_30d > 0 OR c.chat_messages_30d >= 5)
          AND (c.max_members IS NULL OR c.member_count < c.max_members)
          AND NOT EXISTS (SELECT 1 FROM memberships m
                          WHERE m.user_id=? AND m.circle_id=c.id)
    ''', (cutoff, iso(as_of), user_id))]
    # Constant query count. Full feature scans are deliberate for this 40-Circle snapshot.
    topics = {r['id']: r['label'] for r in db.execute('SELECT id,label FROM topics')}
    circle_topics = defaultdict(set)
    for row in db.execute('SELECT circle_id,topic_id FROM circle_topics'):
        circle_topics[row['circle_id']].add(row['topic_id'])
    peers = defaultdict(list)
    for row in db.execute('''SELECT m.circle_id,m.role,u.industry,u.job_title,
                            u.profile_completeness FROM memberships m
                            JOIN users u ON u.id=m.user_id'''):
        peers[row['circle_id']].append(dict(row))
    scored = []
    for circle in candidates:
        cid = circle['id']
        ct = circle_topics[cid]
        overlap = interests & ct
        topic_score = .65 * float(circle['primary_topic_id'] in interests) + .35 * jaccard(interests, ct)
        members = peers[cid]
        industry = sum(bool(user['industry']) and normalized(user['industry']) == normalized(m['industry'])
                       for m in members) / max(1, len(members))
        role = sum(jaccard(role_tokens(user['job_title']), role_tokens(m['job_title']))
                   for m in members) / max(1, len(members))
        # Circle location is absent from the source: never substitute a leader's city.
        local = bool(user['location'] and circle['location'] and
                     normalized(user['location']) == normalized(circle['location']))
        format_fit = (float(circle['format'] == user['preferred_format'])
                      if user['preferred_format'] else
                      {'virtual': 1.0, 'hybrid': .5, 'in_person': 0.0}[circle['format']])
        profile = .35 * industry + .25 * role + .20 * float(local) + .20 * format_fit
        age = max(0, (as_of - timestamp(circle['last_activity_at'])).total_seconds() / 86400)
        freshness = math.exp(-age / 30)
        posts = min(circle['feed_posts_30d'] / 12, 1)
        chat = min(circle['chat_messages_30d'] / 100, 1)
        count = circle['member_count']
        size = 1.0 if 6 <= count <= 16 else .5 if 3 <= count <= 30 else .2
        leaders = [m['profile_completeness'] for m in members if m['role'] == 'leader']
        leader = sum(leaders) / len(leaders) if leaders else 0
        # Completeness is a small operational proxy, never proof of leadership quality.
        health = .30 * freshness + .30 * posts + .15 * chat + .15 * size + .10 * leader
        welcome = .6 * float(circle['join_policy'] == 'open') + .4 * min(count / 12, 1)
        base = (.60 * topic_score + .10 * profile + .30 * health if interests else
                .65 * health + .20 * welcome + .10 * format_fit + .05 * profile)
        scored.append({'circle': circle, 'topics': ct, 'overlap': overlap, 'base': base,
                       'components': {'topic': topic_score, 'profile': profile,
                                      'health': health, 'welcome': welcome}})

    # Greedy maximum-marginal-relevance: penalize repeated niches and cap a primary
    # topic at two results. Null topics are not one shared cluster. Never backfill
    # excluded duplicates just to reach limit.
    selected = []
    primary_counts = Counter()
    remaining = scored.copy()
    while remaining and len(selected) < limit:
        choices = []
        for item in remaining:
            primary = item['circle']['primary_topic_id']
            if primary is not None and primary_counts[primary] >= 2:
                continue
            similarity = max((max(jaccard(item['topics'], old['topics']),
                                  float(primary is not None and primary == old['circle']['primary_topic_id']))
                              for old in selected), default=0)
            penalty = .22 * similarity
            choices.append((item['base'] - penalty, item, penalty))
        if not choices:
            break
        score, best, penalty = max(choices, key=lambda choice: (choice[0], -choice[1]['circle']['id']))
        best['score'], best['penalty'] = score, penalty
        selected.append(best)
        primary_counts[best['circle']['primary_topic_id']] += 1
        remaining.remove(best)

    results = []
    for rank, item in enumerate(selected, 1):
        circle = item['circle']
        if item['overlap']:
            labels = [topics[t] for t in sorted(item['overlap'])]
            reason = 'You share interests in ' + ' and '.join(labels[:2]) + '.'
        else:
            reason = 'An active community to explore as you grow your leadership journey.'
        reason += {'virtual': ' It meets virtually.',
                   'hybrid': ' It offers a hybrid meeting format.',
                   'in_person': ' It meets in person; check the meeting location.'}[circle['format']]
        if circle['join_policy'] == 'request':
            reason += ' You can request to join.'
        else:
            reason += ' It is open to new members.'
        results.append({'rank': rank, 'circle_id': circle['id'], 'name': circle['name'],
                        'description': circle['description'], 'format': circle['format'],
                        'location': circle['location'], 'join_policy': circle['join_policy'],
                        'topics': [topics[t] for t in sorted(item['topics'])],
                        'member_count': circle['member_count'],
                        'available_seats': None if circle['max_members'] is None else
                        circle['max_members'] - circle['member_count'],
                        'score': round(item['score'], 6), 'base_score': round(item['base'], 6),
                        'diversity_penalty': round(item['penalty'], 6),
                        'components': {k: round(v, 6) for k, v in item['components'].items()},
                        'explanation': reason})
    return {'user_id': user_id, 'recommendations': results,
            'metadata': {'algorithm_version': VERSION, 'as_of': iso(as_of),
                         'strategy': strategy, 'cold_start': cold_start,
                         'eligible_count': len(candidates), 'returned_count': len(results),
                         'requested_limit': limit, 'inactivity_days': INACTIVITY_DAYS,
                         'diversity_max_per_primary_topic': 2}}
