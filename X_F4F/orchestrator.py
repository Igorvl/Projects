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
    MIN_SCORE_THRESHOLD
)
from scraper import run_harvesting_cycle
from follower import (
    run_follow_batch,
    run_unfollow_batch,
    get_today_counts
)

# Расписание дня
WORK_START_HOUR = 9      # 09:00 утра
WORK_END_HOUR = 23       # 23:00 вечера
SESSION_MIN_PAUSE_MIN = 60    # Минимум 60 минут между сессиями
SESSION_MAX_PAUSE_MIN = 140   # Максимум 140 минут между сессиями

def is_work_hours() -> bool:
    """Returns True if current local time is within active daytime hours."""
    now = datetime.datetime.now()
    return WORK_START_HOUR <= now.hour < WORK_END_HOUR

def print_banner(profile_name: str):
    """Prints status header."""
    follows_today, unfollows_today = get_today_counts()
    queue_count = get_queue_count()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "=" * 65)
    print(f"  🤖 F4F AUTONOMOUS GROWTH ORCHESTRATOR")
    print(f"  Profile: @{profile_name}  |  Time: {now_str}")
    print(f"  Follows today: {follows_today}/{DAILY_FOLLOW_LIMIT}  |  Queue: {queue_count} leads ready")
    print(f"  Unfollows today: {unfollows_today}/{DAILY_UNFOLLOW_LIMIT}")
    print("=" * 65 + "\n")

def run_single_session(profile_name: str):
    """
    Executes one complete human-style session:
    1. Checks daily quota
    2. Harvests if queue is low
    3. Executes micro-batch follows
    4. Runs mutual check / pruning once a day in evening
    """
    print_banner(profile_name)
    follows_today, _ = get_today_counts()
    
    if follows_today >= DAILY_FOLLOW_LIMIT:
        print(f"[Orchestrator] Daily follow limit ({DAILY_FOLLOW_LIMIT}) reached for today. Standing by.")
        return
        
    remaining_today = DAILY_FOLLOW_LIMIT - follows_today
    batch_target = min(random.randint(8, 12), remaining_today)
    
    print(f"[Orchestrator] Session target: {batch_target} follows (Remaining today: {remaining_today})")
    
    # 1. Проверяем очередь кандидатов. Если мало — добираем скрапером
    queue_count = get_queue_count()
    if queue_count < batch_target:
        needed = batch_target - queue_count
        print(f"[Orchestrator] Queue has {queue_count} leads (< target {batch_target}). Starting on-demand harvesting...")
        try:
            # Запускаем целевой сбор до достижения необходимого количества лидов
            run_harvesting_cycle(profile_name=profile_name, target_queued=needed)
        except Exception as e:
            print(f"[Orchestrator] Harvesting warning: {e}")
            
        # Человеческая пауза между ресёрчем и началом подписок (1.5–3 минуты)
        pause_sec = random.randint(90, 180)
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
        
    # 3. Вечерний аудит взаимности (после 18:00)
    now = datetime.datetime.now()
    if now.hour >= 18:
        print("\n[Orchestrator] Evening routine: checking reciprocal follows & non-responders...")
        try:
            run_unfollow_batch(profile_name=profile_name, batch_size=6)
        except Exception as e:
            print(f"[Orchestrator] Mutual check error: {e}")

def run_daemon_loop(profile_name: str):
    """
    Main autonomous daemon loop.
    Coordinates daytime micro-sessions and night rest.
    """
    print(f"[Orchestrator] Launching continuous autonomous loop for @{profile_name}...")
    
    while True:
        try:
            now = datetime.datetime.now()
            
            # Проверка ночного сна (23:00 - 09:00)
            if not is_work_hours():
                # Вычисляем время до утра
                morning = now.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
                if now.hour >= WORK_END_HOUR:
                    morning += datetime.timedelta(days=1)
                sleep_seconds = max(60, int((morning - now).total_seconds()))
                print(f"[Night Mode] Current time {now.strftime('%H:%M')}. Night rest until {morning.strftime('%H:%M:%S')} (~{sleep_seconds // 3600}h {(sleep_seconds % 3600) // 60}m)...")
                time.sleep(sleep_seconds)
                continue
                
            # Проверка суточной квоты
            follows_today, _ = get_today_counts()
            if follows_today >= DAILY_FOLLOW_LIMIT:
                tomorrow = (now + datetime.timedelta(days=1)).replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
                sleep_seconds = max(60, int((tomorrow - now).total_seconds()))
                print(f"[Daily Limit Reached] Completed {follows_today}/{DAILY_FOLLOW_LIMIT} follows today.")
                print(f"Resting until next day session ({tomorrow.strftime('%Y-%m-%d %H:%M:%S')})...")
                time.sleep(sleep_seconds)
                continue
                
            # Выполняем дневную сессию
            run_single_session(profile_name)
            
            # Рассчитываем человеческий перерыв между сессиями
            pause_minutes = random.randint(SESSION_MIN_PAUSE_MIN, SESSION_MAX_PAUSE_MIN)
            next_time = datetime.datetime.now() + datetime.timedelta(minutes=pause_minutes)
            print(f"\n[Session Complete] Taking organic break for {pause_minutes} minutes.")
            print(f"Next active session planned at: {next_time.strftime('%H:%M:%S')}\n")
            time.sleep(pause_minutes * 60)
            
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
    
    for arg in sys.argv[1:]:
        if arg in ("--once", "-1"):
            run_once = True
        elif not arg.startswith("-"):
            profile = arg
            
    if run_once:
        print(f"[Orchestrator] Running single session for @{profile}...")
        run_single_session(profile)
    else:
        run_daemon_loop(profile)
