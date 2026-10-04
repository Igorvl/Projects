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

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from database import (
    get_connection,
    get_candidates_for_follow,
    get_queue_count,
    get_stale_unfollow_count,
    get_account_stats,
    get_hourly_mutation_stats,
    check_hourly_mutation_governor,
    DB_TYPE
)
from config import (
    DAILY_FOLLOW_LIMIT,
    DAILY_UNFOLLOW_LIMIT,
    MIN_SCORE_THRESHOLD,
    TARGET_ACCOUNT,
    UNFOLLOW_AFTER_DAYS,
    MAX_HOURLY_MUTATIONS,
    get_current_ramp_up
)
from scraper import run_harvesting_cycle
from follower import (
    run_follow_batch,
    run_unfollow_batch,
    get_today_counts,
    get_today_likes,
    sync_target_profile_stats
)

# Расписание дня (сон 7 часов: с 00:00 до 07:00, активные часы: с 07:00 до 00:00)
WORK_START_HOUR = 7       # 07:00 утра
WORK_END_HOUR = 24        # 00:00 (полночь)
MIN_QUEUE_BUFFER = 75     # Постоянный здоровый буфер очереди (держим 75-150 проверенных супер-лайкеров)
MAX_HARVEST_SOURCES = 10  # Безопасный лимит источников за цикл (чтобы сессия оставалась динамичной)

def is_work_hours() -> bool:
    """Returns True if current local time is within active daytime hours (07:00 - 00:00)."""
    now = datetime.datetime.now()
    return now.hour >= WORK_START_HOUR

def print_banner(profile_name: str):
    """Prints status header with Smart Ramp-Up progression and Following/Followers balance."""
    follows_today, unfollows_today = get_today_counts()
    likes_today = get_today_likes()
    hourly_stats = get_hourly_mutation_stats(window_minutes=60)
    h_mut = hourly_stats["total_mutations"]
    h_fol = hourly_stats["follows_count"]
    h_unf = hourly_stats["unfollows_count"]
    h_lik = hourly_stats["likes_count"]

    queue_count = get_queue_count()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stage_idx, stage_data, ramp_day = get_current_ramp_up()
    acc_followers, acc_following = get_account_stats(TARGET_ACCOUNT)
    ratio = (acc_following / max(1, acc_followers)) if acc_followers > 0 else 1.0
    gap = acc_following - acc_followers
    
    speed_status = "🟢 Органика" if h_mut < 23 else ("🟡 Плотная сессия" if h_mut < 33 else "🔴 Предел безопасности")
    
    print("\n" + "=" * 70)
    print(f"  🤖 F4F AUTONOMOUS GROWTH ORCHESTRATOR [SMART RAMP-UP]")
    print(f"  Profile: @{profile_name}  |  Time: {now_str}")
    print(f"  Ramp-Up: {stage_data['name']} (День {ramp_day}/8)")
    print(f"  Balance: [{acc_following} Following] | [{acc_followers} Followers] (Ratio: {ratio:.2f}, Gap: +{gap})")
    print(f"  Follows today: {follows_today}/{stage_data['follows']} (Цель: 300) | Likes today: {likes_today}/{stage_data['likes']}")
    print(f"  Unfollows today: {unfollows_today}/{stage_data['unfollows']} | Queue: {queue_count} leads ready")
    print(f"  ⏱️ Антиспам-Тахометр (1ч): {h_mut}/{MAX_HOURLY_MUTATIONS} мутаций ({h_fol} fol + {h_unf} unfol | {h_lik} ❤️) [{speed_status}]")
    print("=" * 70 + "\n")

def enforce_hourly_safety_governor() -> bool:
    """
    Жесткий предохранитель антиспама:
    Ограничивает мутации графа (follow + unfollow) числом MAX_HOURLY_MUTATIONS (40) в любой скользящий 1 час.
    При превышении >= 40:
    - Выводит причину остановки (кол-во мутаций, подписок, отписок, лайков);
    - Выводит длительность паузы до охлаждения активности до безопасного уровня;
    - Выводит точное местное время возобновления работы бота;
    - Запускает контролируемый sleep с периодическим heart-beat в консоли.
    """
    gov = check_hourly_mutation_governor(limit=MAX_HOURLY_MUTATIONS, target_safe=28)
    if gov["triggered"]:
        wait_sec = gov["wait_seconds"]
        mins = wait_sec // 60
        secs = wait_sec % 60
        resume_str = gov["resume_time"].strftime("%H:%M:%S")
        
        print("\n" + "=" * 72)
        print("  🛑 [АНТИСПАМ-ПРЕДОХРАНИТЕЛЬ] СРАБОТАЛА ЖЕСТКАЯ БЕЗОПАСНАЯ БЛОКИРОВКА!")
        print(f"  Причина: Зафиксировано {gov['mutations']} мутаций графа за скользящий 1 час (лимит: {MAX_HOURLY_MUTATIONS}).")
        print(f"  Действия за последний час: {gov['follows']} подписок + {gov['unfollows']} отписок (также {gov['likes']} ❤️).")
        print(f"  Длительность остановки: {mins} мин {secs} сек (до охлаждения активности до безопасного уровня).")
        print(f"  Возобновление работы бота: ровно в {resume_str}")
        print("=" * 72 + "\n")
        
        sleep_until(gov["resume_time"], reason="Антиспам-Охлаждение")
        return True
    return False

def run_content_pipeline(profile_name: str = "test_igorvl777"):
    """
    Slot for future manual or scheduled content operations:
    (Manifesto tweet EXOMETRIC – STRATOSPHERE_DELTA is already published manually with 48 likes & 1.1k views).
    """
    pass

def run_single_session(profile_name: str):
    """
    Executes one complete human-style session according to active Ramp-Up stage:
    1. Hard Hourly Governor: Enforces <= 40 mutations in rolling 1-hour window.
    2. Dynamic Balance Equalizer: Enforces Following ≈ Followers parity.
       If Following significantly exceeds Followers or like quota is exhausted,
       new follows are FROZEN (batch_target = 0) to avoid dry follows.
    3. Runs Unfollow pruning to reduce Following gap.
    4. Runs Ego-List bombing catalyst & Nudges.
    5. Executes micro-batch follows with Tri-Touch Cascade ONLY if likes are available.
    6. Continuous Lead Harvesting without queue ceilings.
    7. Syncs live followers and following stats on X.
    """
    print_banner(profile_name)

    # Жесткий предохранитель антиспама: проверяем скользящий 1 час
    enforce_hourly_safety_governor()

    follows_today, unfollows_today = get_today_counts()
    likes_today = get_today_likes()
    stage_idx, stage_data, _ = get_current_ramp_up()
    daily_follow_limit = stage_data["follows"]
    daily_unfollow_limit = stage_data["unfollows"]
    daily_like_limit = stage_data["likes"]
    
    acc_followers, acc_following = get_account_stats(TARGET_ACCOUNT)
    stale_unfollow_backlog = get_stale_unfollow_count(days=UNFOLLOW_AFTER_DAYS)
    
    ratio = (acc_following / max(1, acc_followers)) if acc_followers > 0 else 1.0
    gap = acc_following - acc_followers

    # Dynamic Ratio Equalizer: добиваемся паритета Following ≈ Followers!
    is_imbalanced = (acc_following > 0 and acc_followers > 0 and (ratio > 1.05 or gap > 15))
    pruning_priority_mode = is_imbalanced or (stale_unfollow_backlog > 30)

    remaining_follows = daily_follow_limit - follows_today
    remaining_likes = daily_like_limit - likes_today
    remaining_unfollows = daily_unfollow_limit - unfollows_today

    likes_exhausted = (likes_today >= daily_like_limit or remaining_likes < 2)
    follows_exhausted = (follows_today >= daily_follow_limit)

    min_b, max_b = stage_data["batch"]

    # СТРОГОЕ ПРАВИЛО: Подписываться на кандидатов без лайков бессмысленно (нет Tri-Touch Cascade)!
    # Если лимит лайков исчерпан — подписки СТРОГО замораживаются!
    if likes_exhausted:
        batch_target = 0
        print(f"[Orchestrator] 🛑 Daily like limit reached ({likes_today}/{daily_like_limit}).")
        print(f"[Orchestrator] 🚫 Follows FROZEN: Tri-Touch Cascade strictly requires likes. Dry follows are prohibited!")
        print(f"[Orchestrator] ⚡ Activating maintenance mode: executing Unfollows, Lead Harvesting, Ego-Lists, Mutuals.")
    elif follows_exhausted:
        batch_target = 0
        print(f"[Orchestrator] 🎯 Daily follow limit reached ({follows_today}/{daily_follow_limit}). Follows completed.")
        print(f"[Orchestrator] ⚡ Focusing on remaining quotas: Unfollows ({unfollows_today}/{daily_unfollow_limit}), Harvesting, Ego-Lists.")
    elif is_imbalanced:
        # При дисбалансе: подписки идут малым темпом, отписки максимальным
        max_by_likes = remaining_likes // 2
        batch_target = min(random.randint(6, 10), remaining_follows, max_by_likes)
        print(f"[Orchestrator] ⚖️ Ratio Balancing ACTIVE: Following ({acc_following}) > Followers ({acc_followers}) [Gap: +{gap}].")
        print(f"[Orchestrator] 🚀 Paced convergence: {batch_target} follows vs target 18-25 unfollows (gradual parity).")
    elif pruning_priority_mode:
        max_by_likes = remaining_likes // 2
        batch_target = min(random.randint(8, 12), remaining_follows, max_by_likes)
        print(f"[Orchestrator] ⚖️ Pruning Priority Mode: {stale_unfollow_backlog} candidates waiting (72h+). Follow target: {batch_target}.")
    else:
        max_by_likes = remaining_likes // 2
        batch_target = min(random.randint(min_b, max_b), remaining_follows, max_by_likes)

    if batch_target > 0:
        print(f"[Orchestrator] Session target: {batch_target} follows (Remaining today: {remaining_follows}, Likes left: {remaining_likes})")

    # 1. ОТПИСКИ (Reciprocity & Unfollow Pruning):
    # Выполняем в первую очередь, если включен приоритет разгрузки ИЛИ если подписки остановлены (нет лайков/лимит подписок)!
    should_unfollow_first = pruning_priority_mode or likes_exhausted or follows_exhausted
    if should_unfollow_first and unfollows_today < daily_unfollow_limit:
        unfollow_session_target = min(random.randint(18, 25), remaining_unfollows)
        print(f"\n[Orchestrator] 🧹 [Priority Step 1] Reciprocity & Unfollow check (Session target: {unfollow_session_target}, Today: {unfollows_today}/{daily_unfollow_limit}, Backlog: {stale_unfollow_backlog})...")
        try:
            run_unfollow_batch(profile_name=profile_name, batch_size=unfollow_session_target)
            sync_target_profile_stats(profile_name=profile_name, account=TARGET_ACCOUNT)
        except Exception as e:
            print(f"[Orchestrator] Priority Unfollow error: {e}")

    # 2. ВОРОНКА ДОЖИМА — День 2-3: Second-Wave Nudge (повторный лайк на свежий твит)
    now = datetime.datetime.now()
    if 10 <= now.hour <= 22:
        if not likes_exhausted:
            try:
                from follower import run_nudge_batch
                nudge_batch = random.randint(4, 7) if pruning_priority_mode else random.randint(2, 4)
                print(f"\n[Orchestrator] Funnel Stage 2: Day 3 Nudge review ({nudge_batch} candidates)...")
                run_nudge_batch(profile_name=profile_name, batch_size=nudge_batch)
            except Exception as e:
                print(f"[Orchestrator] Day 3 Nudge notice: {e}")
        else:
            print(f"\n[Orchestrator] Funnel Stage 2: Day 3 Nudge skipped (Daily like limit reached: {likes_today}/{daily_like_limit}).")

    # 3. ВОРОНКА ДОЖИМА — День 3-4: Last-Chance Ego-List (добавление в публичный список)
    # Списки НЕ тратят лайки! Работают полноценно в дневное время
    if 10 <= now.hour <= 22:
        try:
            from follower import run_funnel_list_batch
            list_batch = random.randint(3, 5) if pruning_priority_mode else random.randint(2, 3)
            print(f"\n[Orchestrator] Funnel Stage 3: Day 4 Ego-List review ({list_batch} candidates)...")
            run_funnel_list_batch(profile_name=profile_name, batch_size=list_batch)
        except Exception as e:
            print(f"[Orchestrator] Day 4 Funnel List notice: {e}")

    # 4. ПОДПИСКИ: выполняем ТОЛЬКО если batch_target > 0 (есть лайки и нет блокировки)
    if batch_target > 0 and follows_today < daily_follow_limit and not likes_exhausted:
        queue_count = get_queue_count()
        if queue_count < MIN_QUEUE_BUFFER:
            needed = max(25, MIN_QUEUE_BUFFER - queue_count + batch_target)
            print(f"[Orchestrator] Queue has {queue_count} leads (< buffer {MIN_QUEUE_BUFFER}). Starting on-demand harvesting (goal: +{needed} leads)...")
            try:
                run_harvesting_cycle(profile_name=profile_name, target_queued=needed, max_sources=MAX_HARVEST_SOURCES)
            except Exception as e:
                print(f"[Orchestrator] Harvesting warning: {e}")
                
            pause_sec = random.randint(45, 75)
            print(f"[Orchestrator] Human pause between research and follow actions ({pause_sec}s)...")
            time.sleep(pause_sec)

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
    else:
        if likes_exhausted:
            print("[Orchestrator] ⏸️ Follow batch SKIPPED (Tri-Touch Cascade requires likes. Preserving conversion).")
        elif batch_target == 0:
            print("[Orchestrator] ⏸️ Follow batch SKIPPED (Balance Equalizer active).")
        else:
            print(f"[Orchestrator] Daily follow limit ({daily_follow_limit}) reached. Following skipped.")

    # 5. ПОИСК КАНДИДАТОВ В ПУЛ ПОДПИСОК (Continuous Lead Harvesting Engine):
    # Когда подписки заморожены, но на дворе день — сбор кандидатов продолжается непрерывно!
    # Чтение и оценка кандидатов не расходуют квоты лайков/подписок.
    # Чем больше кандидатов в очереди (300, 500, 1000+), тем выше ранжирование и качество выборки.
    if (likes_exhausted or follows_exhausted) and is_work_hours():
        queue_count = get_queue_count()
        target_harvest = random.randint(15, 25)
        print(f"\n[Orchestrator] 🔍 Continuous Lead Harvesting: Expanding candidate pool (Current queue: {queue_count} leads, Session goal: +{target_harvest} qualified leads)...")
        try:
            run_harvesting_cycle(profile_name=profile_name, target_queued=target_harvest, max_sources=MAX_HARVEST_SOURCES)
        except Exception as e:
            print(f"[Orchestrator] Continuous harvesting notice: {e}")

    # 6. КОНТЕНТНЫЙ ПАЙПЛАЙН: задел под постинг, репостинг, комментинг
    try:
        run_content_pipeline(profile_name=profile_name)
    except Exception as e:
        print(f"[Orchestrator] Content pipeline notice: {e}")

    # 7. ПЛАНОВЫЕ ОТПИСКИ (если не запускались на шаге 1)
    if not should_unfollow_first:
        _, unfollows_today = get_today_counts()
        if unfollows_today < daily_unfollow_limit:
            remaining_unfollows = daily_unfollow_limit - unfollows_today
            unfollow_session_target = min(random.randint(10, 16), remaining_unfollows)
            print(f"\n[Orchestrator] Reciprocity & Unfollow check (Session target: {unfollow_session_target}, Today: {unfollows_today}/{daily_unfollow_limit}, Backlog: {stale_unfollow_backlog})...")
            try:
                run_unfollow_batch(profile_name=profile_name, batch_size=unfollow_session_target)
                sync_target_profile_stats(profile_name=profile_name, account=TARGET_ACCOUNT)
            except Exception as e:
                print(f"[Orchestrator] Mutual/Unfollow batch error: {e}")

    # 8. СИНХРОНИЗАЦИЯ ВЗАИМНЫХ ПОДПИСЧИКОВ (1 раз в конце сессии)
    pw = ctx = None
    try:
        from follower import sync_mutual_followers
        from browser import get_browser_context
        pw, ctx, page = get_browser_context(profile_name=profile_name, headless=True)
        sync_mutual_followers(page)
    except Exception as e:
        print(f"[Orchestrator] Quick mutual sync notice: {e}")
    finally:
        if ctx:
            try:
                ctx.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass

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
    Режим «Активной разведки и удержания»:
    Вызывает сессию обслуживания (все процессы кроме подписок).
    """
    run_single_session(profile_name)

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
                
            # Проверка суточной квоты подписок и лайков
            follows_today, _ = get_today_counts()
            likes_today = get_today_likes()
            _, stage_data, _ = get_current_ramp_up()
            daily_follow_limit = stage_data["follows"]
            daily_like_limit = stage_data["likes"]

            if follows_today >= daily_follow_limit or likes_today >= daily_like_limit:
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
                    # Запускаем сессию дневного обслуживания (отписки, поиск кандидатов, списки, mutuals)
                    run_single_session(profile_name)
                    
                    pause_minutes = random.randint(10, 16)
                    next_time = datetime.datetime.now() + datetime.timedelta(minutes=pause_minutes)
                    print(f"\n[Maintenance Cycle Done] Break for {pause_minutes}m. Next maintenance check at: {next_time.strftime('%H:%M:%S')}\n")
                    sleep_until(next_time, reason="Maintenance Break")
                    continue
                
            # Выполняем обычную дневную сессию
            run_single_session(profile_name)
            
            # Рассчитываем человеческий перерыв между сессиями
            acc_followers, acc_following = get_account_stats(TARGET_ACCOUNT)
            gap = acc_following - acc_followers
            is_imbalanced = (acc_following > 0 and acc_followers > 0 and ((acc_following / max(1, acc_followers)) > 1.05 or gap > 15))

            if is_imbalanced:
                pause_minutes = random.randint(8, 14)
                print(f"\n[Session Complete] ⚖️ Equalizer Pacing: break for {pause_minutes} minutes (Gap: +{gap}, focusing on parity).")
            else:
                _, stage_data, _ = get_current_ramp_up()
                p_min, p_max = stage_data["pause"]
                pause_minutes = random.randint(p_min, p_max)
                print(f"\n[Session Complete] Taking organic break for {pause_minutes} minutes ({stage_data['name']}).")

            next_time = datetime.datetime.now() + datetime.timedelta(minutes=pause_minutes)
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
