"""
SQLite схема и хелперы для Behance Scout
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            behance_id       TEXT UNIQUE NOT NULL,    -- числовой ID из URL
            behance_url      TEXT NOT NULL,
            title            TEXT,
            author_name      TEXT,
            author_url       TEXT,
            cover_url        TEXT,
            screenshot_path  TEXT,                    -- локальный путь к скрину
            posted_at        TEXT,                    -- дата публикации проекта
            discovered_at    TEXT NOT NULL,           -- когда мы нашли
            freshness_bucket INTEGER DEFAULT 0,       -- 0=0-1мес, 1=1-3мес, 2=3+мес
            visual_score     REAL DEFAULT 0.0,        -- оценка Qwen-VL (0..1)
            tags             TEXT,                    -- JSON массив тегов
            generated_comment TEXT,                   -- сгенерированный комментарий
            comment_ru       TEXT,                    -- русский перевод комментария для интерфейса
            comment_generated_at TEXT,
            shown_at         TEXT,                    -- когда показали дизайнеру
            marked_done_at   TEXT,                    -- когда отметили "сделано"
            is_done          INTEGER DEFAULT 0        -- 0/1
        );
        """)
        try:
            conn.execute("ALTER TABLE projects ADD COLUMN comment_ru TEXT;")
        except sqlite3.OperationalError:
            pass # колонка уже есть

        conn.executescript("""
        CREATE TABLE IF NOT EXISTS style_samples (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_url TEXT NOT NULL,
            comment     TEXT NOT NULL,
            scraped_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS style_profile (
            id           INTEGER PRIMARY KEY CHECK (id = 1),
            visual_desc  TEXT,    -- текстовое описание визуального стиля
            comment_examples TEXT, -- JSON: список примеров комментариев
            tags          TEXT,   -- JSON: наиболее частые теги
            updated_at   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_projects_done    ON projects(is_done);
        CREATE INDEX IF NOT EXISTS idx_projects_freshness ON projects(freshness_bucket, posted_at);
        CREATE INDEX IF NOT EXISTS idx_projects_shown   ON projects(shown_at);
        """)
    print(f"[DB] Инициализирована: {DB_PATH}")


def calc_freshness(posted_at: str | None) -> int:
    """0 = 0-1 мес, 1 = 1-3 мес, 2 = 3+ мес"""
    if not posted_at:
        return 2
    try:
        posted = datetime.fromisoformat(posted_at)
        delta_days = (datetime.utcnow() - posted).days
        if delta_days <= 31:
            return 0
        elif delta_days <= 92:
            return 1
        return 2
    except Exception:
        return 2


def save_project(data: dict) -> bool:
    """Сохраняет проект. Возвращает True если новый, False если уже был."""
    sql = """
    INSERT OR IGNORE INTO projects
        (behance_id, behance_url, title, author_name, author_url,
         cover_url, posted_at, discovered_at, freshness_bucket, tags)
    VALUES
        (:behance_id, :behance_url, :title, :author_name, :author_url,
         :cover_url, :posted_at, :discovered_at, :freshness_bucket, :tags)
    """
    data.setdefault("discovered_at", datetime.utcnow().isoformat())
    data["freshness_bucket"] = calc_freshness(data.get("posted_at"))
    with get_conn() as conn:
        cur = conn.execute(sql, data)
        return cur.rowcount > 0


def update_comment(behance_id: str, comment_en: str, comment_ru: str = None):
    with get_conn() as conn:
        conn.execute("""
            UPDATE projects
            SET generated_comment = ?, comment_ru = ?, comment_generated_at = ?
            WHERE behance_id = ?
        """, (comment_en, comment_ru, datetime.utcnow().isoformat(), behance_id))


def update_screenshot(behance_id: str, path: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET screenshot_path = ? WHERE behance_id = ?",
            (path, behance_id)
        )


def mark_shown(behance_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE projects SET shown_at = ?
            WHERE behance_id = ? AND shown_at IS NULL
        """, (datetime.utcnow().isoformat(), behance_id))


def mark_done(behance_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE projects SET is_done = 1, marked_done_at = ?
            WHERE behance_id = ?
        """, (datetime.utcnow().isoformat(), behance_id))


def get_pending_projects(bucket: int | None = None, page: int = 1, page_size: int = 29):
    """Проекты не помеченные как done, с комментарием, для дизайнера."""
    offset = (page - 1) * page_size
    where  = "WHERE is_done = 0 AND generated_comment IS NOT NULL"
    if bucket is not None:
        where += f" AND freshness_bucket = {bucket}"
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT * FROM projects {where}
            ORDER BY posted_at DESC
            LIMIT ? OFFSET ?
        """, (page_size, offset)).fetchall()
        total = conn.execute(f"SELECT COUNT(*) FROM projects {where}").fetchone()[0]
    return rows, total


def save_style_sample(project_url: str, comment: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO style_samples (project_url, comment, scraped_at)
            VALUES (?, ?, ?)
        """, (project_url, comment, datetime.utcnow().isoformat()))


def get_style_samples(limit: int = 50) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT comment FROM style_samples ORDER BY RANDOM() LIMIT ?", (limit,)
        ).fetchall()
    return [r["comment"] for r in rows]


def save_style_profile(visual_desc: str, comment_examples: str, tags: str):
    import json
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO style_profile (id, visual_desc, comment_examples, tags, updated_at)
            VALUES (1, ?, ?, ?, ?)
        """, (visual_desc, comment_examples, tags, datetime.utcnow().isoformat()))


def get_style_profile() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM style_profile WHERE id = 1").fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
