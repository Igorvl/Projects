"""
Одноразовый скрипт: извлекает const CATEGORIES = {...} из strips.html,
конвертирует в JSON и сохраняет в dashboard/data/categories_db.json.
Также добавляет маркеры [[CATEGORIES_START]] / [[CATEGORIES_END]] в strips.html.

Запускать один раз из корня behance_scout/:
  python dashboard/extract_categories_to_json.py
"""

import re
import json
from pathlib import Path

STRIPS_HTML = Path(__file__).parent / "templates" / "strips.html"
DATA_DIR    = Path(__file__).parent / "data"
OUTPUT_JSON = DATA_DIR / "categories_db.json"

START_MARKER = "// [[CATEGORIES_START]]"
END_MARKER   = "// [[CATEGORIES_END]]"


def find_categories_block(html: str) -> tuple[int, int]:
    """Возвращает (start_idx, end_idx) блока 'const CATEGORIES = { ... };'"""
    pattern = r'const CATEGORIES\s*='
    m = re.search(pattern, html)
    if not m:
        raise ValueError("Не найдено 'const CATEGORIES =' в strips.html")

    start = m.start()
    # Находим открывающую {
    brace_start = html.index('{', m.end())
    depth = 0
    i = brace_start
    while i < len(html):
        c = html[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                # Ищем следующую ; после закрывающей }
                end = html.index(';', i) + 1
                return start, end
        i += 1
    raise ValueError("Не найдена закрывающая } для CATEGORIES")


def js_obj_to_json(js_str: str) -> dict:
    """
    Конвертирует JS-объект CATEGORIES в Python dict.
    Использует js2py или прямой regex для простых случаев.
    Поскольку структура известна — используем eval через ast-like подход.
    """
    import ast

    # Убираем 'const CATEGORIES =' и финальную ';'
    js_str = re.sub(r'^const CATEGORIES\s*=\s*', '', js_str.strip())
    js_str = js_str.rstrip(';').strip()

    # Конвертируем JS → JSON:
    # 1. Числовые ключи объекта: "1:" → "\"1\":"
    js_str = re.sub(r'(?<=[{,\s])(\d+)\s*:', r'"\1":', js_str)

    # 2. Одиночные кавычки → двойные (с учётом экранирования)
    # Сначала защищаем уже экранированные \'
    js_str = js_str.replace("\\'", "___ESCAPED_QUOTE___")
    js_str = re.sub(r"'([^']*)'", r'"\1"', js_str)
    js_str = js_str.replace("___ESCAPED_QUOTE___", "'")

    # 3. Trailing commas перед } или ]
    js_str = re.sub(r',\s*([}\]])', r'\1', js_str)

    # 4. Комментарии JS (// ...)
    js_str = re.sub(r'//[^\n]*', '', js_str)

    try:
        return json.loads(js_str)
    except json.JSONDecodeError as e:
        # Сохраним промежуточный для отладки
        debug_path = Path(__file__).parent / "_debug_cats.json"
        debug_path.write_text(js_str, encoding='utf-8')
        raise ValueError(
            f"JSON parse error: {e}\n"
            f"Промежуточный файл сохранён: {debug_path}"
        )


def main():
    print(f"Читаем {STRIPS_HTML}...")
    html = STRIPS_HTML.read_text(encoding='utf-8')

    # Проверяем — не добавлены ли маркеры уже
    if START_MARKER in html:
        print("⚠️  Маркеры уже присутствуют в strips.html. Пропускаем добавление маркеров.")
        # Всё равно извлекаем JSON
        m = re.search(re.escape(START_MARKER) + r'(.*?)' + re.escape(END_MARKER), html, re.DOTALL)
        if m:
            js_block = m.group(1).strip()
        else:
            raise ValueError("Маркеры есть, но блок не найден")
    else:
        start, end = find_categories_block(html)
        js_block = html[start:end]
        print(f"Найден блок CATEGORIES: символы {start}–{end} ({end-start} байт)")

        # Добавляем маркеры
        marked_block = f"{START_MARKER}\n{js_block}\n{END_MARKER}"
        new_html = html[:start] + marked_block + html[end:]

        # Бэкап
        bak = STRIPS_HTML.with_suffix('.html.bak_extract')
        STRIPS_HTML.with_suffix('.html.bak_extract')
        bak.write_text(html, encoding='utf-8')
        print(f"Бэкап сохранён: {bak}")

        STRIPS_HTML.write_text(new_html, encoding='utf-8')
        print(f"Маркеры добавлены в {STRIPS_HTML}")

    # Конвертируем в JSON
    print("Конвертируем JS → JSON...")
    cats_dict = js_obj_to_json(js_block)
    print(f"Категорий: {len(cats_dict)}")
    for cid, cat in cats_dict.items():
        count = len(cat.get('items', []))
        print(f"  [{cid}] {cat.get('title', '?')} — {count} элементов")

    # Сохраняем
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(cats_dict, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"\n✅ Сохранено: {OUTPUT_JSON}")
    total = sum(len(c.get('items', [])) for c in cats_dict.values())
    print(f"   Итого элементов: {total}")


if __name__ == '__main__':
    main()
