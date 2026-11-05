"""Import the provided synthetic dataset, preserving its planted scenarios unchanged."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.database import DEFAULT_DB, ROOT, connect

SNAPSHOT_AT = '2026-09-21T00:00:00Z'  # Reference date of the supplied dataset.


def seed(path: Path = DEFAULT_DB, data_dir: Path = ROOT / 'data') -> None:
    """Build atomically, refusing to replace an existing database."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f'{path} already exists; choose a new --db path.')
    data = {name: json.loads((data_dir / f'{name}.json').read_text())
            for name in ('users', 'topics', 'circles', 'memberships', 'activity')}
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.sqlite3')
    os.close(fd)
    connection = connect(Path(temporary))
    try:
        connection.executescript((ROOT / 'schema.sql').read_text())
        with connection:
            def insert(table: str, row: dict) -> None:
                # Identifiers originate only from the fixed importer, never API inputs.
                row = {key: datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                       if key.endswith('_at') else value for key, value in row.items()}
                keys = ','.join(row)
                marks = ','.join('?' for _ in row)
                connection.execute(f'INSERT INTO {table} ({keys}) VALUES ({marks})', tuple(row.values()))

            insert('dataset_metadata', {'key': 'snapshot_at', 'value': SNAPSHOT_AT})
            topic_ids = {t['slug']: t['id'] for t in data['topics']}
            for topic in data['topics']:
                insert('topics', topic)
            for raw in data['users']:
                user = raw.copy()
                interests = user.pop('topic_interests')
                insert('users', user)
                for slug in set(interests):
                    insert('user_interests', {'user_id': user['id'], 'topic_id': topic_ids[slug]})
            for raw in data['circles']:
                circle = raw.copy()
                primary = circle.pop('topic')
                tags = circle.pop('tags')
                circle['primary_topic_id'] = topic_ids[primary] if primary else None
                insert('circles', circle)
                for slug in sorted(set(tags + ([primary] if primary else []))):
                    insert('circle_tags', {'circle_id': circle['id'], 'tag': slug})
                    if slug in topic_ids:
                        insert('circle_topics', {'circle_id': circle['id'], 'topic_id': topic_ids[slug]})
            for membership in data['memberships']:
                insert('memberships', membership)
            for activity in data['activity']:
                insert('activity_logs', activity)
        connection.close()
        # Hard-link publication is atomic and fails if another process created the path.
        os.link(temporary, path)
    finally:
        connection.close()
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    seed(args.db)
    print(f'Seeded {args.db} (snapshot {SNAPSHOT_AT})')
