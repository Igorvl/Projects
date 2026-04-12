"""
Behance Scout — главная точка входа

Использование:
  python run.py --login          # Первый раз: ручной логин через Google
  python run.py --learn          # Phase 1: скрапинг appreciated + стиль Ксении
  python run.py --discover       # Phase 2: поиск новых похожих проектов
  python run.py --comments       # Генерация комментариев для новых проектов
  python run.py --dashboard      # Запуск UI для дизайнера
  python run.py --all            # learn + discover + comments (для cron)
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
    p.add_argument("--learn",     action="store_true", help="Phase 1: скрапинг appreciated + стиль Ксении")
    p.add_argument("--discover",  action="store_true", help="Phase 2: поиск новых проектов по тегам")
    p.add_argument("--comments",  action="store_true", help="Сгенерировать комментарии для новых проектов")
    p.add_argument("--dashboard", action="store_true", help="Запустить UI дашборд")
    p.add_argument("--all",       action="store_true", help="discover + comments (для cron, каждый день)")
    p.add_argument("--max",       type=int, default=200, help="Макс. проектов для --learn")
    p.add_argument("--target",    type=int, default=60,  help="Цель для --discover (кандидатов за прогон)")
    return p.parse_args()


async def async_main(args):
    db.init_db()

    if args.login:
        from scraper.auth import login_flow
        await login_flow()

    elif args.learn:
        from scraper.appreciated import scrape_appreciated
        new, comments = await scrape_appreciated(max_projects=args.max)
        print(f"\n✅ Изучено: {new} новых проектов, {comments} комментариев Ксении")

    elif args.discover or args.all:
        from scraper.discovery import discover_new_projects
        saved = await discover_new_projects(target=args.target)
        print(f"\n✅ Discovery: {saved} новых проектов сохранено")

        if args.all or args.comments:
            from analysis.comment_gen import generate_all_missing
            await generate_all_missing()

    elif args.comments:
        from analysis.comment_gen import generate_all_missing
        await generate_all_missing()

    else:
        print(__doc__)


if __name__ == "__main__":
    args = parse_args()

    # Dashboard запускается вне asyncio.run() — uvicorn сам создаёт event loop
    if args.dashboard:
        import uvicorn
        from config import DASHBOARD_HOST, DASHBOARD_PORT
        db.init_db()
        print(f"\n🌐 Dashboard: http://172.25.9.33:{DASHBOARD_PORT}")
        uvicorn.run(
            "dashboard.app:app",
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            reload=False,
        )
    else:
        asyncio.run(async_main(args))
