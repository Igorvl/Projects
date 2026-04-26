"""
FastAPI Dashboard для дизайнера
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import sys
import httpx
import json
import re
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
            "comment_ru":  r["comment_ru"] or "",
            "screenshot":  f"/screenshots/{Path(r['screenshot_path']).name}" if r["screenshot_path"] else None,
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


@app.get("/strips", response_class=HTMLResponse)
async def strips_page():
    html_path = Path(__file__).parent / "templates" / "strips.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/strips/ai")
async def strips_ai(request: Request):
    """Проксирует запрос на AI-генерацию к нашему LLM роутеру."""
    from config import LLM_API_BASE, LLM_API_KEY, COMMENT_MODEL

    try:
        body = await request.json()
        concept = body.get("concept", "").strip()
        catalog_summary = body.get("catalog_summary", "")

        if not concept:
            return JSONResponse({"error": "No concept provided"}, status_code=400)

        system_prompt = f"""You are an elite art director AI. Map the user's concept to design parameter IDs from this catalog.

{catalog_summary}

Selections rules:
- Category 1 (School): exactly 1 ID
- Category 2 (Aesthetics DNA): 2-4 IDs
- Category 3 (Colors): exactly 1 ID
- Category 4 (Color Rotation): exactly 1 ID
- Category 5 (Structure): exactly 1 ID
- Category 6 (Graphics): 2-4 IDs
- Category 7 (Super-Graphics): exactly 1 ID
- Category 8 (Material/Print): exactly 1 ID
- Category 9 (Optics/Light): exactly 1 ID
- Category 10 (Trigger): exactly 1 ID

Respond with ONLY a JSON object. Keys = category IDs as strings "1"–"10". Values = arrays of integer item IDs.
Example: {{"1":[3],"2":[5,12],"3":[7],"4":[2],"5":[14],"6":[8,22],"7":[4],"8":[11],"9":[6],"10":[17]}}"""

        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{LLM_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": COMMENT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Concept: {concept}. Return JSON only."}
                    ],
                    "max_tokens": 350,
                    "temperature": 0.7
                }
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"].strip()
        clean = re.sub(r'```[a-z]*\n?', '', text).strip()
        json_match = re.search(r'\{.*\}', clean, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return JSONResponse(result)
        return JSONResponse({"error": "Could not parse model response"}, status_code=500)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
