# -*- coding: utf-8 -*-
"""
Database layer for X growth engine.
Supports both SQLite (for local Windows dev) and PostgreSQL (for ESXi Linux server).
"""

import sqlite3
import os
import json
import datetime
import random
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
                followed_at TIMESTAMP,
                nudge_sent INTEGER DEFAULT 0,
                list_add_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Auto-migrate SQLite if columns are missing
        for col, col_def in [
            ("unfollow_attempts", "INTEGER DEFAULT 0"),
            ("followed_at", "TIMESTAMP"),
            ("nudge_sent", "INTEGER DEFAULT 0"),
            ("list_add_sent", "INTEGER DEFAULT 0")
        ]:
            try:
                cur.execute(f"ALTER TABLE candidates ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        # Backfill followed_at for existing followed users
        cur.execute("UPDATE candidates SET followed_at = updated_at WHERE status = 'followed' AND followed_at IS NULL")

        # Action history (follows, unfollows, detections)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS actions_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_username TEXT NOT NULL,
                action_type TEXT NOT NULL, -- follow, unfollow, check_mutual, nudge_like, list_add
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

        # Discovery Engine 2.0: Source tracking & cooldown table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sources_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_identifier TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL, -- donor_likes, donor_followers, search, dynamic_donor
                last_scraped_at TIMESTAMP,
                total_evaluated INTEGER DEFAULT 0,
                leads_yielded INTEGER DEFAULT 0,
                cooldown_hours INTEGER DEFAULT 48,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Dynamic donors discovered via Snowball network graph & Peer seeds
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_donors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                discovered_from TEXT,
                followers_count INTEGER DEFAULT 0,
                donor_type TEXT DEFAULT 'donor', -- 'donor' (studio) or 'peer_seed' (super-engager)
                status TEXT DEFAULT 'active', -- active, exhausted, invalid
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    else:
        # Postgres dialect
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_donors (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                discovered_from VARCHAR(64),
                followers_count INTEGER DEFAULT 0,
                donor_type VARCHAR(32) DEFAULT 'donor',
                status VARCHAR(32) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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
                followed_at TIMESTAMP,
                nudge_sent INTEGER DEFAULT 0,
                list_add_sent INTEGER DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS sources_tracking (
                id SERIAL PRIMARY KEY,
                source_identifier VARCHAR(128) UNIQUE NOT NULL,
                source_type VARCHAR(64) NOT NULL,
                last_scraped_at TIMESTAMP,
                total_evaluated INTEGER DEFAULT 0,
                leads_yielded INTEGER DEFAULT 0,
                cooldown_hours INTEGER DEFAULT 48,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS dynamic_donors (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                discovered_from VARCHAR(64),
                followers_count INTEGER DEFAULT 0,
                status VARCHAR(32) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Auto-migrate Postgres if columns are missing
        for col, col_def in [
            ("unfollow_attempts", "INTEGER DEFAULT 0"),
            ("followed_at", "TIMESTAMP"),
            ("nudge_sent", "INTEGER DEFAULT 0"),
            ("list_add_sent", "INTEGER DEFAULT 0")
        ]:
            try:
                cur.execute(f"ALTER TABLE candidates ADD COLUMN IF NOT EXISTS {col} {col_def};")
            except Exception:
                pass

        cur.execute("UPDATE candidates SET followed_at = updated_at WHERE status = 'followed' AND followed_at IS NULL;")

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
        cur.execute(f"UPDATE candidates SET status = 'followed', followed_at = COALESCE(followed_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE username = {ph}", (username,))
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
    elif action_type == "nudge_like" and success:
        cur.execute(f"UPDATE daily_stats SET likes_sent = likes_sent + 1 WHERE date = {ph}", (today,))
        cur.execute(f"UPDATE candidates SET nudge_sent = 1, updated_at = CURRENT_TIMESTAMP WHERE username = {ph}", (username,))
    elif action_type == "like" and success:
        cur.execute(f"UPDATE daily_stats SET likes_sent = likes_sent + 1 WHERE date = {ph}", (today,))
    elif action_type == "list_add" and success:
        cur.execute(f"UPDATE daily_stats SET list_adds_sent = COALESCE(list_adds_sent, 0) + 1 WHERE date = {ph}", (today,))
        cur.execute(f"UPDATE candidates SET list_add_sent = 1, updated_at = CURRENT_TIMESTAMP WHERE username = {ph}", (username,))

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

def get_candidates_for_nudge(days: int = 3, limit: int = 5) -> list:
    """
    Returns candidates followed N+ days ago (Day 3 Nudge) who haven't received
    a second-wave nudge like yet and haven't followed back.
    """
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(f"""
        SELECT * FROM candidates
        WHERE status = 'followed'
          AND COALESCE(nudge_sent, 0) = 0
          AND COALESCE(followed_at, updated_at) <= {ph}
        ORDER BY score DESC, COALESCE(followed_at, updated_at) ASC
        LIMIT {ph}
    """, (cutoff, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_candidates_for_funnel_list_add(days: int = 4, limit: int = 5) -> list:
    """
    Returns candidates followed N+ days ago (Day 4 Ego-List) who haven't received
    a list addition yet and haven't followed back.
    """
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(f"""
        SELECT * FROM candidates
        WHERE status = 'followed'
          AND COALESCE(list_add_sent, 0) = 0
          AND COALESCE(followed_at, updated_at) <= {ph}
        ORDER BY score DESC, COALESCE(followed_at, updated_at) ASC
        LIMIT {ph}
    """, (cutoff, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

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
def record_source_scrape(source_identifier: str, source_type: str, evaluated_count: int, leads_yielded: int, cooldown_hours: int = 48):
    """Records that a source was scraped, updates historical lead yield and resets cooldown timer."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if DB_TYPE == "sqlite":
        cur.execute("""
            INSERT INTO sources_tracking (source_identifier, source_type, last_scraped_at, total_evaluated, leads_yielded, cooldown_hours)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_identifier) DO UPDATE SET
                last_scraped_at = excluded.last_scraped_at,
                total_evaluated = sources_tracking.total_evaluated + excluded.total_evaluated,
                leads_yielded = sources_tracking.leads_yielded + excluded.leads_yielded,
                cooldown_hours = excluded.cooldown_hours
        """, (source_identifier, source_type, now, evaluated_count, leads_yielded, cooldown_hours))
    else:
        cur.execute("""
            INSERT INTO sources_tracking (source_identifier, source_type, last_scraped_at, total_evaluated, leads_yielded, cooldown_hours)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(source_identifier) DO UPDATE SET
                last_scraped_at = EXCLUDED.last_scraped_at,
                total_evaluated = sources_tracking.total_evaluated + EXCLUDED.total_evaluated,
                leads_yielded = sources_tracking.leads_yielded + EXCLUDED.leads_yielded,
                cooldown_hours = EXCLUDED.cooldown_hours
        """, (source_identifier, source_type, now, evaluated_count, leads_yielded, cooldown_hours))

    conn.commit()
    conn.close()

def add_dynamic_donor(username: str, discovered_from: str = "", followers_count: int = 0, donor_type: str = "donor"):
    """Saves a new donor or peer_seed discovered via Snowball network graph into dynamic_donors pool."""
    clean_u = username.lower().replace("@", "").strip()
    if not clean_u:
        return
    conn = get_connection()
    cur = conn.cursor()
    if DB_TYPE == "sqlite":
        cur.execute("""
            INSERT INTO dynamic_donors (username, discovered_from, followers_count, donor_type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO NOTHING
        """, (clean_u, discovered_from, followers_count, donor_type))
    else:
        cur.execute("""
            INSERT INTO dynamic_donors (username, discovered_from, followers_count, donor_type)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(username) DO NOTHING
        """, (clean_u, discovered_from, followers_count, donor_type))
    conn.commit()
    conn.close()

def get_available_sources() -> list:
    """
    Builds a list of candidate sources across all 3 Discovery vectors:
    - donor_followers: deep followers list of design studios & platforms
    - donor_replies: live commenters under studio posts (to:donor)
    - peer_following: network neighbors / following of proven super-engagers
    - search: live chronological feed for WIP and design challenges
    Prioritized by unscraped sources first and historical lead yield.
    """
    from config import (
        TARGET_DONORS, SEARCH_QUERIES,
        DONOR_COOLDOWN_HOURS, DONOR_LIKES_COOLDOWN_HOURS, SEARCH_COOLDOWN_HOURS
    )
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT source_identifier, last_scraped_at, leads_yielded, cooldown_hours, total_evaluated FROM sources_tracking")
    tracking_map = {}
    for r in cur.fetchall():
        tracking_map[r[0]] = {
            "last_scraped_at": r[1],
            "leads_yielded": r[2] or 0,
            "cooldown_hours": r[3] or 48,
            "total_evaluated": r[4] or 0
        }

    # Fetch active dynamic donors and peer seeds
    cur.execute("SELECT username, donor_type FROM dynamic_donors WHERE status = 'active' ORDER BY id DESC LIMIT 60")
    dynamic_records = cur.fetchall()
    dynamic_donors = [r[0] for r in dynamic_records if r[1] != 'peer_seed']
    peer_seeds = [r[0] for r in dynamic_records if r[1] == 'peer_seed']
    conn.close()

    all_candidates = []
    now = datetime.datetime.now()

    # 1. Curated Target Donors (Studios & Platforms)
    for d in TARGET_DONORS:
        clean_d = d.replace("@", "").strip()

        # A. Fresh Post Likers (cooldown DONOR_LIKES_COOLDOWN_HOURS = 24h) - HIGHEST ROI
        id_likes = f"donor_likes:{clean_d}"
        info_likes = tracking_map.get(id_likes)
        is_ready_likes = True
        if info_likes and info_likes["last_scraped_at"]:
            try:
                last_dt = datetime.datetime.fromisoformat(str(info_likes["last_scraped_at"]).replace("Z", ""))
                if (now - last_dt).total_seconds() < DONOR_LIKES_COOLDOWN_HOURS * 3600:
                    is_ready_likes = False
            except Exception:
                pass
        if is_ready_likes:
            all_candidates.append({
                "type": "donor_likes",
                "target": clean_d,
                "identifier": id_likes,
                "cooldown": DONOR_LIKES_COOLDOWN_HOURS,
                "yield": info_likes["leads_yielded"] if info_likes else 0,
                "has_scraped": bool(info_likes and info_likes["last_scraped_at"])
            })

        # B. Live Commenters / Replies (cooldown 12h) - HIGH ROI
        id_replies = f"donor_replies:{clean_d}"
        info_replies = tracking_map.get(id_replies)
        is_ready_replies = True
        if info_replies and info_replies["last_scraped_at"]:
            try:
                last_dt = datetime.datetime.fromisoformat(str(info_replies["last_scraped_at"]).replace("Z", ""))
                if (now - last_dt).total_seconds() < 12 * 3600:
                    is_ready_replies = False
            except Exception:
                pass
        if is_ready_replies:
            all_candidates.append({
                "type": "donor_replies",
                "target": clean_d,
                "identifier": id_replies,
                "cooldown": 12,
                "yield": info_replies["leads_yielded"] if info_replies else 0,
                "has_scraped": bool(info_replies and info_replies["last_scraped_at"])
            })

        # C. Followers (cooldown DONOR_COOLDOWN_HOURS = 48) - Low ROI fallback
        id_folls = f"donor_followers:{clean_d}"
        info_folls = tracking_map.get(id_folls)
        is_ready_folls = True
        if info_folls and info_folls["last_scraped_at"]:
            try:
                last_dt = datetime.datetime.fromisoformat(str(info_folls["last_scraped_at"]).replace("Z", ""))
                if (now - last_dt).total_seconds() < DONOR_COOLDOWN_HOURS * 3600:
                    is_ready_folls = False
            except Exception:
                pass
        # Skip dead follower sources (evaluated > 25 and yield == 0)
        if info_folls and info_folls.get("total_evaluated", 0) > 25 and info_folls.get("leads_yielded", 0) == 0:
            is_ready_folls = False

        if is_ready_folls:
            all_candidates.append({
                "type": "donor_followers",
                "target": clean_d,
                "identifier": id_folls,
                "cooldown": DONOR_COOLDOWN_HOURS,
                "yield": info_folls["leads_yielded"] if info_folls else 0,
                "has_scraped": bool(info_folls and info_folls["last_scraped_at"])
            })

    # 2. Dynamic Donors (discovered organically): try donor_likes first
    for d in dynamic_donors:
        clean_d = d.replace("@", "").strip()
        id_likes = f"donor_likes:{clean_d}"
        info_likes = tracking_map.get(id_likes)
        is_ready_likes = True
        if info_likes and info_likes["last_scraped_at"]:
            try:
                last_dt = datetime.datetime.fromisoformat(str(info_likes["last_scraped_at"]).replace("Z", ""))
                if (now - last_dt).total_seconds() < DONOR_LIKES_COOLDOWN_HOURS * 3600:
                    is_ready_likes = False
            except Exception:
                pass
        if is_ready_likes:
            all_candidates.append({
                "type": "donor_likes",
                "target": clean_d,
                "identifier": id_likes,
                "cooldown": DONOR_LIKES_COOLDOWN_HOURS,
                "yield": info_likes["leads_yielded"] if info_likes else 0,
                "has_scraped": bool(info_likes and info_likes["last_scraped_at"])
            })

    # 3. Peer Seeds: 'peer_following' (following of verified super-engagers, cooldown 72h)
    for p in peer_seeds:
        clean_p = p.replace("@", "").strip()
        id_peer = f"peer_following:{clean_p}"
        info_peer = tracking_map.get(id_peer)
        is_ready_peer = True
        if info_peer and info_peer["last_scraped_at"]:
            try:
                last_dt = datetime.datetime.fromisoformat(str(info_peer["last_scraped_at"]).replace("Z", ""))
                if (now - last_dt).total_seconds() < 72 * 3600:
                    is_ready_peer = False
            except Exception:
                pass
        if is_ready_peer:
            all_candidates.append({
                "type": "peer_following",
                "target": clean_p,
                "identifier": id_peer,
                "cooldown": 72,
                "yield": info_peer["leads_yielded"] if info_peer else 0,
                "has_scraped": bool(info_peer and info_peer["last_scraped_at"])
            })

    # 4. Live Search Queries (cooldown SEARCH_COOLDOWN_HOURS = 10) - HIGHEST ROI
    for q in SEARCH_QUERIES:
        id_search = f"search:{q}"
        info_search = tracking_map.get(id_search)
        is_ready_search = True
        if info_search and info_search["last_scraped_at"]:
            try:
                last_dt = datetime.datetime.fromisoformat(str(info_search["last_scraped_at"]).replace("Z", ""))
                if (now - last_dt).total_seconds() < SEARCH_COOLDOWN_HOURS * 3600:
                    is_ready_search = False
            except Exception:
                pass
        if is_ready_search:
            all_candidates.append({
                "type": "search",
                "target": q,
                "identifier": id_search,
                "cooldown": SEARCH_COOLDOWN_HOURS,
                "yield": info_search["leads_yielded"] if info_search else 0,
                "has_scraped": bool(info_search and info_search["last_scraped_at"])
            })

    # Smart Prioritization:
    # 1. Base weight by source ROI type (search & donor_likes lead)
    # 2. Historical yield bonus
    # 3. Fresh unscraped bonus
    TYPE_WEIGHT = {
        "search": 45,
        "donor_likes": 40,
        "donor_replies": 30,
        "peer_following": 25,
        "donor_followers": 5
    }
    random.shuffle(all_candidates)
    all_candidates.sort(
        key=lambda s: (
            TYPE_WEIGHT.get(s["type"], 10) + min(35, s["yield"] * 2) + (10 if not s["has_scraped"] else 0)
        ),
        reverse=True
    )
    return all_candidates

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", SQLITE_PATH)
