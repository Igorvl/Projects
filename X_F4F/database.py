# -*- coding: utf-8 -*-
"""
Database layer for X growth engine.
Supports both SQLite (for local Windows dev) and PostgreSQL (for ESXi Linux server).
"""

import sqlite3
import os
import json
import datetime
from config import SQLITE_PATH, DB_TYPE, DATABASE_URL, MIN_SCORE_THRESHOLD

def get_connection():
    """Returns database connection."""
    if DB_TYPE == "sqlite":
        conn = sqlite3.connect(SQLITE_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn
    else:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Initializes schema and tables."""
    conn = get_connection()
    cur = conn.cursor()

    if DB_TYPE == "sqlite":
        # Candidates table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                name TEXT,
                bio TEXT,
                url TEXT,
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                ratio REAL DEFAULT 0.0,
                score INTEGER DEFAULT 0,
                score_breakdown TEXT,
                source TEXT,
                status TEXT DEFAULT 'discovered', -- discovered, queued, followed, mutual, unqueued, ignored, unfollowed, failed_unfollow
                unfollow_attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Auto-migrate SQLite if unfollow_attempts column is missing
        try:
            cur.execute("ALTER TABLE candidates ADD COLUMN unfollow_attempts INTEGER DEFAULT 0")
        except Exception:
            pass

        # Action history (follows, unfollows, detections)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS actions_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_username TEXT NOT NULL,
                action_type TEXT NOT NULL, -- follow, unfollow, check_mutual
                success INTEGER DEFAULT 1,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Daily stats aggregate
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                candidates_found INTEGER DEFAULT 0,
                follows_sent INTEGER DEFAULT 0,
                mutual_received INTEGER DEFAULT 0,
                unfollows_done INTEGER DEFAULT 0,
                likes_sent INTEGER DEFAULT 0,
                list_adds_sent INTEGER DEFAULT 0
            )
        """)

    else:
        # Postgres dialect
        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                name VARCHAR(255),
                bio TEXT,
                url TEXT,
                followers_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                ratio REAL DEFAULT 0.0,
                score INTEGER DEFAULT 0,
                score_breakdown JSONB,
                source VARCHAR(128),
                status VARCHAR(32) DEFAULT 'discovered',
                unfollow_attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                last_active TIMESTAMP,
                updated_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS actions_history (
                id SERIAL PRIMARY KEY,
                candidate_username VARCHAR(64) NOT NULL,
                action_type VARCHAR(32) NOT NULL,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                candidates_found INTEGER DEFAULT 0,
                follows_sent INTEGER DEFAULT 0,
                mutual_received INTEGER DEFAULT 0,
                unfollows_done INTEGER DEFAULT 0
            );
        """)

        # Auto-migrate Postgres if unfollow_attempts is missing
        try:
            cur.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS unfollow_attempts INTEGER DEFAULT 0;")
        except Exception:
            pass

    conn.commit()
    conn.close()

def upsert_candidate(data: dict):
    """Inserts or updates candidate profile."""
    conn = get_connection()
    cur = conn.cursor()
    
    breakdown_json = json.dumps(data.get("score_breakdown", {}), ensure_ascii=False)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    last_active = data.get("last_active")
    
    if DB_TYPE == "sqlite":
        cur.execute("""
            INSERT INTO candidates (
                username, name, bio, url, followers_count, following_count,
                ratio, score, score_breakdown, source, status, last_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                name=excluded.name,
                bio=excluded.bio,
                url=excluded.url,
                followers_count=excluded.followers_count,
                following_count=excluded.following_count,
                ratio=excluded.ratio,
                score=excluded.score,
                score_breakdown=excluded.score_breakdown,
                last_active=COALESCE(excluded.last_active, candidates.last_active),
                -- НЕ перетираем статус у followed/mutual/unfollowed/failed_unfollow — бот не должен подписываться дважды
                status=CASE
                    WHEN candidates.status IN ('followed', 'mutual', 'unfollowed', 'failed_unfollow') THEN candidates.status
                    ELSE excluded.status
                END,
                updated_at=excluded.updated_at
        """, (
            data["username"].lower().replace("@", ""),
            data.get("name", ""),
            data.get("bio", ""),
            data.get("url", ""),
            data.get("followers_count", 0),
            data.get("following_count", 0),
            data.get("ratio", 0.0),
            data.get("score", 0),
            breakdown_json,
            data.get("source", ""),
            data.get("status", "discovered"),
            last_active,
            now
        ))
    else:
        # PostgreSQL — placeholder %s, score_breakdown как JSONB
        cur.execute("""
            INSERT INTO candidates (
                username, name, bio, url, followers_count, following_count,
                ratio, score, score_breakdown, source, status, last_active, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            ON CONFLICT(username) DO UPDATE SET
                name=EXCLUDED.name,
                bio=EXCLUDED.bio,
                url=EXCLUDED.url,
                followers_count=EXCLUDED.followers_count,
                following_count=EXCLUDED.following_count,
                ratio=EXCLUDED.ratio,
                score=EXCLUDED.score,
                score_breakdown=EXCLUDED.score_breakdown::jsonb,
                last_active=COALESCE(EXCLUDED.last_active, candidates.last_active),
                -- НЕ перетираем статус у followed/mutual/unfollowed/failed_unfollow
                status=CASE
                    WHEN candidates.status IN ('followed', 'mutual', 'unfollowed', 'failed_unfollow') THEN candidates.status
                    ELSE EXCLUDED.status
                END,
                updated_at=EXCLUDED.updated_at
        """, (
            data["username"].lower().replace("@", ""),
            data.get("name", ""),
            data.get("bio", ""),
            data.get("url", ""),
            data.get("followers_count", 0),
            data.get("following_count", 0),
            data.get("ratio", 0.0),
            data.get("score", 0),
            breakdown_json,
            data.get("source", ""),
            data.get("status", "discovered"),
            last_active,
            now
        ))
    conn.commit()
    conn.close()

def get_queue_count(min_score: int = None) -> int:
    """Returns total number of candidates ready to follow."""
    if min_score is None:
        min_score = MIN_SCORE_THRESHOLD
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cur.execute(f"SELECT COUNT(*) FROM candidates WHERE status = 'queued' AND score >= {ph}", (min_score,))
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_candidates_for_follow(limit: int = 10, min_score: int = None):
    """Retrieves highest scored candidates ready to follow."""
    if min_score is None:
        min_score = MIN_SCORE_THRESHOLD
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cur.execute(f"""
        SELECT * FROM candidates 
        WHERE status = 'queued' AND score >= {ph} 
        ORDER BY score DESC, ratio DESC 
        LIMIT {ph}
    """, (min_score, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_existing_candidate_usernames() -> set:
    """Returns set of all lowercase usernames already tracked in candidates database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT LOWER(username) FROM candidates")
    existing = {r[0] for r in cur.fetchall()}
    conn.close()
    return existing

def log_action(username: str, action_type: str, success: bool = True, error: str = ""):
    """Logs action taken and updates daily stats."""
    conn = get_connection()
    cur = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    ph = "?" if DB_TYPE == "sqlite" else "%s"  # placeholder по типу БД

    cur.execute(f"""
        INSERT INTO actions_history (candidate_username, action_type, success, error_message)
        VALUES ({ph}, {ph}, {ph}, {ph})
    """, (username, action_type, 1 if success else 0, error))

    cur.execute(f"""
        INSERT INTO daily_stats (date, follows_sent, mutual_received, unfollows_done)
        VALUES ({ph}, 0, 0, 0)
        ON CONFLICT(date) DO NOTHING
    """, (today,))

    if action_type == "follow" and success:
        if error != "already_following":
            cur.execute(f"UPDATE daily_stats SET follows_sent = follows_sent + 1 WHERE date = {ph}", (today,))
        cur.execute(f"UPDATE candidates SET status = 'followed', updated_at = CURRENT_TIMESTAMP WHERE username = {ph}", (username,))
    elif action_type == "unfollow" and success:
        cur.execute(f"UPDATE daily_stats SET unfollows_done = unfollows_done + 1 WHERE date = {ph}", (today,))
        cur.execute(f"UPDATE candidates SET status = 'unfollowed', updated_at = CURRENT_TIMESTAMP WHERE username = {ph}", (username,))
    elif action_type == "unfollow" and not success:
        cur.execute(f"""
            UPDATE candidates 
            SET unfollow_attempts = COALESCE(unfollow_attempts, 0) + 1,
                status = CASE WHEN COALESCE(unfollow_attempts, 0) + 1 >= 5 THEN 'failed_unfollow' ELSE status END
            WHERE username = {ph}
        """, (username,))
        cur.execute(f"SELECT unfollow_attempts, status FROM candidates WHERE username = {ph}", (username,))
        row = cur.fetchone()
        attempts = row[0] if row else 1
        curr_status = row[1] if row else 'followed'
        if curr_status == 'failed_unfollow':
            print(f"  [Follower] ⚠️ @{username} reached {attempts}/5 failed unfollow attempts -> marked as 'failed_unfollow'. Bot will not touch this account anymore.")
        else:
            print(f"  [Follower] Unfollow attempt {attempts}/5 failed for @{username}.")
    elif action_type == "mutual":
        cur.execute(f"UPDATE daily_stats SET mutual_received = mutual_received + 1 WHERE date = {ph}", (today,))
        cur.execute(f"UPDATE candidates SET status = 'mutual', updated_at = CURRENT_TIMESTAMP WHERE username = {ph}", (username,))
    elif action_type == "like" and success:
        cur.execute(f"UPDATE daily_stats SET likes_sent = likes_sent + 1 WHERE date = {ph}", (today,))
    elif action_type == "list_add" and success:
        cur.execute(f"UPDATE daily_stats SET list_adds_sent = COALESCE(list_adds_sent, 0) + 1 WHERE date = {ph}", (today,))

    conn.commit()
    conn.close()

def get_today_list_adds() -> int:
    """Gets count of list adds executed today to enforce DAILY_LIST_ADD_LIMIT."""
    conn = get_connection()
    cur = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cur.execute(f"SELECT COALESCE(list_adds_sent, 0) FROM daily_stats WHERE date = {ph}", (today,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def get_candidates_for_list_bombing(limit: int = 10, min_score: int = 50) -> list:
    """
    Retrieves qualified candidates (status 'queued' or 'followed') who have NOT yet
    been added to an ego list.
    """
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cur.execute(f"""
        SELECT c.* FROM candidates c
        WHERE c.status IN ('queued', 'followed')
          AND c.score >= {ph}
          AND c.username NOT IN (
              SELECT candidate_username FROM actions_history 
              WHERE action_type = 'list_add' AND success = 1
          )
        ORDER BY c.score DESC, c.ratio DESC
        LIMIT {ph}
    """, (min_score, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", SQLITE_PATH)
