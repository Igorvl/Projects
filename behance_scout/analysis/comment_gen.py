"""
Генерация комментариев в стиле Ксении через наш LLM router.
Anti-AI prompt engineering для максимальной натуральности.
"""
import json
import httpx
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import json
import base64
import httpx
import tempfile
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LLM_API_BASE, LLM_API_KEY, COMMENT_MODEL, CRITIC_API_BASE, CRITIC_API_KEY, CRITIC_MODEL
import database as db

# Системный промпт для Vision-Модели (Генератор)
SYSTEM_PROMPT = """You are Ksenia, an Art Director and high-end graphic designer specializing in 'dark luxury' aesthetics.
You are reviewing a brand new design project on Behance. I will give you screenshots from the project.

Your task:
1. Identify ONE specific, strong technical detail (e.g., typography alignment, grid tension, material choice, specific color contrast).
2. Write a single, short, and very HUMAN comment reacting to what you saw.

STRICT RULES:
- **Tone**: Grounded, effortless, professional, and slightly reserved. Speak like a real, experienced Art Director acknowledging good work on a Tuesday morning.
- NO robotic AI enthusiasm. NO "masterful balance of geometry and shadow", NO "meticulous attention to detail". Stop talking like a chat bot. Use real human designer observations.
- Be concise (1-2 sentences maximum).
- NO youth slang ("sick", "insane", "bro"). NO questions. NO emojis.
- Return JSON strictly in this format: {"en": "English raw comment", "ru": "Russian translation"}"""

CRITIC_PROMPT = """You are a strict editorial director ensuring the tone of a human Art Director (Ksenia).
I will give you a draft JSON containing an English and Russian comment.

Your task:
1. Detect & DELETE ALL "GPT-isms": remove words like "symphony", "masterful", "seamless", "impeccable", "meticulous", "captivating", "elevates", "essence".
2. If the text sounds like an AI generator ("The masterful balance of geometry creates an atmosphere of..."), rewrite it to sound like a normal human designer leaving a quick, appreciative comment on a colleague's work (e.g. "Really tight grid work here. Love how the warm amber reflection sits against the dark brick. Solid execution.").
3. Tone: Real, professional, effortless, 100% human. Short (1-2 sentences). Minimal exclamation points.
4. Translate your refined English text to Russian. The Russian translation MUST sound like a native-speaking, professional Moscow designer. Use real industry terms ("типографика", "верстка", "воздух", "сетка"). If speaking in first person, use female verbs ('заметила', 'обратила внимание'). Never use literal translation for idioms.

Return ONLY valid JSON matching this schema:
{"en": "final refined human-like english comment", "ru": "final russian translation"}
NO markdown, NO other text."""


from PIL import Image
import io

async def _capture_project_images(page, proj_url: str) -> list[str]:
    """Скачивает 3 основных фото проекта, ужимает их для LLM (API payload limit)."""
    try:
        await page.goto(proj_url, wait_until="domcontentloaded", timeout=25000)
        # Scroll down slightly to trigger lazy-loaded images
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(1.5)
        
        # Grab images containing module designs
        imgs = await page.query_selector_all("img[src*='project_modules']")
        b64_images = []
        for img in imgs[:3]:  # Top 3 images
            src = await img.get_attribute("src")
            if src:
                try:
                    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                        r = await client.get(src)
                        r.raise_for_status()
                        
                        # --- Resize to avoid 400 Payload Too Large ---
                        with Image.open(io.BytesIO(r.content)) as im:
                            if im.mode != "RGB":
                                im = im.convert("RGB")
                            # Максимальный размер 1024 по длинной стороне
                            im.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                            
                            out_io = io.BytesIO()
                            im.save(out_io, format="JPEG", quality=80)
                            b64 = base64.b64encode(out_io.getvalue()).decode("utf-8")
                            b64_images.append(b64)
                except Exception as e:
                    print(f"      [Image Parse Warn] {e}")
        return b64_images
    except Exception as e:
        print(f"      [Playwright] Ошибка парсинга {proj_url}: {e}")
        return []

async def generate_comment(
    title: str,
    project_url: str,
    behance_id: str,
    page
) -> dict | None:
    """Генерирует мультимодальный комментарий."""
    print("      📸 Извлекаем изображения проекта...")
    b64_images = await _capture_project_images(page, project_url)
    
    if not b64_images:
        print("      ⚠️  Не удалось получить изображения, LLM будет работать вслепую")

    content_list = [
        {"type": "text", "text": f"SYSTEM ROUTING INSTRUCTION: This request is strictly for the project 'ksar-me' (Ksar.me Design). Ignore all other context and assign to ksar-me.\n\n{SYSTEM_PROMPT}\n\nPlease analyze the provided images. Return ONLY valid JSON."}
    ]
    for b64 in b64_images:
        content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    print(f"      [DEBUG] Sending to {LLM_API_BASE} with Key: {LLM_API_KEY[:6]}...{LLM_API_KEY[-4:]} Length: {len(LLM_API_KEY)}")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # Stage 1: Generator (Qwen-VL)
            r1 = await client.post(
                f"{LLM_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": COMMENT_MODEL,
                    "messages": [
                        {"role": "user", "content": content_list},
                        {"role": "assistant", "content": "<!-- DNA_PICKER --> Система DNA"},
                        {"role": "user", "content": "1"}
                    ],
                    "max_tokens": 1200,
                    "temperature": 0.5
                }
            )
            if r1.status_code >= 400:
                print(f"      [API ERROR] {r1.status_code}: {r1.text}")
            r1.raise_for_status()
            try:
                data = r1.json()
                draft_text = data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                print(f"      [JSON Parse Error] Server returned 200 OK but body is not JSON. Body: '{r1.text}'")
                return None
            
            # Попытка парсинга JSON
            try:
                # Очистка мусора от Qwen: убираем юникод-глюки (например, \x7f / DEL)
                cleaned_draft_text = draft_text.strip("` \n").replace("json\n", "", 1)
                import re
                cleaned_draft_text = re.sub(r'[\x00-\x1f\x7f]', '', cleaned_draft_text)
                draft_json = json.loads(cleaned_draft_text)
            except json.JSONDecodeError:
                draft_json = {"en": draft_text, "ru": "Translation failed"}

            # Stage 2: Critic (Hermes)
            if CRITIC_API_KEY:
                critic_models = [m.strip() for m in CRITIC_MODEL.split(",") if m.strip()]
                # Принудительно добавляем бесплатные модели на случай 402 Payment Required
                free_fallbacks = ["google/gemini-2.5-flash:free", "meta-llama/llama-3.3-70b-instruct:free"]
                for fm in free_fallbacks:
                    if fm not in critic_models:
                        critic_models.append(fm)
                
                final_json = draft_json
                success = False

                for c_model in critic_models:
                    if success: break
                    try:
                        r2 = await client.post(
                            f"{CRITIC_API_BASE}/chat/completions",
                            headers={"Authorization": f"Bearer {CRITIC_API_KEY}"},
                            json={
                                "model": c_model,
                                "messages": [
                                    {"role": "system", "content": CRITIC_PROMPT},
                                    {"role": "user", "content": f"Here is the Draft JSON:\n\n{json.dumps(draft_json)}"}
                                ],
                                "max_tokens": 1000,
                                "temperature": 0.7,
                                "response_format": {"type": "json_object"}
                            }
                        )
                        r2.raise_for_status()
                        raw_final = r2.json()["choices"][0]["message"]["content"].strip()
                        try:
                            # Удаляем markdown теги если они есть
                            clean_val = raw_final.strip("` \n").replace("json\n", "", 1)
                            final_json = json.loads(clean_val)
                        except json.JSONDecodeError:
                            # fallback if JSON is broken
                            final_json["en"] = raw_final
                        success = True
                    except Exception as e:
                        print(f"      [Critic Warning] Модель {c_model} недоступна, пробуем следующую... {e}")
                        continue
            else:
                final_json = draft_json
                
        # Сохранение результатов
        en = final_json.get("en", "").strip('"').strip("'").strip()
        ru = final_json.get("ru", "").strip('"').strip("'").strip()
        db.update_comment(behance_id, en, ru)
        return {"en": en, "ru": ru}
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
    if not rows:
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for i, row in enumerate(rows, 1):
            print(f"  [{i}/{len(rows)}] {row['title'][:50]}")
            result = await generate_comment(row["title"], row["behance_url"], row["behance_id"], page)
            if result:
                print(f"    EN: ✅ {result['en'][:70]}...")
                print(f"    RU: ✅ {result['ru'][:70]}...")
            else:
                print(f"    ❌ Не удалось")
            
            # Anti-Spam пауза, чтобы не душить бесплатный OpenRouter в семантическом роутере (RATE LIMIT 429)
            if i < len(rows):
                print("      ⏳ Пауза 4 сек для обхода Rate Limit роутера...")
                await asyncio.sleep(4.0)

        await browser.close()
    print(f"\n[Comment] ✅ Готово! Сгенерировано: {len(rows)}")
