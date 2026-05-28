"""
API Quota Tracker — отслеживание вызовов к OpenRouter (бесплатный tier).
Хранит счётчики в data/api_quota.json, сбрасывает раз в день.

Примерные лимиты OpenRouter free tier:
  - ~20 req/min global
  - ~200 req/day для текстовых моделей
  - ~50 req/day для vision-моделей (тяжёлые запросы)
"""
import json
import threading
from datetime import date
from pathlib import Path

_QUOTA_FILE = Path(__file__).parent / "data" / "api_quota.json"
_lock = threading.Lock()

# Мягкие лимиты — при достижении логируем предупреждение
SOFT_LIMITS = {
    "vision":    20,   # Vision-запросы (изображения тяжёлые)
    "strips_ai": 200,  # Генерация параметров Strips
    "comment":   50,   # Генерация комментариев Ксении
}

_EMPTY_DAY = lambda: {
    "vision":    {"calls": 0, "errors": 0, "last_model": None},
    "strips_ai": {"calls": 0, "errors": 0, "last_model": None},
    "comment":   {"calls": 0, "errors": 0, "last_model": None},
}


def _load() -> dict:
    """Загружает или создаёт файл квоты."""
    today = str(date.today())
    if _QUOTA_FILE.exists():
        try:
            data = json.loads(_QUOTA_FILE.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return data
        except Exception:
            pass
    # Новый день или повреждённый файл — сбрасываем
    fresh = {"date": today, **_EMPTY_DAY()}
    _save(fresh)
    return fresh


def _save(data: dict):
    _QUOTA_FILE.parent.mkdir(exist_ok=True)
    tmp = _QUOTA_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_QUOTA_FILE)


def log_call(endpoint: str, model: str | None = None, success: bool = True):
    """
    Логирует API-вызов.
    
    Args:
        endpoint: "vision", "strips_ai", или "comment"
        model: название модели (например "google/gemma-4-26b-a4b:free")
        success: True если запрос прошёл, False если была ошибка (429/401/500)
    """
    if endpoint not in SOFT_LIMITS:
        return
    with _lock:
        data = _load()
        ep = data[endpoint]
        ep["calls"] += 1
        if not success:
            ep["errors"] += 1
        if model:
            ep["last_model"] = model.split("/")[-1]  # Короткое имя модели
        _save(data)

    # Предупреждение при достижении мягкого лимита
    calls = data[endpoint]["calls"]
    limit = SOFT_LIMITS[endpoint]
    if calls == limit:
        import logging
        logging.warning(f"[Quota] ⚠️  {endpoint}: достигнут мягкий лимит {limit} req/day")
    elif calls > limit:
        import logging
        logging.warning(f"[Quota] 🔴 {endpoint}: превышен лимит! {calls}/{limit} req/day")


def get_today_stats() -> dict:
    """
    Возвращает статистику за сегодня.
    
    Returns:
        {
            "date": "2026-05-27",
            "vision":    {"calls": 3, "errors": 0, "limit": 20, "pct": 15, "last_model": "gemma-4-26b-a4b:free"},
            "strips_ai": {"calls": 12, "errors": 1, "limit": 200, "pct": 6, "last_model": "gpt-oss-20b:free"},
            "comment":   {"calls": 0, "errors": 0, "limit": 50, "pct": 0, "last_model": null},
        }
    """
    with _lock:
        data = _load()

    result = {"date": data["date"]}
    for ep, limit in SOFT_LIMITS.items():
        ep_data = data.get(ep, {"calls": 0, "errors": 0, "last_model": None})
        calls = ep_data["calls"]
        result[ep] = {
            "calls":      calls,
            "errors":     ep_data["errors"],
            "limit":      limit,
            "pct":        round(calls / limit * 100) if limit else 0,
            "last_model": ep_data.get("last_model"),
        }
    return result


def check_limit(endpoint: str) -> tuple[bool, int, int]:
    """
    Проверяет достигнут ли лимит.
    
    Returns:
        (ok, calls_today, limit) — ok=False если лимит превышен
    """
    with _lock:
        data = _load()
    calls = data.get(endpoint, {}).get("calls", 0)
    limit = SOFT_LIMITS.get(endpoint, 999)
    return calls < limit, calls, limit
