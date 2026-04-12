"""
FastAPI Dashboard для дизайнера
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import database as db
from config import PAGE_SIZE, SCREENSHOTS_DIR

app = FastAPI(title="Behance Scout")

# Отдаём скрины как статику
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/projects")
async def get_projects(bucket: int = -1, page: int = 1):
    bucket_arg = None if bucket == -1 else bucket
    rows, total = db.get_pending_projects(bucket=bucket_arg, page=page, page_size=PAGE_SIZE)

    projects = []
    for r in rows:
        # Помечаем как показанные
        db.mark_shown(r["behance_id"])
        projects.append({
            "id":          r["behance_id"],
            "url":         r["behance_url"],
            "title":       r["title"] or "Untitled",
            "author":      r["author_name"] or "",
            "posted_at":   r["posted_at"] or "",
            "comment":     r["generated_comment"] or "",
            "screenshot":  f"/screenshots/{r['behance_id']}.png" if r["screenshot_path"] else None,
            "bucket":      r["freshness_bucket"],
            "is_done":     r["is_done"],
        })

    # Подсчёт по вкладкам
    _, c0 = db.get_pending_projects(bucket=0, page=1, page_size=1)
    _, c1 = db.get_pending_projects(bucket=1, page=1, page_size=1)
    _, c2 = db.get_pending_projects(bucket=2, page=1, page_size=1)

    return JSONResponse({
        "projects": projects,
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "counts": {"0": c0, "1": c1, "2": c2, "all": c0 + c1 + c2},
    })


@app.post("/api/done/{behance_id}")
async def mark_done(behance_id: str):
    db.mark_done(behance_id)
    return {"ok": True}
