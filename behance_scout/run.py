"""
Behance Scout — главная точка входа

Использование:
  python run.py --login          # Первый раз: ручной логин через Google
  python run.py --learn          # Phase 1: скрапинг appreciated + извлечение стиля
  python run.py --comments       # Генерация комментариев для новых проектов
  python run.py --dashboard      # Запуск UI для дизайнера
  python run.py --all            # learn + comments (для cron)
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import database as db


def parse_args():
    p = argparse.ArgumentParser(description="Behance Scout")
    p.add_argument("--login",     action="store_true", help="Ручной логин в Behance (первый запуск)")
    p.add_argument("--learn",     action="store_true", help="Phase 1: скрапинг appreciated + комментарии Ксении")
    p.add_argument("--comments",  action="store_true", help="Сгенерировать комментарии для всех новых проектов")
    p.add_argument("--dashboard", action="store_true", help="Запустить UI дашборд")
    p.add_argument("--all",       action="store_true", help="learn + comments (для cron)")
    p.add_argument("--max",       type=int, default=200, help="Макс. проектов для --learn")
    return p.parse_args()


async def main():
    args = parse_args()
    db.init_db()

    if args.login:
        from scraper.auth import login_flow
        await login_flow()

    elif args.learn or args.all:
        from scraper.appreciated import scrape_appreciated
        new, comments = await scrape_appreciated(max_projects=args.max)
        print(f"\n✅ Изучено: {new} новых проектов, {comments} комментариев Ксении")

        if args.all:
            from analysis.comment_gen import generate_all_missing
            await generate_all_missing()

    elif args.comments:
        from analysis.comment_gen import generate_all_missing
        await generate_all_missing()

    elif args.dashboard:
        import uvicorn
        from config import DASHBOARD_HOST, DASHBOARD_PORT
        print(f"\n🌐 Dashboard: http://172.25.9.33:{DASHBOARD_PORT}")
        uvicorn.run(
            "dashboard.app:app",
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            reload=False,
        )

    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
