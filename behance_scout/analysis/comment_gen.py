"""
Генерация комментариев в стиле Ксении через наш LLM router.
Anti-AI prompt engineering для максимальной натуральности.
"""
import json
import httpx
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LLM_API_BASE, LLM_API_KEY, COMMENT_MODEL
import database as db

# Системный промпт — ядро anti-AI маскировки
SYSTEM_PROMPT = """You are an experienced graphic designer leaving a genuine, personal comment on Behance.

STRICT RULES for human-like writing:
1. NEVER start with "I" as the first word
2. Vary sentence length — mix short punchy sentences with longer ones
3. Use specific visual observations (colors, composition, typography) rather than generic praise
4. Occasionally use informal contractions: "it's", "that's", "don't"  
5. Show a personal emotional reaction — what specifically caught your eye?
6. Avoid: "stunning", "amazing", "incredible", "breathtaking", "absolutely", "truly"
7. Avoid: any lists, bullet points, hashtags
8. Keep it 1-3 short paragraphs maximum. Sometimes just 1-2 sentences is perfect.
9. Sound like you genuinely stopped scrolling because something grabbed you
10. NEVER sound promotional or sycophantic
11. It's OK to ask one genuine question about the creative process
12. Vary opening words: "Love how...", "The way...", "What strikes me...", "Really digging...", "Can't get over...", "That color palette..."
"""


def _build_prompt(project_title: str, project_url: str, style_examples: list[str]) -> str:
    examples_block = "\n\n".join(
        f"Example {i+1}: \"{ex}\"" for i, ex in enumerate(style_examples[:8])
    )
    return f"""Study these real comments by a professional designer (DO NOT copy them, learn the STYLE):

{examples_block}

Now write ONE original comment for this Behance project:
Title: {project_title}
URL: {project_url}

Requirements:
- Match the style, tone and length of the examples above
- Be specific to what a designer might genuinely notice
- Sound completely human, personal, and authentic
- Do NOT use generic AI phrases
- Output ONLY the comment text, nothing else"""


async def generate_comment(
    title: str,
    project_url: str,
    behance_id: str,
) -> str | None:
    """Генерирует комментарий в стиле Ксении через наш LLM router."""
    style_examples = db.get_style_samples(limit=8)
    if not style_examples:
        print("[Comment] ⚠️  Нет обучающих примеров! Сначала запусти --learn")
        return None

    prompt = _build_prompt(title, project_url, style_examples)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{LLM_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": COMMENT_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.9,   # высокая вариативность = разные комменты
                    "top_p": 0.95,
                }
            )
        r.raise_for_status()
        comment = r.json()["choices"][0]["message"]["content"].strip()
        # Убираем кавычки если LLM обернул
        comment = comment.strip('"').strip("'").strip()
        db.update_comment(behance_id, comment)
        return comment
    except Exception as e:
        print(f"[Comment] Ошибка генерации: {e}")
        return None


async def generate_all_missing():
    """Генерирует комментарии для всех проектов без комментариев."""
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT behance_id, behance_url, title FROM projects "
        "WHERE generated_comment IS NULL ORDER BY posted_at DESC"
    ).fetchall()
    conn.close()

    print(f"[Comment] Нужно сгенерировать: {len(rows)} комментариев")
    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {row['title'][:50]}")
        comment = await generate_comment(row["title"], row["behance_url"], row["behance_id"])
        if comment:
            print(f"    ✅ {comment[:70]}...")
        else:
            print(f"    ❌ Не удалось")
    print(f"\n[Comment] ✅ Готово! Сгенерировано: {len(rows)}")
