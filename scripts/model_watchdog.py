#!/usr/bin/env python3
"""
Model Watchdog — DNA Router Health Monitor v1.0
================================================
Делает три вещи:
  1. HEALTH CHECK   — тестирует каждую модель из antigravity.json
  2. DISCOVERY      — ищет новые free модели на OpenRouter (не в конфиге)
  3. AUTO-REPLACE   — заменяет мёртвые модели живыми аналогами

Уведомляет через ntfy.

Usage:
    python3 model_watchdog.py [--auto-replace] [--dry-run]

Cron (каждые 6 часов):
    0 */6 * * * cd /home/igorvl/ai-design-workspace && python3 scripts/model_watchdog.py --auto-replace >> /var/log/model_watchdog.log 2>&1
"""

import asyncio
import json
import os
import sys
import time
import httpx
import argparse
from datetime import datetime
from pathlib import Path

# ─── Конфиг ─────────────────────────────────────────────────────────────────

# Пути относительно корня проекта (ai-design-workspace)
CONFIG_PATH          = Path(os.getenv("CONFIG_PATH", "deploy/antigravity.json"))
FAILURE_HISTORY_PATH = Path(os.getenv("FAILURE_HISTORY_PATH", "deploy/model_failures.json"))
NTFY_URL             = os.getenv("NTFY_URL", "https://ntfy.sh/dna-alerts-igorvl777")

# Таймауты для тестов
TEST_TIMEOUT_OK   = 5.0    # быстрее — ОК
TEST_TIMEOUT_SLOW = 12.0   # медленнее — SLOW
TEST_MAX_RETRIES  = 2      # кол-во попыток при сетевых ошибках (TIMEOUT/502)
TEST_MAX_TOKENS   = 5
TEST_PROMPT       = "Reply with just the number: 1+1="


# ─── Smart Auto-Replace: фильтры для кандидатов из Discovery ─────────────────
# Старые захардкоженные REPLACEMENT_CANDIDATES и MODEL_ROLES удалены.
# Теперь кандидаты берутся из свежего Discovery-списка и фильтруются по качеству.

# Минимальный контекст для кандидата замены
MIN_CTX_FOR_REPLACE    = 32_000   # меньше — пропускаем
PREFER_CTX_FOR_REPLACE = 131_000  # предпочитаем 131k+

# Паттерны в ID указывающие на слишком маленькую модель
SKIP_PARAM_PATTERNS = [
    "-1b", "/1b", "-1.2b", "/1.2b",   # ≤ 1.2B
    "-2b", "/2b",                       # 2B
    "-3b", "/3b",                       # 3B
    "-4b", "/4b",                       # 4B (gemma-3-4b)
    "-6b", "/6b",                       # 6B
    "-7b", "/7b",                       # 7B
    "nano",                             # NVIDIA nano-серия
    "e2b", "e4b",                       # gemma-3n tiny
]

# Типы, которые не нужны как text-замена
SKIP_TYPE_PATTERNS = ["lyria", "clip", "audio", "music", "video"]

# Сколько кандидатов тестировать параллельно
MAX_CANDIDATES_TO_TEST = 8

# ─── Умная аналитика недоступности ───────────────────────────────────────────
#
# Стратегия замены:
#   НЕМЕДЛЕННО  — если ошибка явно говорит «модель навсегда ушла»
#   ОТЛОЖЕНО    — если просто временный сбой: ждём N провалов подряд
#
# Таким образом, DeepSeek-V3 который лёг на 1 час — НЕ будет заменён.

# Сколько последовательных неудачных запусков cron нужно до замены
CONSECUTIVE_FAILS_BEFORE_REPLACE = 3

# Ключевые слова в тексте ошибки, которые означают «модель навсегда недоступна»
# Одно совпадение = немедленная замена без ожидания consecutive-счётчика
PERMANENT_DEATH_KEYWORDS = [
    "deprecated",
    "transition to",
    "no longer available",
    "not a valid model",
    "no endpoints found",
    "no longer free",
    "became paid",
    "this model is not free",
    "removed from free",
    "model not found",
    "provider returned error",   # OpenRouter: модель убрана из free-tier
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)

def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_api_key(env_name: str) -> str | None:
    val = os.getenv(env_name)
    if val:
        return val
    # Попробуем читать из deploy/.env
    env_file = Path("deploy/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{env_name}="):
                return line.split("=", 1)[1].strip().strip('"\'')
    return None

# ─── Failure History (persistent across cron runs) ───────────────────────────

def load_failure_history() -> dict:
    """Загружает историю отказов из JSON-файла."""
    if FAILURE_HISTORY_PATH.exists():
        try:
            return json.loads(FAILURE_HISTORY_PATH.read_text())
        except Exception:
            return {}
    return {}

def save_failure_history(history: dict):
    """Сохраняет историю отказов."""
    FAILURE_HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False))

def is_permanent_death(status: str, error_msg: str | None) -> bool:
    """
    Возвращает True если ошибка явно говорит что модель навсегда недоступна.
    Только в этом случае заменяем немедленно, без ожидания N провалов.
    """
    if status == "DEPRECATED":
        return True
    if error_msg:
        err_lower = error_msg.lower()
        for kw in PERMANENT_DEATH_KEYWORDS:
            if kw in err_lower:
                return True
    return False

def should_replace(
    model_name: str,
    status: str,
    error_msg: str | None,
    history: dict,
) -> tuple[bool, str]:
    """
    Определяет нужно ли заменять модель.

    Returns:
        (replace: bool, reason: str)

    Логика:
      - DEPRECATED или постоянная смерть (ключевое слово) → заменяем немедленно
      - TIMEOUT / ERROR / RATE_LIMIT (временное) → считаем consecutive_fails,
        заменяем только после CONSECUTIVE_FAILS_BEFORE_REPLACE запусков подряд
      - OK / SLOW → сбрасываем счётчик, не заменяем
    """
    if status in ("OK", "SLOW", "NO_KEY", "AUTH_FAIL"):
        return False, "ok"

    if is_permanent_death(status, error_msg):
        return True, f"permanent_death (status={status})"

    # Статус временной ошибки — обновляем счётчик
    entry = history.get(model_name, {"consecutive_fails": 0, "last_statuses": []})
    fails = entry.get("consecutive_fails", 0)

    # NOTE: consecutive_fails уже инкрементирован в main() до вызова этой функции,
    # поэтому сравниваем напрямую (без +1).
    if fails >= CONSECUTIVE_FAILS_BEFORE_REPLACE:
        return True, f"consecutive_fails={fails} >= {CONSECUTIVE_FAILS_BEFORE_REPLACE}"

    return False, f"soft_fail {fails}/{CONSECUTIVE_FAILS_BEFORE_REPLACE} (waiting)"

async def send_ntfy(title: str, msg: str, priority: str = "default", tags: list = None):
    tags_str = ",".join(tags or ["robot"])
    # ntfy HTTP-заголовки должны быть ASCII — убираем emoji из title,
    # emoji остаются в теле сообщения (msg)
    ascii_title = title.encode("ascii", errors="replace").decode("ascii")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                NTFY_URL,
                content=msg.encode("utf-8"),
                headers={
                    "Title": ascii_title,
                    "Priority": priority,
                    "Tags": tags_str,
                    "Content-Type": "text/plain; charset=utf-8",
                }
            )
        print(f"[ntfy] Отправлено ({r.status_code}): {ascii_title}")
    except Exception as e:
        print(f"[ntfy] Ошибка отправки: {e}")

# ─── Model Health Check ────────────────────────────────────────────────────────

async def test_model(model_cfg: dict) -> dict:
    """
    Тестирует одну модель из antigravity.json.
    Возвращает: {model_name, status, latency_s, error}
    """
    model_name = model_cfg["model_name"]
    params = model_cfg.get("litellm_params", {})
    model_id = params.get("model", "")
    api_base = params.get("api_base", "https://openrouter.ai/api/v1")
    api_key_env = params.get("api_key_env", "OPENROUTER_API_KEY")

    api_key = get_api_key(api_key_env)
    if not api_key:
        return {"model_name": model_name, "status": "NO_KEY", "latency_s": 0, "error": f"Нет ключа {api_key_env}"}

    # ── Определяем провайдера и нормализуем model_id ──────────────────────────
    real_model_id = model_id
    if model_id.startswith("gemini/"):
        # Нативный Gemini → Google OpenAI-совместимый эндпоинт
        api_base = "https://generativelanguage.googleapis.com/v1beta/openai"
        real_model_id = model_id.split("/", 1)[1]   # "gemini/gemini-2.5-flash" → "gemini-2.5-flash"
    elif model_id.startswith("groq/"):
        # FIX: Groq требует свой api_base, даже если не прописан в params
        if api_base == "https://openrouter.ai/api/v1":
            api_base = "https://api.groq.com/openai/v1"
        # FIX: Groq требует свой ключ — если не прописан явно, берём GROQ_API_KEY
        if api_key_env == "OPENROUTER_API_KEY":
            groq_key = get_api_key("GROQ_API_KEY")
            if groq_key:
                api_key     = groq_key
                api_key_env = "GROQ_API_KEY"
                print(f"  [GROQ FIX] {model_name}: auto-detected GROQ_API_KEY")
        real_model_id = model_id.split("/", 1)[1]   # "groq/llama-3.3-70b" → "llama-3.3-70b"
    elif "/" in model_id:
        parts = model_id.split("/", 1)
        if parts[0] in ("openai", "openrouter"):
            real_model_id = parts[1]

    payload = {
        "model": real_model_id,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": TEST_MAX_TOKENS,
    }

    t0 = time.time()
    try:
        for attempt in range(TEST_MAX_RETRIES):
            try:
                # Даем щедрый таймаут в 30 секунд для тяжелых моделей (DeepSeek-V3, Llama-70B)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        f"{api_base.rstrip('/')}/chat/completions",
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                latency = time.time() - t0
                data = r.json()

                if r.status_code == 200 and "choices" in data:
                    status = "OK" if latency <= TEST_TIMEOUT_OK else "SLOW"
                    return {"model_name": model_name, "status": status, "latency_s": round(latency, 2), "error": None}

                # Анализируем ошибку (OpenRouter — dict, Google — list)
                err_raw = data.get("error", {})
                if isinstance(err_raw, list):
                    err_raw = err_raw[0] if err_raw else {}
                err_msg = err_raw.get("message", str(data))[:120] if isinstance(err_raw, dict) else str(err_raw)[:120]

                if any(kw in err_msg.lower() for kw in ["deprecated", "transition to", "no longer available"]):
                    status = "DEPRECATED"
                elif r.status_code == 404 or "not a valid model" in err_msg.lower() or "no endpoints found" in err_msg.lower():
                    status = "DEPRECATED"
                elif r.status_code == 401:
                    status = "AUTH_FAIL"
                elif r.status_code == 429:
                    status = "RATE_LIMIT"
                else:
                    status = "ERROR"
                
                # Если RATE_LIMIT или AUTH_FAIL, нет смысла делать retry
                if status in ("RATE_LIMIT", "AUTH_FAIL", "DEPRECATED"):
                    return {"model_name": model_name, "status": status, "latency_s": round(latency, 2), "error": err_msg}
                    
                # Для ERROR/502.. - повторяем, если остались попытки
                if attempt < TEST_MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    t0 = time.time()
                    continue

                return {"model_name": model_name, "status": status, "latency_s": round(latency, 2), "error": err_msg}

            except httpx.TimeoutException:
                if attempt < TEST_MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    t0 = time.time()
                    continue
                return {"model_name": model_name, "status": "TIMEOUT", "latency_s": round(time.time() - t0, 2), "error": "Timeout"}
            
    except Exception as e:
        return {"model_name": model_name, "status": "ERROR", "latency_s": round(time.time() - t0, 2), "error": str(e)[:100]}


# ─── OpenRouter Free Models Discovery ─────────────────────────────────────────

async def fetch_openrouter_free_models(api_key: str) -> list[dict]:
    """Возвращает список free-моделей OpenRouter с ценой=0."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        r.raise_for_status()
        data = r.json()
        free = []
        for m in data.get("data", []):
            pricing = m.get("pricing", {})
            # prompt=="0" означает free; None или "" — пропускаем
            raw = pricing.get("prompt", None)
            if raw is None:
                continue
            try:
                prompt_cost = float(raw)
            except (ValueError, TypeError):
                continue
            if prompt_cost == 0.0:
                free.append({
                    "id": m["id"],
                    "name": m.get("name", m["id"]),
                    "ctx": m.get("context_length", 0),
                    "provider": "openrouter",
                    "litellm_params": {
                        "model": f"openrouter/{m['id']}",
                        "api_base": "https://openrouter.ai/api/v1",
                        "api_key_env": "OPENROUTER_API_KEY",
                    },
                })
        print(f"  [DISCOVERY] Всего free моделей на OpenRouter: {len(free)}")
        return sorted(free, key=lambda x: -x["ctx"])
    except Exception as e:
        print(f"[DISCOVERY] Ошибка ({type(e).__name__}): {e}")
        return []

def get_existing_model_keys(cfg: dict) -> set[str]:
    """Ключи всех моделей в конфиге. Формат: 'provider:model_id'."""
    keys = set()
    for m in cfg.get("model_list", []):
        p    = m.get("litellm_params", {})
        raw  = p.get("model", "")
        base = p.get("api_base", "")
        if raw.startswith("openrouter/"):
            keys.add(f"openrouter:{raw[len('openrouter/'):]}")
        elif raw.startswith("gemini/"):
            keys.add(f"gemini:{raw[len('gemini/'):]}")
        elif raw.startswith("groq/"):
            keys.add(f"groq:{raw[len('groq/'):]}")
        elif "siliconflow" in base:
            keys.add(f"siliconflow:{raw[len('openai/'):] if raw.startswith('openai/') else raw}")
        else:
            keys.add(f"other:{raw}")
    return keys


# ─── Multi-Provider Discovery ──────────────────────────────────────────────────

def make_litellm_params(provider: str, model_id: str) -> dict:
    """Формирует litellm_params для любого провайдера."""
    if provider == "openrouter":
        return {"model": f"openrouter/{model_id}",
                "api_base": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY"}
    elif provider == "siliconflow":
        return {"model": f"openai/{model_id}",
                "api_base": "https://api.siliconflow.com/v1",
                "api_key_env": "SILICONFLOW_API_KEY"}
    elif provider == "gemini":
        return {"model": f"gemini/{model_id}",
                "api_key_env": "GEMINI_API_KEY"}
    elif provider == "groq":
        return {"model": f"groq/{model_id}",
                "api_base": "https://api.groq.com/openai/v1",
                "api_key_env": "GROQ_API_KEY"}
    return {}


_SF_SKIP = [
    "Stable", "FLUX", "CogVideo", "Wan", "HiDream", "Janus",
    "whisper", "speech", "tts",       # аудио
    "Reranker", "reranker",            # reranking-модели
    "Embedding", "embedding",          # embedding-модели
    "Image-Edit", "Image-Turbo",       # image-generation (ne text)
    "IndexTTS",                        # TTS
    "VL-8B",                           # слишком маленькая vision
]

async def fetch_siliconflow_models(api_key: str) -> list[dict]:
    """Доступные text-модели SiliconFlow (бесплатно до дневного лимита)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://api.siliconflow.com/v1/models",
                                 headers={"Authorization": f"Bearer {api_key}"})
        r.raise_for_status()
        models = []
        for m in r.json().get("data", []):
            mid = m["id"]
            if any(pat in mid for pat in _SF_SKIP):
                continue
            models.append({"id": mid, "name": mid.split("/")[-1],
                           "ctx": 131_072, "provider": "siliconflow",
                           "litellm_params": make_litellm_params("siliconflow", mid)})
        print(f"  [SiliconFlow] {len(models)} text-моделей")
        return models
    except Exception as e:
        print(f"  [SiliconFlow] Ошибка ({type(e).__name__}): {e}")
        return []


async def fetch_gemini_models(api_key: str) -> list[dict]:
    """Модели Gemini поддерживающие generateContent (бесплатно с лимитами)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://generativelanguage.googleapis.com/v1beta/models",
                                 params={"key": api_key})
        r.raise_for_status()
        models = []
        for m in r.json().get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            name = m["name"].replace("models/", "")
            if any(s in name for s in ["embed", "aqa", "1.0"]):
                continue
            models.append({"id": name, "name": m.get("displayName", name),
                           "ctx": m.get("inputTokenLimit", 131_072),
                           "provider": "gemini",
                           "litellm_params": make_litellm_params("gemini", name)})
        print(f"  [Gemini] {len(models)} моделей")
        return models
    except Exception as e:
        print(f"  [Gemini] Ошибка ({type(e).__name__}): {e}")
        return []


async def fetch_groq_models(api_key: str) -> list[dict]:
    """Модели Groq (все бесплатны с rate-limit, очень быстрые ~0.2s)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
        if r.status_code == 403:
            print(f"  [Groq] ⚠️  403 — geo-block (IP сервера заблокирован). Пропущен.")
            return []
        r.raise_for_status()
        models = []
        for m in r.json().get("data", []):
            mid = m["id"]
            if any(s in mid for s in ["whisper", "tts", "vision"]):
                continue
            models.append({"id": mid, "name": mid,
                           "ctx": m.get("context_window", 131_072),
                           "provider": "groq",
                           "litellm_params": make_litellm_params("groq", mid)})
        print(f"  [Groq] {len(models)} моделей")
        return models
    except Exception as e:
        print(f"  [Groq] Ошибка ({type(e).__name__}): {e}")
        return []


_PROVIDER_FETCHERS = [
    ("OPENROUTER_API_KEY",  fetch_openrouter_free_models),
    ("SILICONFLOW_API_KEY", fetch_siliconflow_models),
    ("GEMINI_API_KEY",      fetch_gemini_models),
    ("GROQ_API_KEY",        fetch_groq_models),
]

async def fetch_all_free_models(api_keys: dict) -> list[dict]:
    """Собирает доступные модели со всех провайдеров параллельно."""
    tasks, labels = [], []
    for key_env, fn in _PROVIDER_FETCHERS:
        key = api_keys.get(key_env)
        if key:
            tasks.append(fn(key))
            labels.append(key_env.replace("_API_KEY", ""))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_models = []
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            print(f"  [{label}] Провайдер недоступен: {result}")
        else:
            all_models.extend(result)
    return sorted(all_models, key=lambda x: -x["ctx"])



async def try_find_replacement(
    dead_model_name: str,
    free_models: list[dict],
) -> dict | None:
    """
    Умный поиск замены из свежего Discovery-списка.

    Алгоритм:
      1. Фильтруем free_models по качеству (ctx, размер модели)
      2. Шикуем топ-MAX_CANDIDATES_TO_TEST параллельно
      3. Берём самого быстрого со статусом OK
    """
    print(f"  -> Ищем замену для [{dead_model_name}]…")

    def is_quality_candidate(m: dict) -> bool:
        mid = m["id"].lower()
        ctx = m.get("ctx", 0)
        if ctx < MIN_CTX_FOR_REPLACE:
            return False
        for pat in SKIP_TYPE_PATTERNS:
            if pat in mid:
                return False
        for pat in SKIP_PARAM_PATTERNS:
            if pat in mid:
                return False
        return True

    quality = [m for m in free_models if is_quality_candidate(m)]

    # Предпочитаем модели с >= PREFER_CTX_FOR_REPLACE, остальные — запасной вариант
    preferred = [m for m in quality if m["ctx"] >= PREFER_CTX_FOR_REPLACE]
    fallback  = [m for m in quality if m["ctx"] <  PREFER_CTX_FOR_REPLACE]

    # Берём топ по контексту (уже отсортировано по -ctx)
    candidates = (preferred + fallback)[:MAX_CANDIDATES_TO_TEST]

    if not candidates:
        print(f"  !! Нет качественных кандидатов в Discovery ({len(free_models)} free моделей всего)")
        return None

    print(f"  -> Тестируем {len(candidates)} кандидатов параллельно:")
    for c in candidates:
        print(f"      {c['id']} (ctx: {c['ctx']//1000}k)")

    # Тестируем всех параллельно
    test_tasks = [
        test_model({
            "model_name": f"__cand_{fm['id']}",
            "litellm_params": fm["litellm_params"],   # provider-aware!
        })
        for fm in candidates
    ]
    results = await asyncio.gather(*test_tasks)

    # Сортируем по задержке и берём лучшего
    for fm, r in sorted(zip(candidates, results), key=lambda x: x[1]["latency_s"]):
        print(f"      {r['status']} [{fm['provider']}] {fm['id']} ({r['latency_s']}s) {r.get('error') or ''}")

    ok = [(fm, r) for fm, r in zip(candidates, results) if r["status"] in ("OK", "SLOW")]
    ok.sort(key=lambda x: x[1]["latency_s"])

    if ok:
        best_fm, best_r = ok[0]
        print(f"  ✅ Лучший кандидат: [{best_fm['provider']}] {best_fm['id']} "
              f"({best_r['latency_s']}s, ctx: {best_fm['ctx']//1000}k)")
        return {
            "or_id":            best_fm["id"],
            "display_name":     best_fm.get("name", best_fm["id"]),
            "latency_s":        best_r["latency_s"],
            "provider":         best_fm["provider"],
            "new_litellm_params": best_fm["litellm_params"],   # provider-aware!
        }

    print(f"  !! Ни один из {len(candidates)} кандидатов не ответил")
    return None



def apply_replacement(cfg: dict, old_model_name: str, new_id: str, new_params: dict) -> dict:
    """Обновляет litellm_params, переименовывает модель и обновляет алиасы."""
    for m in cfg.get("model_list", []):
        if m.get("model_name") == old_model_name:
            m["model_name"] = new_id
            m["litellm_params"] = new_params
            
            # Инициализируем структуру алиасов LiteLLM
            if "router_settings" not in cfg:
                cfg["router_settings"] = {}
            if "model_group_alias" not in cfg["router_settings"]:
                cfg["router_settings"]["model_group_alias"] = {}
                
            aliases = cfg["router_settings"]["model_group_alias"]
            
            # Сам старый ID становится алиасом для нового
            aliases[old_model_name] = new_id
            
            # Все старые алиасы, которые вели на умершую модель, теперь должны вести на новую
            for alias_key, target in list(aliases.items()):
                if target == old_model_name:
                    aliases[alias_key] = new_id
                    
            break
    return cfg


# ─── Main ──────────────────────────────────────────────────────────────────────

async def main(auto_replace: bool = False, dry_run: bool = False):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"🔍 Model Watchdog запущен: {ts}")
    print(f"   Auto-replace: {auto_replace} | Dry-run: {dry_run}")
    print(f"{'='*60}\n")

    cfg = load_config()
    model_list = cfg.get("model_list", [])

    # Собираем ключи всех провайдеров
    api_keys = {
        "OPENROUTER_API_KEY":  get_api_key("OPENROUTER_API_KEY"),
        "SILICONFLOW_API_KEY": get_api_key("SILICONFLOW_API_KEY"),
        "GEMINI_API_KEY":      get_api_key("GEMINI_API_KEY"),
        "GROQ_API_KEY":        get_api_key("GROQ_API_KEY"),
    }
    active_providers = [k.replace("_API_KEY", "") for k, v in api_keys.items() if v]
    openrouter_key = api_keys["OPENROUTER_API_KEY"]  # backward compat

    # ── 1. HEALTH CHECK ────────────────────────────────────────────────────────
    print(f"[1/3] HEALTH CHECK — {len(model_list)} моделей...\n")
    tasks = [test_model(m) for m in model_list]
    results = await asyncio.gather(*tasks)

    status_icons = {"OK": "✅", "SLOW": "⚠️", "DEPRECATED": "❌", "TIMEOUT": "❌",
                    "ERROR": "❌", "AUTH_FAIL": "🔑", "RATE_LIMIT": "🚦", "NO_KEY": "🔑"}

    ok_models, problem_models = [], []
    for r in results:
        icon = status_icons.get(r["status"], "❓")
        latency = f"{r['latency_s']}s" if r["latency_s"] else ""
        err = f" — {r['error']}" if r["error"] else ""
        print(f"  {icon} [{r['model_name']}] {r['status']} {latency}{err}")
        if r["status"] in ("OK", "SLOW"):
            ok_models.append(r)
        else:
            problem_models.append(r)

    # ── 2. DISCOVERY — новые free модели со всех провайдеров ──────────────────
    providers_str = "+".join(active_providers) or "none"
    print(f"\n[2/3] DISCOVERY ({providers_str})...")
    new_free_models = []
    free_models = []  # доступен ниже в AUTO-REPLACE
    if active_providers:
        free_models = await fetch_all_free_models(api_keys)
        existing_keys = get_existing_model_keys(cfg)
        for fm in free_models:
            prov_key = f"{fm['provider']}:{fm['id']}"
            if prov_key not in existing_keys:
                if not any(kw in fm["id"].lower() for kw in SKIP_TYPE_PATTERNS):
                    new_free_models.append(fm)
                    print(f"  [+] [{fm['provider']}] {fm['id']} (ctx: {fm['ctx']//1000}k)")
        if not new_free_models:
            print("  (нет новых)")
    else:
        print("  Нет API-ключей, discovery пропущен")

    # ── 3. AUTO-REPLACE с умной аналитикой недоступности ───────────────────────
    replacements_done = []
    history = load_failure_history()

    # Сбрасываем счётчики для OK/SLOW-моделей
    for r in ok_models:
        if r["model_name"] in history:
            old_fails = history[r["model_name"]].get("consecutive_fails", 0)
            if old_fails > 0:
                print(f"  ✅ [{r['model_name']}] recovered after {old_fails} fail(s) — counter reset")
            del history[r["model_name"]]

    # Увеличиваем счётчики для проблемных моделей
    for r in problem_models:
        name = r["model_name"]
        entry = history.get(name, {"consecutive_fails": 0, "last_statuses": []})
        entry["consecutive_fails"] = entry.get("consecutive_fails", 0) + 1
        last = entry.get("last_statuses", [])
        last.append({"status": r["status"], "error": r.get("error", "")[:80], "ts": ts})
        entry["last_statuses"] = last[-5:]
        history[name] = entry

    print(f"\n[3/3] AUTO-REPLACE — анализ {len(problem_models)} проблем...")

    models_to_replace = []
    models_waiting    = []

    for pm in problem_models:
        do_replace, reason = should_replace(
            pm["model_name"], pm["status"], pm.get("error"), history
        )
        if do_replace:
            models_to_replace.append((pm, reason))
            print(f"  🔴 [{pm['model_name']}] → REPLACE ({reason})")
        else:
            fails = history.get(pm["model_name"], {}).get("consecutive_fails", 1)
            models_waiting.append(pm)
            print(f"  🟡 [{pm['model_name']}] → WAIT {fails}/{CONSECUTIVE_FAILS_BEFORE_REPLACE} ({reason})")

    if auto_replace and models_to_replace and free_models:
        for pm, reason in models_to_replace:
            replacement = await try_find_replacement(pm["model_name"], free_models)
            if replacement:
                provider = replacement.get("provider", "?")
                replacements_done.append({
                    "old_name":    pm["model_name"],
                    "old_status":  pm["status"],
                    "new_id":      replacement["or_id"],
                    "new_display": replacement["display_name"],
                    "latency_s":   replacement["latency_s"],
                    "provider":    provider,
                    "reason":      reason,
                })
                if not dry_run:
                    cfg = apply_replacement(
                        cfg,
                        pm["model_name"],
                        replacement["or_id"],
                        replacement["new_litellm_params"]
                    )
                    history.pop(pm["model_name"], None)
                    print(f"  >> [{pm['model_name']}] -> {replacement['or_id']} [{provider}] ({replacement['latency_s']}s) - APPLIED")
                else:
                    print(f"  >> [{pm['model_name']}] -> {replacement['or_id']} [{provider}] - DRY RUN")
            else:
                print(f"  !! [{pm['model_name']}] - no live replacement found!")
    elif not auto_replace and models_to_replace:
        print("  (auto-replace disabled, use --auto-replace)")

    # Сохраняем историю отказов и конфиг
    if not dry_run:
        save_failure_history(history)
    if replacements_done and not dry_run:
        save_config(cfg)
        print(f"\n💾 antigravity.json обновлён ({len(replacements_done)} замен)")

    # ── NTFY УВЕДОМЛЕНИЯ ──────────────────────────────────────────────────────
    print(f"\n[NTFY] Формируем отчёт...")

    if problem_models:
        lines = [f"📅 {ts}", ""]
        for pm in problem_models:
            icon = status_icons.get(pm["status"], "❓")
            fails = history.get(pm["model_name"], {}).get("consecutive_fails", 1)
            is_waiting = pm in models_waiting
            verdict = f"⏳ {fails}/{CONSECUTIVE_FAILS_BEFORE_REPLACE}" if is_waiting else "🔄 replace"
            lines.append(f"{icon} {pm['model_name']}: {pm['status']} [{verdict}]")
            if pm["error"]:
                lines.append(f"   {pm['error'][:80]}")

        if replacements_done:
            lines.append("\n🔄 АВТО-ЗАМЕНЕНЫ:")
            for r in replacements_done:
                lines.append(f"  {r['old_name']} → {r['new_id']} ({r['latency_s']}s)")
                lines.append(f"  причина: {r['reason']}")
            if dry_run:
                lines.append("  ⚠️  DRY RUN — изменения не применены")

        if models_waiting:
            lines.append(f"\n⏳ Ждём ({CONSECUTIVE_FAILS_BEFORE_REPLACE} запуска подряд):")
            for pm in models_waiting:
                fails = history.get(pm["model_name"], {}).get("consecutive_fails", 1)
                lines.append(f"  {pm['model_name']}: {fails}/{CONSECUTIVE_FAILS_BEFORE_REPLACE}")

        has_replaced = len(replacements_done) > 0
        has_critical = len(models_to_replace) > 0
        en_title = (
            f"DNA Router: {len(replacements_done)} auto-replaced, {len(problem_models)} issues"
            if has_replaced else
            f"DNA Router: {len(problem_models)} model issues (waiting)"
        )
        await send_ntfy(
            title=en_title,
            msg="\n".join(lines),
            priority="high" if has_critical else "default",
            tags=["warning", "robot"]
        )

    if new_free_models:
        top = new_free_models[:5]
        lines = [f"📅 {ts}", f"Найдено {len(new_free_models)} новых free моделей:", ""]
        for fm in top:
            lines.append(f"🆕 {fm['id']} (ctx: {fm['ctx']//1000}k)")
        if len(new_free_models) > 5:
            lines.append(f"... и ещё {len(new_free_models) - 5} моделей")
        lines.append("\nЗапусти model_watchdog.py для проверки живости.")
        await send_ntfy(
            title=f"DNA Router: {len(new_free_models)} new free models on OpenRouter",
            msg="\n".join(lines),
            priority="low",
            tags=["tada", "robot"]
        )

    # ── ФИНАЛ ─────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ OK: {len(ok_models)} | ❌ Проблем: {len(problem_models)} | 🔴 К замене: {len(models_to_replace)} | 🟡 Ожидают: {len(models_waiting)} | 🔄 Заменено: {len(replacements_done)} | 🆕 Новых: {len(new_free_models)}")
    print(f"{'='*60}\n")

    return 1 if problem_models and not replacements_done else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model Watchdog — DNA Router")
    parser.add_argument("--auto-replace", action="store_true", help="Авто-заменять мёртвые модели")
    parser.add_argument("--dry-run", action="store_true", help="Симуляция без записи конфига")
    args = parser.parse_args()

    exit_code = asyncio.run(main(
        auto_replace=args.auto_replace,
        dry_run=args.dry_run,
    ))
    sys.exit(exit_code)
