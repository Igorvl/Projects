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
from config import LLM_API_BASE, LLM_API_KEY, COMMENT_MODEL, CRITIC_API_BASE, CRITIC_API_KEY, CRITIC_MODEL, \
    VISION_API_BASE, VISION_API_KEY, VISION_MODEL_DIRECT, CRITIC_MODEL_DIRECT
import database as db

# Системный промпт для Vision-Модели (Генератор)
SYSTEM_PROMPT = """You are Ksenia, an experienced Art Director specializing in 'dark luxury' brand identity and high-end graphic design.
You are looking at screenshots from a designer's Behance project. Your job is to understand the work deeply before commenting.

FOLLOW THESE STEPS IN ORDER:

**STEP 1 — READ EVERYTHING:** Carefully read all visible text in the screenshots: headlines, taglines, labels, body copy, UI labels, brand names. These tell you what the project is actually ABOUT.

**STEP 2 — UNDERSTAND THE PROJECT:** Based on what you see and read, determine:
- What is this project? (e.g., brand identity for a restaurant, UI design for a fintech app, packaging for a cosmetics line)
- What industry or niche does it serve?
- What is the visual mood and style direction the designer chose?

**STEP 3 — IDENTIFY THE STRENGTHS:** Pick 1-2 specific, concrete things the designer did well. Think like a designer, not an AI. Examples:
- "The negative space between the letterforms creates natural breathing room"
- "Warm amber tones against dark concrete textures — a smart material contrast"
- "The grid is tight. Every element has a reason to be where it is."

**STEP 4 — WRITE THE COMMENT:** Write a short, natural comment that:
- Responds directly to what the project IS (don't be vague)
- Highlights ONE real strength you identified
- Sounds like a real Art Director leaving a quick note on a colleague's portfolio
- Will make the AUTHOR feel seen and understood, not just praised generically

STRICT TONE RULES:
- Grounded, confident, slightly reserved. No hype.
- NO AI-isms: no "masterful", "seamless", "impeccable", "meticulous", "captivating", "elevates",
  "essence", "symphony", "at its finest", "sophisticated", "deep respect for".
- NO youth slang. NO questions. NO emojis.
- LENGTH: **ONE short sentence.** If second sentence is needed — only if it adds a completely different observation. No complex structures like "The way X does Y gives Z".
- ADJECTIVES: **MAX 1-2 in the entire comment.** No paired adjectives ("stark, deliberate", "quiet, intentional", "clean, precise"). Pick ONE word or none. Prefer verbs and nouns.
  - BAD: "a strong, deliberate choice" → GOOD: "a good call" or just "works"
  - BAD: "stark black and textured beige" → GOOD: "black against beige"
- Think: a Behance comment typed on a phone between meetings.

Return ONLY valid JSON in this exact format:
{"analysis": {"project_type": "EN: one sentence", "project_type_ru": "RU: одно предложение", "strengths": "EN: one sentence", "strengths_ru": "RU: одно предложение"}, "en": "English comment", "ru": "Russian comment"}
NO markdown fences, NO extra text."""

CRITIC_PROMPT = """You are a strict editorial director reviewing a comment written by Art Director Ksenia.
You will receive a JSON with an analysis block and a draft comment in English and Russian.

═══════════════════════════════════════
PASS 1 — FIX THE ENGLISH COMMENT
═══════════════════════════════════════
A) BANNED WORDS — delete or rephrase any of these:
   "symphony", "masterful", "seamless", "impeccable", "meticulous", "captivating", "elevates",
   "essence", "testament", "breathtaking", "at its finest", "sophisticated", "refined tension",
   "honors the", "pays homage", "effortlessly", "striking balance", "timeless", "harmonious".

B) BANNED SENTENCE PATTERNS — rewrite if found:
   - "X honors/pays homage to Y" → describe what it actually does visually
   - "creates a sense of..." → cut it, say what you SEE
   - "feels distinctly contemporary" → too vague, say HOW it feels modern specifically
   - "The contrast between X and Y creates Z" → overused structure, rephrase
   - Any sentence that could describe a DIFFERENT project = must be rewritten to be specific

C) GOOD ENGLISH — use as reference tone:
   - "Really tight grid. The vertical Japanese text isn't decoration — it's load-bearing."
   - "Bold title on woodblock texture: brave call. Works because the weight difference is extreme."
   - "That black-to-silver contrast ratio is deliberate. Someone spent real time on this."
   - "Clean hierarchy. The brand mark doesn't fight the imagery — they share space well."

D) Tone: Dry, confident. **ONE short sentence. Max two only if truly different observations.**
   Never start with "This is", "The way", "I noticed". Just say the thing. The shorter, the better.
E) ADJECTIVES: **MAXIMUM 1-2 in the entire comment.** Cut all paired adjectives.
   - BAD: "stark black and textured beige" → GOOD: "black against beige"
   - BAD: "a strong, deliberate choice" → GOOD: "a good call" / "works"
   - BAD: "quiet, intentional weight" → GOOD: "real weight" or just "weight"

═══════════════════════════════════════
PASS 2 — WRITE THE RUSSIAN FROM SCRATCH
═══════════════════════════════════════
DO NOT translate the English. Write a FRESH, NATIVE Russian comment inspired by the same
observation. Imagine Ksenia is typing it directly to the designer in a DM — casual, professional,
specific. A senior Moscow designer writing to a colleague, not an essayist.

BANNED RUSSIAN PATTERNS (machine-translation red flags):
   - "почитает традиционную эстетику" (calque of "honors the aesthetic")
   - "утончённое напряжение" / "изысканное напряжение" (calque of "refined tension")
   - "оставаясь при этом" (bureaucratic connector)
   - "создаёт ощущение" / "создаёт атмосферу" (AI filler)
   - "гармонично сочетается" / "удачно сочетается" (generic AI compliment)
   - Long subordinate clause chains — real designers write short

GOOD RUSSIAN — use as reference tone:
   - "Сетка жёсткая, всё держится. Вертикальный текст — не декорация, он работает."
   - "Смелый ход с контрастом. Чёрное с серебром — и не банально, потому что пропорции выверены."
   - "Эта типографика не конкурирует с иллюстрацией — они делят пространство. Редко так бывает."
   - "Заметила сразу: жирный заголовок не давит, а наоборот — открывает вход в проект."
   - "Воздух есть, сетка читается. Для такой темы — правильное решение."

RULES FOR RUSSIAN:
   - Short sentences. Real designers don't write в длину.
   - Industry terms are welcome: типографика, верстка, воздух, сетка, айдентика, палитра, контраст, вес, ритм, пропорции.
   - First-person forms must be female: "заметила", "обратила внимание", "зацепило".
   - Length: **ONE short sentence.** Max two only if observing truly different things.
   - No subordinate clause chains. No "оставаясь при этом", no "что придаёт".
   - ПРИЛАГАТЕЛЬНЫЕ: МАКСИМУМ 1-2 на весь комментарий. Запрещены пары ("чистым черным", "сильное, продуманное").
     - НЕТ: "чистый черный, текстурированный бежевый" → ДА: "черный с бежевым"
     - НЕТ: "сильное, продуманное решение" → ДА: "смелое решение" или "работает"

═══════════════════════════════════════
OUTPUT
═══════════════════════════════════════
Return ONLY valid JSON:
{"en": "final refined english comment", "ru": "fresh native russian comment"}
NO markdown, NO extra text."""


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
        for img in imgs[:2]:  # Top 2 images (3 was causing 502 Payload Too Large on router)
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
                            # Максимальный размер 800px — баланс качество/пайлоад для self-hosted роутера
                            im.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            
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
        {"type": "text", "text": f"{SYSTEM_PROMPT}\n\nPlease analyze the provided images. Return ONLY valid JSON."}
    ]
    for b64 in b64_images:
        content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    vision_models = [m.strip() for m in VISION_MODEL_DIRECT.split(",") if m.strip()]
    draft_json = None
    used_vision_model = "None"
    
    import os
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("WATCHDOG_PROXY")
    client_kwargs = {"proxy": proxy_url} if proxy_url else {}
    if proxy_url:
        print(f"      [Network] Использование SOCKS5/HTTP прокси: {proxy_url}")

    try:
        async with httpx.AsyncClient(timeout=60, **client_kwargs) as client:
            # Stage 1: Generator (VLM) — ПРЯМОЙ вызов с Fallback каскадом
            for v_model in vision_models:
                print(f"      [Stage 1] Пробуем Vision: {v_model}")
                try:
                    r1 = await client.post(
                        f"{VISION_API_BASE}/chat/completions",
                        headers={"Authorization": f"Bearer {VISION_API_KEY}"},
                        json={
                            "model": v_model,
                            "messages": [{"role": "user", "content": content_list}],
                            "max_tokens": 450,
                            "temperature": 0.5
                        }
                    )
                    r1.raise_for_status()
                    data = r1.json()
                    draft_text = data["choices"][0]["message"]["content"].strip()
                    
                    # Очистка мусора от Qwen
                    cleaned_draft_text = draft_text.strip("` \n").replace("json\n", "", 1)
                    import re
                    cleaned_draft_text = re.sub(r'[\x00-\x1f\x7f]', '', cleaned_draft_text)
                    draft_json = json.loads(cleaned_draft_text)
                    used_vision_model = v_model
                    
                    # Структурированный вывод
                    if "analysis" in draft_json:
                        analysis = draft_json["analysis"]
                        print(f"")
                        print(f"      ┌─ Что VLM ({v_model.split('/')[-1]}) понял о проекте:")
                        print(f"      │  {analysis.get('project_type_ru') or analysis.get('project_type', '?')}")
                        print(f"      │")
                        print(f"      │  Сильные стороны:")
                        print(f"      │  {analysis.get('strengths_ru') or analysis.get('strengths', '?')}")
                        print(f"      └────────────────────────────────")
                    
                    break # Успех, выходим из каскада
                    
                except json.JSONDecodeError:
                    print(f"      [Vision Warn] Модель {v_model} не вернула JSON, падаем на fallback")
                    continue
                except Exception as e:
                    status = getattr(getattr(e, 'response', None), 'status_code', '?')
                    print(f"      [Vision Warning] {v_model} — HTTP {status}: {repr(e)[:150]}")
                    continue

            if not draft_json:
                print("      [Vision Error] Все бесплатные Vision-модели недоступны или исчерпаны лимиты.")
                return None

            # Stage 2: Critic (DeepSeek-V3.2 @ SiliconFlow — тот же провайдер что Stage 1)
            # Динамически загружаем реальные комментарии Ксении для few-shot
            style_examples = db.get_style_samples(48)  # все доступные примеры Ксении
            if style_examples:
                examples_block = "\n\n═══ РЕАЛЬНЫЕ ПРИМЕРЫ КОММЕНТАРИЕВ КСЕНИИ (few-shot) ═══\n"
                examples_block += "Изучи эти примеры. Твоя задача - звучать абсолютно так же.\n\n"
                for i, ex in enumerate(style_examples, 1):
                    examples_block += f"{i}. «{ex}»\n"
                dynamic_critic_prompt = CRITIC_PROMPT + examples_block
            else:
                dynamic_critic_prompt = CRITIC_PROMPT
                print("      [Critic] style_samples пусты — few-shot не загружены")
            if VISION_API_KEY:
                critic_models = [m.strip() for m in CRITIC_MODEL.split(",") if m.strip()]
                final_json = draft_json
                used_critic_model = "None"
                success = False

                for c_model in critic_models:
                    if success: break
                    print(f"      [Stage 2] Пробуем Critic: {c_model}")
                    try:
                        r2 = await client.post(
                            f"{CRITIC_API_BASE}/chat/completions",
                            headers={"Authorization": f"Bearer {VISION_API_KEY}"},
                            json={
                                "model": c_model,
                                "messages": [
                                    {"role": "system", "content": dynamic_critic_prompt},
                                    {"role": "user", "content": f"Here is the Draft JSON:\n\n{json.dumps(draft_json)}"}
                                ],
                                "max_tokens": 300,
                                "temperature": 0.7
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
                        
                        used_critic_model = c_model
                        success = True
                    except Exception as e:
                        status = getattr(getattr(e, 'response', None), 'status_code', '?')
                        print(f"      [Critic Warning] {c_model} — HTTP {status}: {repr(e)[:150]}")
                        continue
            else:
                final_json = draft_json
                used_critic_model = "Skipped"
                
        # Сохранение результатов
        en = final_json.get("en", "").strip('"').strip("'").strip()
        ru = final_json.get("ru", "").strip('"').strip("'").strip()
        print(f"")
        print(f"      ✅ [СИСТЕМА] Выбор моделей: VLM: [{used_vision_model.split('/')[-1]}] | Critic: [{used_critic_model.split('/')[-1]}]")
        print(f"      ► EN: {en}")
        print(f"      ► RU: {ru}")
        print(f"")
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
