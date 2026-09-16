# -*- coding: utf-8 -*-
"""
Autonomous Human-Style F4F Growth Orchestrator.
Manages the full 24-hour cycle:
- Respects day-parting (active during day, sleeping at night)
- Balances search & donor harvesting dynamically
- Executes micro-batches of high-score follows with human pauses
- Checks reciprocity (mutuals) and handles pruning (unfollows)
- Adheres strictly to safety limits (<= 40 follows/day)
"""

import sys
import time
import random
import datetime
from database import get_connection, get_candidates_for_follow, get_queue_count, DB_TYPE
from config import (
    DAILY_FOLLOW_LIMIT,
    DAILY_UNFOLLOW_LIMIT,
    MIN_SCORE_THRESHOLD,
    get_current_ramp_up
)
from scraper import run_harvesting_cycle
from follower import (
    run_follow_batch,
    run_unfollow_batch,
    get_today_counts
)

# Расписание дня (сон 7 часов: с 00:00 до 07:00, активные часы: с 07:00 до 00:00)
WORK_START_HOUR = 7       # 07:00 утра
WORK_END_HOUR = 24        # 00:00 (полночь)
MIN_QUEUE_BUFFER = 75     # Постоянный буфер очереди (держим 75+ проверенных супер-лайкеров)

def is_work_hours() -> bool:
    """Returns True if current local time is within active daytime hours (07:00 - 00:00)."""
    now = datetime.datetime.now()
    return now.hour >= WORK_START_HOUR

def print_banner(profile_name: str):
    """Prints status header with Smart Ramp-Up progression."""
    follows_today, unfollows_today = get_today_counts()
    queue_count = get_queue_count()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stage_idx, stage_data, ramp_day = get_current_ramp_up()
    
    print("\n" + "=" * 65)
    print(f"  🤖 F4F AUTONOMOUS GROWTH ORCHESTRATOR [SMART RAMP-UP]")
    print(f"  Profile: @{profile_name}  |  Time: {now_str}")
    print(f"  Ramp-Up: {stage_data['name']} (День {ramp_day}/8)")
    print(f"  Follows today: {follows_today}/{stage_data['follows']} (Цель: 300) | Queue: {queue_count} leads ready")
    print(f"  Unfollows today: {unfollows_today}/{stage_data['unfollows']}")
    print("=" * 65 + "\n")

def run_single_session(profile_name: str):
    """
    Executes one complete human-style session according to active Ramp-Up stage:
    1. Checks daily quota for current stage
    2. Harvests if queue is below buffer target (MIN_QUEUE_BUFFER = 75)
    3. Executes micro-batch follows according to current stage pace
    4. Runs Ego-List bombing catalyst
    5. Runs evening mutual check / pruning (72h non-responders)
    6. Syncs mutual followers for up-to-date stats
    """
    print_banner(profile_name)
    follows_today, _ = get_today_counts()
    stage_idx, stage_data, _ = get_current_ramp_up()
    daily_follow_limit = stage_data["follows"]
    
    if follows_today >= daily_follow_limit:
        print(f"[Orchestrator] Daily follow limit for {stage_data['name']} ({daily_follow_limit}) reached today. Standing by.")
        return
        
    remaining_today = daily_follow_limit - follows_today
    min_b, max_b = stage_data["batch"]
    batch_target = min(random.randint(min_b, max_b), remaining_today)
    
    print(f"[Orchestrator] Session target: {batch_target} follows (Remaining today: {remaining_today})")
    
    # 1. Проверяем очередь кандидатов. Держим здоровый буфер (минимум MIN_QUEUE_BUFFER лидов)
    queue_count = get_queue_count()
    if queue_count < MIN_QUEUE_BUFFER:
        target_to_harvest = max(10, MIN_QUEUE_BUFFER - queue_count + batch_target)
        print(f"[Orchestrator] Queue has {queue_count} leads (< buffer {MIN_QUEUE_BUFFER}). Starting on-demand harvesting (+{target_to_harvest})...")
        try:
            run_harvesting_cycle(profile_name=profile_name, target_queued=target_to_harvest)
        except Exception as e:
            print(f"[Orchestrator] Harvesting warning: {e}")
            
        # Человеческая пауза между ресёрчем и началом подписок (1.5–2.5 минуты)
        pause_sec = random.randint(75, 150)
        print(f"[Orchestrator] Human pause between research and follow actions ({pause_sec}s)...")
        time.sleep(pause_sec)
        
    # 2. Выполняем пачку подписок
    queue_count = get_queue_count()
    if queue_count > 0:
        actual_batch = min(batch_target, queue_count)
        print(f"[Orchestrator] Executing follow batch of {actual_batch} top-scored candidates...")
        try:
            run_follow_batch(profile_name=profile_name, batch_size=actual_batch)
        except Exception as e:
            print(f"[Orchestrator] Follow batch error: {e}")
    else:
        print("[Orchestrator] No qualified candidates found in this cycle. Will retry in next session.")
        
    # 3. Воронка Дожима — День 3: Second-Wave Nudge (повторный лайк на свежий твит)
    now = datetime.datetime.now()
    if 12 <= now.hour <= 20:
        try:
            from follower import run_nudge_batch
            print("\n[Orchestrator] Funnel Stage 2: Day 3 Nudge review...")
            run_nudge_batch(profile_name=profile_name, batch_size=random.randint(2, 4))
        except Exception as e:
            print(f"[Orchestrator] Day 3 Nudge notice: {e}")

    # 4. Воронка Дожима — День 4: Last-Chance Ego-List (дожим системным пушем тщеславия)
    if 14 <= now.hour <= 21:
        try:
            from follower import run_funnel_list_batch
            print("\n[Orchestrator] Funnel Stage 3: Day 4 Ego-List review...")
            run_funnel_list_batch(profile_name=profile_name, batch_size=random.randint(2, 4))
        except Exception as e:
            print(f"[Orchestrator] Day 4 Funnel List notice: {e}")

    # 5. Вечерний аудит взаимности (после 18:00) с Weekend Safe-Zone
    if now.hour >= 18:
        print("\n[Orchestrator] Evening routine: checking reciprocal follows & non-responders...")
        try:
            run_unfollow_batch(profile_name=profile_name, batch_size=5)
        except Exception as e:
            print(f"[Orchestrator] Mutual check error: {e}")

    # 6. Быстрая фоновая синхронизация взаимных подписчиков (1 запрос на 3 секунды)
    try:
        from follower import sync_mutual_followers
        from browser import get_browser_context
        pw, ctx, page = get_browser_context(profile_name=profile_name, headless=True)
        sync_mutual_followers(page)
        ctx.close()
        pw.stop()
    except Exception as e:
        print(f"[Orchestrator] Quick mutual sync notice: {e}")

def sleep_until(target_dt: datetime.datetime, reason: str = "Break"):
    """
    Sleeps until target_dt checking wall-clock time in 15-second chunks.
    Resilient to Windows standby, sleep, and system clock changes.
    Prints periodic countdown heartbeats so the user knows it's actively waiting.
    """
    last_heartbeat = 0.0
    while datetime.datetime.now() < target_dt:
        diff = (target_dt - datetime.datetime.now()).total_seconds()
        if diff <= 0:
            break
        now_ts = time.time()
        # Print status every 2 minutes or when remaining is under 60s
        if now_ts - last_heartbeat >= 120.0 or (diff <= 60 and now_ts - last_heartbeat >= 20.0):
            hours = int(diff // 3600)
            mins = int((diff % 3600) // 60)
            secs = int(diff % 60)
            time_str = f"{hours:02d}h {mins:02d}m" if hours > 0 else f"{mins}m {secs:02d}s"
            print(f"  ⏳ [{reason}] Next action at {target_dt.strftime('%H:%M:%S')} (Remaining: {time_str})...")
            last_heartbeat = now_ts
        time.sleep(min(15.0, diff))

def run_passive_intelligence_session(profile_name: str):
    """
    Режим «Активной разведки»: запускается днем, когда лимит подписок уже исчерпан.
    Занимается безопасными действиями чтения и удержания аудитории (Read Actions):
    1. Пополняет очередь до 45+ лидов, чтобы на утро были самые свежие супер-лайкеры.
    2. Синхронизирует взаимных подписчиков (детекция новых mutuals в реальном времени).
    3. Запускает дожим через Ego-List или Nudge, если суточные квоты списков еще не исчерпаны.
    """
    print("\n" + "=" * 65)
    print(f"  🔍 ACTIVE INTELLIGENCE & RETENTION MODE")
    print(f"  Profile: @{profile_name}  |  Daily follow limit reached, but daytime is active!")
    print("=" * 65)
    
    # 1. Пополнение очереди до буфера
    queue_count = get_queue_count()
    if queue_count < MIN_QUEUE_BUFFER:
        target_harvest = min(15, MIN_QUEUE_BUFFER - queue_count)
        print(f"[Intelligence] Queue has {queue_count} leads (< buffer {MIN_QUEUE_BUFFER}). Harvesting +{target_harvest} top creators...")
        try:
            run_harvesting_cycle(profile_name=profile_name, target_queued=target_harvest)
        except Exception as e:
            print(f"[Intelligence] Harvesting notice: {e}")
            
    # 2. Дожим через списки тщеславия (Ego-List), если квота еще свободна
    now = datetime.datetime.now()
    if 13 <= now.hour <= 22:
        try:
            from follower import run_funnel_list_batch
            print("[Intelligence] Day 4 Funnel Ego-List review...")
            run_funnel_list_batch(profile_name=profile_name, batch_size=random.randint(2, 3))
        except Exception as e:
            print(f"[Intelligence] Funnel list notice: {e}")
            
    # 3. Синхронизация взаимных
    try:
        from follower import sync_mutual_followers
        from browser import get_browser_context
        pw, ctx, page = get_browser_context(profile_name=profile_name, headless=True)
        sync_mutual_followers(page)
        ctx.close()
        pw.stop()
    except Exception as e:
        print(f"[Intelligence] Mutual sync notice: {e}")

def run_daemon_loop(profile_name: str, ignore_work_hours: bool = False):
    """
    Main autonomous daemon loop.
    Coordinates daytime micro-sessions and night rest.
    """
    print(f"[Orchestrator] Launching continuous autonomous loop for @{profile_name}...")
    if ignore_work_hours:
        print("[Orchestrator] ⚡ Night mode bypass enabled (--force / --ignore-night). Running 24/7.")
    
    while True:
        try:
            now = datetime.datetime.now()
            
            # Проверка ночного сна (00:00 - 07:00)
            if not ignore_work_hours and not is_work_hours():
                morning = now.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
                if now.hour >= WORK_START_HOUR:
                    morning += datetime.timedelta(days=1)
                sleep_seconds = max(60, int((morning - now).total_seconds()))
                print(f"\n[Night Mode] Current time {now.strftime('%H:%M')}. Night rest until {morning.strftime('%H:%M:%S')} (~{sleep_seconds // 3600}h {(sleep_seconds % 3600) // 60}m)...")
                print("Tip: Run with --force or --ignore-night if you want to run micro-sessions right now during night hours.")
                sleep_until(morning, reason="Night Rest")
                continue
                
            # Проверка суточной квоты подписок
            follows_today, _ = get_today_counts()
            if follows_today >= DAILY_FOLLOW_LIMIT:
                # Если наступила ночь (00:00 - 07:00) — спим до утра
                if not is_work_hours():
                    morning = now.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
                    if now.hour >= WORK_START_HOUR:
                        morning += datetime.timedelta(days=1)
                    sleep_seconds = max(60, int((morning - now).total_seconds()))
                    print(f"\n[Daily Limit Reached + Night Mode] Resting until {morning.strftime('%H:%M:%S')} (~{sleep_seconds // 3600}h {(sleep_seconds % 3600) // 60}m)...")
                    sleep_until(morning, reason="Night Rest")
                    continue
                else:
                    # Дневное активное время (07:00 - 00:00): НЕ засыпаем на полдня!
                    # Запускаем режим «Активной разведки и удержания» (Passive Intelligence)
                    run_passive_intelligence_session(profile_name)
                    _, stage_data, _ = get_current_ramp_up()
                    p_min, p_max = stage_data["pause"]
                    pause_minutes = random.randint(p_min, p_max)
                    next_time = datetime.datetime.now() + datetime.timedelta(minutes=pause_minutes)
                    print(f"\n[Intelligence Cycle Done] Break for {pause_minutes}m. Next check at: {next_time.strftime('%H:%M:%S')}\n")
                    sleep_until(next_time, reason="Passive Mode Break")
                    continue
                
            # Выполняем дневную сессию
            run_single_session(profile_name)
            
            # Рассчитываем человеческий перерыв между сессиями согласно активному этапу разгона
            _, stage_data, _ = get_current_ramp_up()
            p_min, p_max = stage_data["pause"]
            pause_minutes = random.randint(p_min, p_max)
            next_time = datetime.datetime.now() + datetime.timedelta(minutes=pause_minutes)
            print(f"\n[Session Complete] Taking organic break for {pause_minutes} minutes ({stage_data['name']}).")
            print(f"Next active session planned at: {next_time.strftime('%H:%M:%S')}\n")
            sleep_until(next_time, reason="Session Break")
            
        except KeyboardInterrupt:
            print("\n[Orchestrator] Manual shutdown requested by user. Terminating gracefully.")
            break
        except Exception as e:
            print(f"\n[Orchestrator Unexpected Error] {e}")
            print("Cooling down for 5 minutes before auto-retry...")
            time.sleep(300)

if __name__ == "__main__":
    profile = "test_igorvl777"
    run_once = False
    ignore_work_hours = False
    
    for arg in sys.argv[1:]:
        if arg in ("--once", "-1"):
            run_once = True
        elif arg in ("--force", "--ignore-night", "--anytime", "-f"):
            ignore_work_hours = True
        elif not arg.startswith("-"):
            profile = arg
            
    if run_once:
        print(f"[Orchestrator] Running single session for @{profile}...")
        run_single_session(profile)
    else:
        run_daemon_loop(profile, ignore_work_hours=ignore_work_hours)
