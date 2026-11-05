PRAGMA foreign_keys = ON;
CREATE TABLE dataset_metadata (
    key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    has_photo INTEGER NOT NULL CHECK (has_photo IN (0,1)),
    bio TEXT, job_title TEXT, company TEXT, industry TEXT, location TEXT,
    preferred_format TEXT CHECK (preferred_format IN ('virtual','hybrid','in_person')),
    joined_at TEXT NOT NULL,
    profile_completeness REAL NOT NULL CHECK (profile_completeness BETWEEN 0 AND 1)
);
CREATE TABLE topics (
    id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL, domain TEXT NOT NULL
);
CREATE TABLE circles (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
    description TEXT, cover_image_url TEXT,
    primary_topic_id INTEGER REFERENCES topics(id),
    format TEXT NOT NULL CHECK (format IN ('virtual','hybrid','in_person')),
    location TEXT,
    access TEXT NOT NULL CHECK (access IN ('public','unlisted')),
    join_policy TEXT NOT NULL CHECK (join_policy IN ('open','request')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    max_members INTEGER CHECK (max_members > 0),
    member_count INTEGER NOT NULL CHECK (member_count >= 0),
    created_at TEXT NOT NULL, last_activity_at TEXT NOT NULL,
    feed_posts_30d INTEGER NOT NULL CHECK (feed_posts_30d >= 0),
    chat_messages_30d INTEGER NOT NULL CHECK (chat_messages_30d >= 0)
);
CREATE TABLE memberships (
    user_id INTEGER NOT NULL REFERENCES users(id),
    circle_id INTEGER NOT NULL REFERENCES circles(id),
    role TEXT NOT NULL CHECK (role IN ('member','leader')),
    joined_at TEXT NOT NULL, PRIMARY KEY (user_id, circle_id)
);
CREATE TABLE circle_topics (
    circle_id INTEGER NOT NULL REFERENCES circles(id),
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    PRIMARY KEY (circle_id, topic_id)
);
-- Preserve non-taxonomy tags without silently turning them into stated topics.
CREATE TABLE circle_tags (
    circle_id INTEGER NOT NULL REFERENCES circles(id), tag TEXT NOT NULL,
    PRIMARY KEY (circle_id, tag)
);
CREATE TABLE user_interests (
    user_id INTEGER NOT NULL REFERENCES users(id),
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    PRIMARY KEY (user_id, topic_id)
);
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY,
    circle_id INTEGER NOT NULL REFERENCES circles(id),
    author_user_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL, created_at TEXT NOT NULL,
    reaction_count INTEGER NOT NULL CHECK (reaction_count >= 0),
    comment_count INTEGER NOT NULL CHECK (comment_count >= 0),
    save_count INTEGER NOT NULL CHECK (save_count >= 0),
    FOREIGN KEY (author_user_id, circle_id) REFERENCES memberships(user_id, circle_id)
);
CREATE INDEX circles_discovery ON circles(access, status, last_activity_at);
CREATE INDEX memberships_circle_role ON memberships(circle_id, role, user_id);
CREATE INDEX circle_topics_topic ON circle_topics(topic_id, circle_id);
CREATE INDEX user_interests_topic ON user_interests(topic_id, user_id);
CREATE INDEX activity_circle_time ON activity_logs(circle_id, created_at);
