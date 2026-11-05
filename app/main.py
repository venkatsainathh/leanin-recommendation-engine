"""Read-only local API. Production authentication belongs at the identity boundary."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import DEFAULT_DB, ROOT, connect
from app.ranking import recommend, timestamp
from seed import seed


class Components(BaseModel):
    topic: float
    profile: float
    health: float
    welcome: float


class Recommendation(BaseModel):
    rank: int
    circle_id: int
    name: str
    description: str | None
    format: Literal['virtual', 'hybrid', 'in_person']
    location: str | None
    join_policy: Literal['open', 'request']
    topics: list[str]
    member_count: int
    available_seats: int | None
    score: float
    base_score: float
    diversity_penalty: float
    components: Components
    explanation: str


class Metadata(BaseModel):
    algorithm_version: str
    as_of: str
    clock_mode: str
    strategy: str
    cold_start: bool
    eligible_count: int
    returned_count: int
    requested_limit: int
    inactivity_days: int
    diversity_max_per_primary_topic: int


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[Recommendation]
    metadata: Metadata


def create_app(db_path: Path | None = None, clock_mode: str | None = None) -> FastAPI:
    database = db_path or Path(os.environ.get('DATABASE_PATH', str(DEFAULT_DB)))
    mode = clock_mode or os.environ.get('CLOCK_MODE', 'snapshot')
    if mode not in {'snapshot', 'realtime'}:
        raise ValueError('CLOCK_MODE must be snapshot or realtime')

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if not database.exists():
            try:
                seed(database)
            except FileExistsError:
                pass  # Another worker atomically published the same initial dataset.
        yield

    application = FastAPI(title='Lean In Circle Recommendations', version='1.0.0', lifespan=lifespan)

    application.mount('/static', StaticFiles(directory=ROOT / 'app' / 'static'), name='static')

    @application.get('/', include_in_schema=False)
    def home():
        """The local, buildless member experience uses the same recommendation API."""
        return FileResponse(ROOT / 'app' / 'static' / 'index.html')

    @application.get('/demo/members', tags=['Demo'])
    def demo_members():
        """Synthetic profile picker. Remove this directory before a real deployment."""
        db = connect(database)
        try:
            db.execute('BEGIN')
            members = [dict(row) for row in db.execute(
                'SELECT id,first_name,last_name FROM users ORDER BY id')]
            interests = {}
            for row in db.execute('SELECT ui.user_id,t.label FROM user_interests ui '
                                  'JOIN topics t ON t.id=ui.topic_id ORDER BY t.label'):
                interests.setdefault(row['user_id'], []).append(row['label'])
            return [dict(member, interests=interests.get(member['id'], [])) for member in members]
        finally:
            db.close()

    @application.get('/recommendations/{user_id}', response_model=RecommendationResponse)
    def recommendations(user_id: Annotated[int, ApiPath(gt=0)],
                        limit: Annotated[int, Query(ge=1, le=50)] = 10):
        db = connect(database)
        try:
            db.execute('BEGIN')
            reference = (timestamp(db.execute("SELECT value FROM dataset_metadata WHERE key='snapshot_at'")
                                   .fetchone()[0]) if mode == 'snapshot' else datetime.now(timezone.utc))
            try:
                result = recommend(db, user_id, limit, reference)
            except KeyError:
                raise HTTPException(status_code=404, detail='User not found') from None
            result['metadata']['clock_mode'] = mode
            return result
        finally:
            db.close()

    return application


app = create_app()
