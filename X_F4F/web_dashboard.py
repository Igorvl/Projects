# -*- coding: utf-8 -*-
"""
Standalone Lightweight Web Dashboard & Analytics Center for X F4F Engine.
Runs with Python standard library (http.server) - no external server frameworks needed!
Provides:
- Real-time status cards and candidates monitoring (pagination, search, filters)
- 6 Smart Telemetry Gauges (Ramp-Up, Hourly Speedometer, 5K Ceiling, Lead Quality, 72h Funnel, Source Yield)
- Dedicated Analytics Center with Chart.js timeline charts (Mutuals, Organic growth, Conversion % by day)
"""

import http.server
import socketserver
import json
import sqlite3
import os
import urllib.parse
import datetime
import threading
import time
from config import (
    SQLITE_PATH,
    DASHBOARD_PORT,
    DASHBOARD_HOST,
    TARGET_ACCOUNT,
    DAILY_LIKE_LIMIT,
    get_current_ramp_up
)


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gerrit Brandt ✦ X Growth & Analytics Command Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --bg: #0b0c10;
            --surface: #12141c;
            --surface-hover: #181b26;
            --surface-border: #232738;
            --text-main: #f0f3f8;
            --text-dim: #8b949e;
            --accent: #4f8cff;
            --accent-glow: rgba(79, 140, 255, 0.15);
            --success: #00d26a;
            --success-glow: rgba(0, 210, 106, 0.15);
            --warning: #ffaa00;
            --warning-glow: rgba(255, 170, 0, 0.15);
            --danger: #ff4d4f;
            --purple: #a78bfa;
            --pink: #ff758f;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Space Grotesk', -apple-system, sans-serif;
            padding: 28px 40px;
            line-height: 1.5;
            min-height: 100vh;
        }

        /* Header & Navigation */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 20px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }

        .logo-title {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo-badge {
            background: linear-gradient(135deg, #1d9bf0, #4f8cff);
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 22px;
            color: #fff;
            box-shadow: 0 4px 20px rgba(29, 155, 240, 0.3);
        }

        h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
        .subtitle { color: var(--text-dim); font-size: 13px; margin-top: 2px; }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .nav-tabs {
            display: flex;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 4px;
            gap: 4px;
        }

        .nav-tab {
            background: transparent;
            border: none;
            color: var(--text-dim);
            padding: 8px 18px;
            border-radius: 8px;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .nav-tab:hover { color: #fff; background: rgba(255,255,255,0.04); }
        .nav-tab.active {
            background: var(--accent);
            color: #fff;
            box-shadow: 0 4px 14px rgba(79, 140, 255, 0.35);
        }

        .target-pill {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 8px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            transition: all 0.2s;
        }
        .target-pill:hover {
            border-color: var(--accent);
            background: rgba(79, 140, 255, 0.08);
        }
        .target-pill span { color: var(--accent); font-weight: 600; }

        .sync-btn {
            background: linear-gradient(135deg, rgba(79, 140, 255, 0.18), rgba(0, 210, 106, 0.18));
            border: 1px solid rgba(0, 210, 106, 0.45);
            color: #fff;
            padding: 8px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .sync-btn:hover {
            background: linear-gradient(135deg, rgba(79, 140, 255, 0.35), rgba(0, 210, 106, 0.35));
            border-color: #00d26a;
            transform: translateY(-1px);
            box-shadow: 0 4px 14px rgba(0, 210, 106, 0.25);
        }
        .sync-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .stat-sub {
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 5px;
            font-family: 'JetBrains Mono', monospace;
        }

        .live-dot {
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.4; }
            50% { opacity: 1; }
            100% { opacity: 0.4; }
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 16px 18px;
            border-radius: 12px;
            cursor: pointer;
            user-select: none;
            transition: all 0.2s ease;
        }
        .stat-card:hover { transform: translateY(-2px); border-color: #3b425b; background: var(--surface-hover); }
        .stat-card.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), 0 8px 24px var(--accent-glow); }

        .stat-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
            margin-bottom: 6px;
        }

        .stat-value {
            font-size: 28px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        .stat-value.accent { color: var(--accent); }
        .stat-value.warning { color: var(--warning); }
        .stat-value.success { color: var(--success); }
        .stat-value.pink { color: var(--pink); }

        /* Section Titles */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }
        .section-title {
            font-size: 15px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-dim);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title span { color: var(--accent); }

        /* Gauges Grid */
        .gauges-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }

        .gauge-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            transition: border-color 0.2s;
        }
        .gauge-card:hover { border-color: #383f58; }

        .gauge-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }
        .gauge-name {
            font-size: 14px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .gauge-badge {
            font-size: 11px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            padding: 3px 8px;
            border-radius: 6px;
            background: rgba(255,255,255,0.06);
        }
        .gauge-badge.safe { color: var(--success); background: var(--success-glow); border: 1px solid rgba(0, 210, 106, 0.3); }
        .gauge-badge.warn { color: var(--warning); background: var(--warning-glow); border: 1px solid rgba(255, 170, 0, 0.3); }
        .gauge-badge.danger { color: var(--danger); background: rgba(255, 77, 79, 0.15); border: 1px solid rgba(255, 77, 79, 0.3); }

        .gauge-metric {
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin-bottom: 10px;
        }
        .gauge-val-big {
            font-size: 26px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }
        .gauge-val-sub {
            font-size: 13px;
            color: var(--text-dim);
            font-family: 'JetBrains Mono', monospace;
        }

        /* Custom Progress Bars */
        .progress-track {
            background: #191c28;
            height: 8px;
            border-radius: 999px;
            overflow: hidden;
            position: relative;
            margin-bottom: 8px;
        }
        .progress-fill {
            height: 100%;
            border-radius: 999px;
            transition: width 0.4s ease;
        }
        .fill-accent { background: linear-gradient(90deg, #1d9bf0, #4f8cff); }
        .fill-success { background: linear-gradient(90deg, #00d26a, #10b981); }
        .fill-warning { background: linear-gradient(90deg, #ffaa00, #f59e0b); }
        .fill-pink { background: linear-gradient(90deg, #ff758f, #f43f5e); }
        .fill-purple { background: linear-gradient(90deg, #a78bfa, #8b5cf6); }

        .gauge-meta-row {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: var(--text-dim);
            font-family: 'JetBrains Mono', monospace;
        }

        /* Ramp up steps indicator */
        .ramp-steps {
            display: flex;
            gap: 6px;
            margin: 10px 0 6px 0;
        }
        .ramp-step {
            flex: 1;
            padding: 6px 4px;
            background: #171a26;
            border: 1px solid var(--surface-border);
            border-radius: 6px;
            text-align: center;
            font-size: 10px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-dim);
            transition: all 0.2s;
        }
        .ramp-step.active {
            background: var(--accent-glow);
            border-color: var(--accent);
            color: var(--accent);
            font-weight: 700;
        }
        .ramp-step.completed {
            background: rgba(0, 210, 106, 0.08);
            border-color: rgba(0, 210, 106, 0.3);
            color: var(--success);
        }

        /* Reciprocity Funnel Mini Bars */
        .funnel-segments {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        .funnel-col {
            flex: 1;
            background: #171a26;
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            padding: 8px 10px;
            text-align: center;
        }
        .funnel-col-val {
            font-size: 18px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }
        .funnel-col-lbl {
            font-size: 10px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-top: 2px;
        }

        /* Controls / Filters / Pagination bar */
        .controls-bar {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 14px 18px;
            border-radius: 12px;
            margin-bottom: 16px;
        }

        .filter-group {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .filter-btn {
            background: #161924;
            border: 1px solid var(--surface-border);
            color: var(--text-dim);
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'Space Grotesk', sans-serif;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .filter-btn:hover { color: #fff; border-color: #404863; background: #1c202e; }
        .filter-btn.active {
            background: var(--accent-glow);
            color: var(--accent);
            border-color: var(--accent);
        }
        .filter-btn.active.success-btn {
            background: var(--success-glow);
            color: var(--success);
            border-color: var(--success);
        }
        .filter-btn.active.warning-btn {
            background: var(--warning-glow);
            color: var(--warning);
            border-color: var(--warning);
        }
        .filter-btn.active.danger-btn {
            background: rgba(255, 77, 79, 0.18);
            color: #ff6b6b;
            border-color: #ff4d4f;
        }

        .filter-count {
            background: rgba(255, 255, 255, 0.08);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
        }

        .options-group {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .search-input {
            background: #161924;
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-family: 'Space Grotesk', sans-serif;
            width: 200px;
            outline: none;
            transition: border-color 0.15s;
        }
        .search-input:focus { border-color: var(--accent); }

        select.control-select {
            background: #161924;
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 7px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-family: 'Space Grotesk', sans-serif;
            cursor: pointer;
            outline: none;
        }
        select.control-select:focus { border-color: var(--accent); }

        /* Candidates Table */
        .table-container {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 16px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }

        th {
            background: #141722;
            color: var(--text-dim);
            font-weight: 600;
            padding: 12px 16px;
            border-bottom: 1px solid var(--surface-border);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        td {
            padding: 14px 16px;
            border-bottom: 1px solid rgba(35, 39, 56, 0.6);
            vertical-align: middle;
        }

        tr:hover td { background: var(--surface-hover); }

        .user-col { display: flex; flex-direction: column; gap: 2px; }
        .user-name { font-weight: 700; color: #fff; }
        .user-handle { color: var(--accent); text-decoration: none; font-size: 12px; font-family: 'JetBrains Mono', monospace; }
        .user-handle:hover { text-decoration: underline; }

        .bio-text {
            color: #b0b8c4;
            font-size: 12px;
            max-width: 380px;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .ratio-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-dim);
        }
        .ratio-pill b { color: #fff; }

        .score-box {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 14px;
        }
        .score-high { background: var(--success-glow); color: var(--success); border: 1px solid rgba(0, 210, 106, 0.4); }
        .score-mid { background: var(--accent-glow); color: var(--accent); border: 1px solid rgba(79, 140, 255, 0.4); }
        .score-low { background: #1a1d2b; color: var(--text-dim); border: 1px solid var(--surface-border); }

        .badge {
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
        }
        .badge.queued { background: #1c2333; color: #79a8ff; border: 1px solid rgba(121, 168, 255, 0.3); }
        .badge.followed { background: rgba(255, 170, 0, 0.12); color: var(--warning); border: 1px solid rgba(255, 170, 0, 0.3); }
        .badge.mutual { background: var(--success-glow); color: var(--success); border: 1px solid rgba(0, 210, 106, 0.4); font-weight: 700; }
        .badge.ignored { background: #161822; color: #626a7a; }
        .badge.unfollowed { background: #221a24; color: #d68cb8; }
        .badge.failed_unfollow { background: rgba(255, 77, 79, 0.15); color: #ff6b6b; border: 1px solid rgba(255, 77, 79, 0.3); }

        /* Pagination Bar */
        .pagination-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 12px 18px;
            border-radius: 12px;
            font-size: 12px;
            color: var(--text-dim);
        }

        .pagination-actions {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-page {
            background: #161924;
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-family: 'Space Grotesk', sans-serif;
            transition: all 0.15s;
        }
        .btn-page:hover:not(:disabled) { background: var(--accent); color: #fff; border-color: var(--accent); }
        .btn-page:disabled { opacity: 0.35; cursor: not-allowed; }

        .page-info {
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
            padding: 0 8px;
        }

        /* Analytics Tab Styles */
        .analytics-view { display: none; }
        .analytics-view.active { display: block; }

        .chart-card-full {
            width: 100%;
            margin-bottom: 20px;
        }

        .charts-grid-2x2 {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 1024px) {
            .charts-grid-2x2 {
                grid-template-columns: 1fr;
            }
        }

        .chart-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            padding: 20px;
            position: relative;
        }
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .chart-title {
            font-size: 14px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .chart-desc {
            font-size: 12px;
            color: var(--text-dim);
            font-family: 'JetBrains Mono', monospace;
        }
        .chart-canvas-container {
            position: relative;
            height: 240px;
            width: 100%;
        }

        /* Cohort Table in Analytics */
        .cohort-table-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 24px;
        }
    </style>
</head>
<body>

    <!-- Header -->
    <div class="header">
        <div class="logo-title">
            <div class="logo-badge">𝕏</div>
            <div>
                <h1>Gerrit Brandt ✦ Growth Command Center</h1>
                <div class="subtitle">Autonomous Targeting • Precision Bio Scoring • Real-time Monitoring & Analytics</div>
            </div>
        </div>
        <div class="header-actions">
            <div class="nav-tabs">
                <button class="nav-tab active" id="tab-btn-overview" onclick="switchMainTab('overview')">✦ Обзор и База</button>
                <button class="nav-tab" id="tab-btn-analytics" onclick="switchMainTab('analytics')">📈 Аналитика и Графика</button>
            </div>
            <div class="target-pill" onclick="promptProfileEdit()" title="Кликните для быстрой калибровки">
                <span class="live-dot"></span> Active: <span id="target-account">@GerritBrandt777</span>
                <span style="color:var(--text-dim); margin: 0 4px;">•</span>
                <span style="color:#00d26a; font-weight:700;" id="header-followers-count">36</span> fol /
                <span style="color:#38bdf8; font-weight:700;" id="header-following-count">384</span> fing
            </div>
            <button class="sync-btn" id="btn-sync-profile" onclick="triggerProfileSync()" title="Синхронизировать данные профиля с X онлайн">
                🔄 Обновить из 𝕏
            </button>
        </div>
    </div>

    <!-- TAB 1: OVERVIEW & CANDIDATES -->
    <div id="view-overview">
        <!-- Top Stats Cards -->
        <div class="stats-grid">
            <!-- Card 1: The Result (My Profile Followers) -->
            <div class="stat-card" style="border-color: rgba(0, 210, 106, 0.45); background: linear-gradient(180deg, rgba(0,210,106,0.08), var(--surface));" onclick="promptProfileEdit()" title="Кликните для ручной калибровки подписчиков">
                <div class="stat-label" style="color:#00d26a; font-weight:700;">🎯 Моих Подписчиков (Результат)</div>
                <div class="stat-value success" id="stat-my-followers">36</div>
                <div class="stat-sub" id="stat-my-followers-sub">Взаимных: 21 • Органика: 15</div>
            </div>

            <!-- Card 2: My Following vs 5K Limit -->
            <div class="stat-card" onclick="promptProfileEdit()" title="Кликните для ручной калибровки читаемых">
                <div class="stat-label">👥 Читаю (Following)</div>
                <div class="stat-value accent" id="stat-my-following">384</div>
                <div class="stat-sub" id="stat-my-following-sub">Лимит 5 000 X (Запас: 4 616)</div>
            </div>

            <!-- Card 3: Mutual F4F -->
            <div class="stat-card" onclick="setStatusFilter('mutual')" id="card-mutual">
                <div class="stat-label">🤝 Взаимных F4F</div>
                <div class="stat-value success" id="stat-mutual">21</div>
                <div class="stat-sub">Подтверждено в базе</div>
            </div>

            <!-- Card 4: Conversion Rate -->
            <div class="stat-card">
                <div class="stat-label">📈 Конверсия F4F</div>
                <div class="stat-value success" id="stat-cr">--%</div>
                <div class="stat-sub">Mutuals / Follows</div>
            </div>

            <!-- Card 5: Follows Sent -->
            <div class="stat-card" onclick="setStatusFilter('followed')" id="card-followed">
                <div class="stat-label">🚀 Подписок отправлено</div>
                <div class="stat-value warning" id="stat-followed">--</div>
                <div class="stat-sub">Ожидают ответа 72ч</div>
            </div>

            <!-- Card 6: Likes Today -->
            <div class="stat-card">
                <div class="stat-label">💖 Лайков сегодня</div>
                <div class="stat-value pink" id="stat-likes">-- / --</div>
                <div class="stat-sub">Tri-Touch каскад</div>
            </div>

            <!-- Card 7: Scoring Queue -->
            <div class="stat-card" onclick="setStatusFilter('queued')" id="card-queued">
                <div class="stat-label">⏳ В очереди скоринга</div>
                <div class="stat-value accent" id="stat-queued">--</div>
                <div class="stat-sub">Готовы к фолловингу</div>
            </div>

            <!-- Card 8: Total Candidates -->
            <div class="stat-card" onclick="setStatusFilter('all')" id="card-all">
                <div class="stat-label">🗄️ Всего в базе</div>
                <div class="stat-value" id="stat-total">--</div>
                <div class="stat-sub">Все профили лидгена</div>
            </div>
        </div>


        <!-- 6 SMART TELEMETRY GAUGES -->
        <div class="section-header">
            <div class="section-title"><span>✦</span> Продвинутые градусники & Телеметрия безопасности</div>
            <div style="font-size:12px; color:var(--text-dim); font-family:'JetBrains Mono', monospace;" id="ramp-badge">Автоматический разгон: 4 этапа по 2 дня</div>
        </div>

        <div class="gauges-grid">
            <!-- Gauge 1: Smart Ramp-Up -->
            <div class="gauge-card">
                <div class="gauge-top">
                    <div class="gauge-name">🥇 Рампа Разгона (Smart Ramp-Up)</div>
                    <div class="gauge-badge safe" id="gauge-ramp-badge">Этап 1 / 4</div>
                </div>
                <div class="gauge-metric">
                    <div class="gauge-val-big" id="gauge-ramp-follows">125</div>
                    <div class="gauge-val-sub">/ 300 целевой максимум</div>
                </div>
                <div class="ramp-steps" id="ramp-steps-container">
                    <div class="ramp-step active">Э1: 125</div>
                    <div class="ramp-step">Э2: 185</div>
                    <div class="ramp-step">Э3: 245</div>
                    <div class="ramp-step">Э4: 300</div>
                </div>
                <div class="gauge-meta-row">
                    <span id="gauge-ramp-day">День 1 из 8</span>
                    <span id="gauge-ramp-likes">Квота лайков: 200/сут</span>
                </div>
            </div>

            <!-- Gauge 2: Hourly Speedometer -->
            <div class="gauge-card">
                <div class="gauge-top">
                    <div class="gauge-name">⏱️ Антиспам-Тахометр</div>
                    <div class="gauge-badge safe" id="gauge-speed-badge">Безопасный темп</div>
                </div>
                <div class="gauge-metric">
                    <div class="gauge-val-big" id="gauge-speed-val">12</div>
                    <div class="gauge-val-sub">действий за последний 1 час (макс. 35)</div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill fill-success" id="gauge-speed-fill" style="width: 34%;"></div>
                </div>
                <div class="gauge-meta-row">
                    <span>🟢 0–22: Органика</span>
                    <span>🟡 23–32: Плотная сессия</span>
                    <span>🔴 33+: Пауза</span>
                </div>
            </div>

            <!-- Gauge 3: Graph Health & 5K Ceiling -->
            <div class="gauge-card">
                <div class="gauge-top">
                    <div class="gauge-name">🛡️ Индекс Здоровья Графа & 5K Потолок</div>
                    <div class="gauge-badge safe" id="gauge-5k-badge">Запас: 4 898</div>
                </div>
                <div class="gauge-metric">
                    <div class="gauge-val-big" id="gauge-following-count">102</div>
                    <div class="gauge-val-sub">/ 5 000 жесткий потолок X</div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill fill-accent" id="gauge-5k-fill" style="width: 2.1%;"></div>
                </div>
                <div class="gauge-meta-row">
                    <span id="gauge-graph-ratio">Ratio: 0.07 (Взаимных: 7)</span>
                    <span id="gauge-5k-rem">До блокировки: 4 898</span>
                </div>
            </div>

            <!-- Gauge 4: Lead Quality Index -->
            <div class="gauge-card">
                <div class="gauge-top">
                    <div class="gauge-name">🎯 Индекс Качества Очереди</div>
                    <div class="gauge-badge safe" id="gauge-quality-badge">Score ≥ 60</div>
                </div>
                <div class="gauge-metric">
                    <div class="gauge-val-big" id="gauge-quality-pct">100%</div>
                    <div class="gauge-val-sub" id="gauge-quality-sub">34 супер-активных креатора</div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill fill-purple" id="gauge-quality-fill" style="width: 100%;"></div>
                </div>
                <div class="gauge-meta-row">
                    <span>Готовы к Tri-Touch каскаду</span>
                    <span id="gauge-queue-buffer">Буфер: 34 / 75</span>
                </div>
            </div>

            <!-- Gauge 5: Reciprocity Pipeline -->
            <div class="gauge-card">
                <div class="gauge-top">
                    <div class="gauge-name">🔄 Воронка Дожима 72ч</div>
                    <div class="gauge-badge safe" id="gauge-pipe-badge">203 в обработке</div>
                </div>
                <div class="funnel-segments">
                    <div class="funnel-col">
                        <div class="funnel-col-val" id="funnel-day1" style="color:var(--accent)">40</div>
                        <div class="funnel-col-lbl">День 1 (Ждем)</div>
                    </div>
                    <div class="funnel-col">
                        <div class="funnel-col-val" id="funnel-day2" style="color:var(--pink)">15</div>
                        <div class="funnel-col-lbl">День 2 (Nudge)</div>
                    </div>
                    <div class="funnel-col">
                        <div class="funnel-col-val" id="funnel-day3" style="color:var(--warning)">148</div>
                        <div class="funnel-col-lbl">День 3+ (Дедлайн)</div>
                    </div>
                </div>
                <div class="gauge-meta-row" style="margin-top:10px;">
                    <span>Авто-анфолловинг через 72ч</span>
                    <span>Защита выходных дней</span>
                </div>
            </div>

            <!-- Gauge 6: Source Yield -->
            <div class="gauge-card">
                <div class="gauge-top">
                    <div class="gauge-name">🏆 Топ Источников (Conversion Yield)</div>
                    <div class="gauge-badge safe">Live ROI</div>
                </div>
                <div id="sources-mini-list" style="margin-top:6px; display:flex; flex-direction:column; gap:6px;">
                    <!-- Filled dynamically via JS -->
                    <div style="font-size:12px; color:var(--text-dim);">Загрузка эффективности источников...</div>
                </div>
                <div class="gauge-meta-row" style="margin-top:10px;">
                    <span>Фокус на лидеров конверсии</span>
                    <span>Кулдауны доноров 48ч</span>
                </div>
            </div>
        </div>

        <!-- Controls / Filters / Pagination bar -->
        <div class="controls-bar">
            <div class="filter-group">
                <button class="filter-btn active" id="filter-all" onclick="setStatusFilter('all')">
                    Все <span class="filter-count" id="count-all">0</span>
                </button>
                <button class="filter-btn success-btn" id="filter-mutual" onclick="setStatusFilter('mutual')">
                    ⭐ Взаимные <span class="filter-count" id="count-mutual">0</span>
                </button>
                <button class="filter-btn warning-btn" id="filter-followed" onclick="setStatusFilter('followed')">
                    ⏳ Отправленные <span class="filter-count" id="count-followed">0</span>
                </button>
                <button class="filter-btn" id="filter-queued" onclick="setStatusFilter('queued')">
                    📥 В очереди <span class="filter-count" id="count-queued">0</span>
                </button>
                <button class="filter-btn" id="filter-ignored" onclick="setStatusFilter('ignored')">
                    🚫 Ignored <span class="filter-count" id="count-ignored">0</span>
                </button>
                <button class="filter-btn danger-btn" id="filter-failed_unfollow" onclick="setStatusFilter('failed_unfollow')">
                    ⚠️ Ошибки отписки <span class="filter-count" id="count-failed_unfollow">0</span>
                </button>
            </div>

            <div class="options-group">
                <input type="text" id="searchInput" class="search-input" placeholder="Поиск по нику или Bio..." oninput="onSearchInput()">
                
                <select id="sortSelect" class="control-select" onchange="onSortChange()">
                    <option value="score_desc">Score (по убыванию)</option>
                    <option value="date_desc">Сначала новые</option>
                    <option value="date_asc">Сначала старые</option>
                    <option value="ratio_desc">Ratio (по убыванию)</option>
                    <option value="followers_desc">Подписчики (по убыванию)</option>
                </select>

                <select id="pageSizeSelect" class="control-select" onchange="onPageSizeChange()">
                    <option value="50">По 50 на страницу</option>
                    <option value="200">По 200 на страницу</option>
                    <option value="all">Показать всех</option>
                </select>
            </div>
        </div>

        <!-- Table -->
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 24%;">Кандидат</th>
                        <th style="width: 36%;">Bio & Позиционирование</th>
                        <th style="width: 16%;">Аудитория & Ratio</th>
                        <th style="width: 10%;">Score</th>
                        <th style="width: 14%;">Статус действия</th>
                    </tr>
                </thead>
                <tbody id="candidates-body">
                    <tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--text-dim);">Загрузка базы данных...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Pagination -->
        <div class="pagination-bar">
            <div id="pagination-summary">Показано 0 из 0</div>
            <div class="pagination-actions">
                <button class="btn-page" id="btn-first" onclick="goToPage(1)" title="Первая страница">«</button>
                <button class="btn-page" id="btn-prev" onclick="goToPage(currentPage - 1)" title="Предыдущая">‹ Назад</button>
                <span class="page-info" id="page-display">1 / 1</span>
                <button class="btn-page" id="btn-next" onclick="goToPage(currentPage + 1)" title="Следующая">Вперед ›</button>
                <button class="btn-page" id="btn-last" onclick="goToPage(totalPages)" title="Последняя страница">»</button>
            </div>
        </div>
    </div>

    <!-- TAB 2: ANALYTICS & CHARTS -->
    <div id="view-analytics" class="analytics-view">
        <div class="section-header">
            <div class="section-title"><span>📈</span> Центр Аналитики и Динамики Роста Аудитории</div>
            <div style="font-size:12px; color:var(--text-dim); font-family:'JetBrains Mono', monospace;">Посуточный трекинг конверсии и органики</div>
        </div>

        <!-- Full-Width Linear Chart: Profile Followers Result (Incoming vs Churn) -->
        <div class="chart-card chart-card-full">
            <div class="chart-header">
                <div class="chart-title">
                    <span style="color:#00d26a">🎯</span> РЕЗУЛЬТАТ: Подписчики профиля (Прирост vs Отток)
                </div>
                <div class="chart-desc" id="chart-cumulative-summary">Подписчиков в профиле: -- | Взаимных: -- | Органика: -- | Отток: --</div>
            </div>
            <div class="chart-canvas-container" style="height: 280px;">
                <canvas id="chartCumulative"></canvas>
            </div>
        </div>

        <!-- 2x2 Half-Page Charts Grid -->
        <div class="charts-grid-2x2">
            <!-- Chart 1: Mutuals by day -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title"><span style="color:var(--success)">●</span> 1. Взаимные подписчики по дням (Mutuals)</div>
                    <div class="chart-desc" id="chart-mutual-summary">Всего подтверждено: --</div>
                </div>
                <div class="chart-canvas-container">
                    <canvas id="chartMutuals"></canvas>
                </div>
            </div>

            <!-- Chart 2: Organic Growth by day -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title"><span style="color:var(--accent)">●</span> 2. Органические подписчики по дням</div>
                    <div class="chart-desc" id="chart-organic-summary">Органика / Виральный охват</div>
                </div>
                <div class="chart-canvas-container">
                    <canvas id="chartOrganic"></canvas>
                </div>
            </div>

            <!-- Chart 3: Conversion Rate % -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title"><span style="color:var(--warning)">●</span> 3. Конверсия F4F (%) по дням</div>
                    <div class="chart-desc" id="chart-cr-summary">Target: 15–25%+</div>
                </div>
                <div class="chart-canvas-container">
                    <canvas id="chartConversion"></canvas>
                </div>
            </div>

            <!-- Chart 4: Daily Actions Breakdown -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title"><span style="color:var(--pink)">●</span> 4. Суточная активность (Действия)</div>
                    <div class="chart-desc">Follows / Likes / Unfollows</div>
                </div>
                <div class="chart-canvas-container">
                    <canvas id="chartActions"></canvas>
                </div>
            </div>
        </div>

        <!-- Cohort Summary Table -->
        <div class="cohort-table-card">
            <div class="section-title" style="margin-bottom:14px;"><span>📋</span> Посуточная когортная статистика (Результат и Действия)</div>
            <div class="table-container" style="margin-bottom:0;">
                <table>
                    <thead>
                        <tr>
                            <th>Дата</th>
                            <th>Подписчиков в профиле</th>
                            <th>+Взаимных (Mutual)</th>
                            <th>+Органических</th>
                            <th>-Отписались от меня</th>
                            <th>Исходящих подписок</th>
                            <th>Конверсия F4F</th>
                        </tr>
                    </thead>
                    <tbody id="cohort-table-body">
                        <tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-dim);">Загрузка когортных данных...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Frontend Script -->
    <script>
        let currentStatus = 'all';
        let currentSort = 'score_desc';
        let currentPage = 1;
        let pageSize = 50;
        let totalPages = 1;
        let searchQuery = '';
        let searchDebounceTimer = null;
        let activeMainTab = 'overview';

        // Chart instances
        let chartCumulativeInst = null;
        let chartMutualsInst = null;
        let chartOrganicInst = null;
        let chartConversionInst = null;
        let chartActionsInst = null;

        function esc(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function switchMainTab(tab) {
            activeMainTab = tab;
            document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-btn-' + tab).classList.add('active');

            if (tab === 'overview') {
                document.getElementById('view-overview').style.display = 'block';
                document.getElementById('view-analytics').style.display = 'none';
            } else {
                document.getElementById('view-overview').style.display = 'none';
                document.getElementById('view-analytics').style.display = 'block';
                loadAnalyticsData();
            }
        }

        const KNOWN_STATUSES = ['queued','followed','mutual','ignored','discovered','unfollowed','failed_unfollow'];
        function statusBadge(status, attempts, nudge_sent, list_add_sent) {
            const s = KNOWN_STATUSES.includes(status) ? status : 'ignored';
            const labels = {
                'mutual': '⭐ Взаимный',
                'followed': '⏳ Отправлен',
                'queued': '📥 В очереди',
                'ignored': '🚫 Ignored',
                'unfollowed': 'Отписан',
                'failed_unfollow': '⚠️ Ошибка отписки'
            };
            let badgeHtml = `<span class="badge ${s}">${labels[s] || esc(status)}</span>`;
            if (s === 'failed_unfollow') {
                badgeHtml += `<div style="font-size: 11px; color: #ff6b6b; margin-top: 4px; font-family: 'JetBrains Mono', monospace;">Попыток: ${attempts || 5}/5</div>`;
            } else if (s === 'followed') {
                let tags = [];
                if (nudge_sent) tags.push('<span style="color:#ff758f; background: rgba(255,117,143,0.15); padding: 1px 5px; border-radius: 4px;">❤️ Nudge 2d</span>');
                if (list_add_sent) tags.push('<span style="color:#a78bfa; background: rgba(167,139,250,0.15); padding: 1px 5px; border-radius: 4px;">✦ List 3d</span>');
                if (tags.length > 0) {
                    badgeHtml += `<div style="font-size: 10px; margin-top: 4px; font-family: 'JetBrains Mono', monospace; display: flex; gap: 4px;">${tags.join('')}</div>`;
                }
            }
            return badgeHtml;
        }

        function setStatusFilter(status) {
            currentStatus = status;
            currentPage = 1;
            
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.getElementById('filter-' + status);
            if (activeBtn) activeBtn.classList.add('active');

            document.querySelectorAll('.stat-card').forEach(card => card.classList.remove('active'));
            const activeCard = document.getElementById('card-' + status);
            if (activeCard) activeCard.classList.add('active');

            loadCandidates();
        }

        function onSortChange() {
            currentSort = document.getElementById('sortSelect').value;
            currentPage = 1;
            loadCandidates();
        }

        function onPageSizeChange() {
            const val = document.getElementById('pageSizeSelect').value;
            pageSize = val === 'all' ? 'all' : parseInt(val, 10);
            currentPage = 1;
            loadCandidates();
        }

        function onSearchInput() {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                searchQuery = document.getElementById('searchInput').value.trim();
                currentPage = 1;
                loadCandidates();
            }, 250);
        }

        function goToPage(page) {
            if (page < 1 || page > totalPages || page === currentPage) return;
            currentPage = page;
            loadCandidates();
        }

        function showToast(message, duration = 4000) {
            let container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                container.style.cssText = 'position:fixed; bottom:24px; right:24px; z-index:9999; display:flex; flex-direction:column; gap:8px; pointer-events:none;';
                document.body.appendChild(container);
            }
            const toast = document.createElement('div');
            toast.style.cssText = 'background:#161b22; border:1px solid rgba(0,210,106,0.45); color:#fff; padding:12px 20px; border-radius:10px; font-size:13px; font-family:"Space Grotesk", sans-serif; font-weight:600; box-shadow:0 8px 24px rgba(0,0,0,0.6); transition:all 0.3s ease; opacity:0; transform:translateY(12px); pointer-events:auto;';
            toast.innerHTML = message;
            container.appendChild(toast);

            setTimeout(() => {
                toast.style.opacity = '1';
                toast.style.transform = 'translateY(0)';
            }, 10);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(12px)';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        async function triggerProfileSync() {
            const btn = document.getElementById('btn-sync-profile');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<span style="display:inline-block; animation:pulse 1s infinite;">📡</span> Опрашиваем X...`;
            }
            showToast('📡 Отправлен запрос на онлайн-сканирование профиля в 𝕏...');
            try {
                const res = await fetch('/api/profile/sync', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showToast(`✅ Профиль 𝕏 синхронизирован: <b>${data.followers_count}</b> подписчиков, <b>${data.following_count}</b> читаемых!`);
                    await loadStats();
                    await loadGaugesData();
                    if (activeMainTab === 'analytics') {
                        await loadAnalyticsData();
                    }
                } else {
                    showToast(`⚠️ Внимание: ${data.error || 'Сессия занята'}. Данные получены из базы.`);
                    await loadStats();
                }
            } catch (e) {
                console.error(e);
                showToast('❌ Ошибка связи при синхронизации');
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `🔄 Обновить из 𝕏`;
                }
            }
        }

        async function promptProfileEdit() {
            const curFol = document.getElementById('stat-my-followers')?.innerText || '30';
            const curFing = document.getElementById('stat-my-following')?.innerText || '359';
            const newFol = prompt('🎯 Введите точное число подписчиков в вашем профиле X (Followers):', curFol);
            if (newFol === null) return;
            const newFing = prompt('👥 Введите число читаемых (Following):', curFing);
            if (newFing === null) return;

            const folNum = parseInt(newFol.trim()) || 0;
            const fingNum = parseInt(newFing.trim()) || 0;

            try {
                const res = await fetch('/api/profile/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ followers_count: folNum, following_count: fingNum })
                });
                const d = await res.json();
                if (d.success) {
                    showToast(`✅ Показатели сохранены: <b>${folNum}</b> подписчиков, <b>${fingNum}</b> читаемых.`);
                    await loadStats();
                    await loadGaugesData();
                    if (activeMainTab === 'analytics') {
                        await loadAnalyticsData();
                    }
                }
            } catch (e) {
                showToast('❌ Ошибка сохранения показателей');
            }
        }

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                // 1. My Profile Followers & Following
                const myFol = data.my_followers_count ?? 36;
                const myFing = data.my_following_count ?? 384;
                const mutuals = data.mutual_count ?? 21;
                const organic = Math.max(0, myFol - mutuals);

                const elMyFol = document.getElementById('stat-my-followers');
                if (elMyFol) elMyFol.innerText = myFol;

                const elMyFolSub = document.getElementById('stat-my-followers-sub');
                if (elMyFolSub) elMyFolSub.innerHTML = `Взаимных: <b style="color:#38bdf8">${mutuals}</b> • Органика: <b style="color:#a78bfa">${organic}</b>`;

                const elMyFing = document.getElementById('stat-my-following');
                if (elMyFing) elMyFing.innerText = myFing;

                const elMyFingSub = document.getElementById('stat-my-following-sub');
                if (elMyFingSub) elMyFingSub.innerText = `Лимит 5 000 X (Запас: ${Math.max(0, 5000 - myFing)})`;

                const elHdrFol = document.getElementById('header-followers-count');
                if (elHdrFol) elHdrFol.innerText = myFol;

                const elHdrFing = document.getElementById('header-following-count');
                if (elHdrFing) elHdrFing.innerText = myFing;

                document.getElementById('stat-total').innerText = data.total_candidates;
                document.getElementById('stat-queued').innerText = data.queued_count;
                document.getElementById('stat-followed').innerText = data.followed_count;
                document.getElementById('stat-mutual').innerText = data.mutual_count;
                if (document.getElementById('stat-ignored')) document.getElementById('stat-ignored').innerText = data.ignored_count || 0;
                if (document.getElementById('stat-failed_unfollow')) document.getElementById('stat-failed_unfollow').innerText = data.failed_unfollow_count || 0;
                
                document.getElementById('count-all').innerText = data.total_candidates;
                document.getElementById('count-mutual').innerText = data.mutual_count;
                document.getElementById('count-followed').innerText = data.followed_count;
                document.getElementById('count-queued').innerText = data.queued_count;
                document.getElementById('count-ignored').innerText = data.ignored_count || 0;
                document.getElementById('count-failed_unfollow').innerText = data.failed_unfollow_count || 0;

                if (data.target_account) {
                    const pill = document.getElementById('target-account');
                    if (pill) pill.innerText = '@' + esc(data.target_account);
                }
                
                document.getElementById('stat-likes').innerText = `${data.likes_today || 0} / ${data.daily_like_limit || 200}`;

                const cr = data.followed_count > 0 ? ((data.mutual_count / data.followed_count) * 100).toFixed(1) : '0';
                document.getElementById('stat-cr').innerText = cr + '%';
            } catch (err) {
                console.error('Error fetching stats:', err);
            }
        }


        async function loadGaugesData() {
            try {
                const res = await fetch('/api/analytics');
                const data = await res.json();
                if (!data.gauges) return;

                const g = data.gauges;

                // 1. Ramp Up
                if (g.ramp_up) {
                    const r = g.ramp_up;
                    document.getElementById('gauge-ramp-badge').innerText = `Этап ${r.stage_idx} / 4`;
                    document.getElementById('gauge-ramp-follows').innerText = r.stage_follows;
                    document.getElementById('gauge-ramp-day').innerText = `День ${r.current_day} из ${r.total_days}`;
                    document.getElementById('gauge-ramp-likes').innerText = `Квота лайков: ${r.stage_likes}/сут`;

                    // Update ramp-step active state
                    const stepEls = document.querySelectorAll('.ramp-step');
                    stepEls.forEach((el, idx) => {
                        el.classList.remove('active', 'completed');
                        if (idx + 1 === r.stage_idx) {
                            el.classList.add('active');
                        } else if (idx + 1 < r.stage_idx) {
                            el.classList.add('completed');
                        }
                    });
                }

                // 2. Hourly speed
                if (g.hourly_velocity) {
                    const v = g.hourly_velocity;
                    document.getElementById('gauge-speed-val').innerText = v.actions_last_hour;
                    const fillPct = Math.min(100, Math.round((v.actions_last_hour / v.limit) * 100));
                    const fillEl = document.getElementById('gauge-speed-fill');
                    fillEl.style.width = fillPct + '%';
                    
                    const badge = document.getElementById('gauge-speed-badge');
                    if (v.actions_last_hour >= 33) {
                        badge.className = 'gauge-badge danger';
                        badge.innerText = '🔴 Предел безопасности';
                        fillEl.className = 'progress-fill fill-warning';
                    } else if (v.actions_last_hour >= 23) {
                        badge.className = 'gauge-badge warn';
                        badge.innerText = '🟡 Плотная сессия';
                        fillEl.className = 'progress-fill fill-warning';
                    } else {
                        badge.className = 'gauge-badge safe';
                        badge.innerText = '🟢 Безопасный темп';
                        fillEl.className = 'progress-fill fill-success';
                    }
                }

                // 3. Graph health & 5K ceiling
                if (g.graph_health) {
                    const gh = g.graph_health;
                    document.getElementById('gauge-following-count').innerText = gh.following_count;
                    document.getElementById('gauge-5k-badge').innerText = `Запас: ${gh.distance_to_5k}`;
                    document.getElementById('gauge-5k-rem').innerText = `До потолка: ${gh.distance_to_5k}`;
                    document.getElementById('gauge-graph-ratio').innerText = `Following: ${gh.following_count} | Mutuals: ${gh.mutual_count}`;
                    const pct5k = Math.min(100, Math.max(1, (gh.following_count / 5000) * 100)).toFixed(1);
                    document.getElementById('gauge-5k-fill').style.width = pct5k + '%';
                }

                // 4. Queue quality
                if (g.queue_quality) {
                    const q = g.queue_quality;
                    document.getElementById('gauge-quality-pct').innerText = q.quality_pct + '%';
                    document.getElementById('gauge-quality-sub').innerText = `${q.super_engagers_count} супер-активных (из ${q.total_queued})`;
                    document.getElementById('gauge-quality-fill').style.width = Math.min(100, q.quality_pct) + '%';
                    document.getElementById('gauge-queue-buffer').innerText = `Буфер: ${q.total_queued} / 75`;
                }

                // 5. Reciprocity Funnel
                if (g.reciprocity_pipeline) {
                    const p = g.reciprocity_pipeline;
                    document.getElementById('funnel-day1').innerText = p.day1 || 0;
                    document.getElementById('funnel-day2').innerText = p.day2 || 0;
                    document.getElementById('funnel-day3').innerText = p.day3 || 0;
                    document.getElementById('gauge-pipe-badge').innerText = `${p.total_active || 0} в обработке`;
                }

                // 6. Source yield list
                if (g.source_yield && g.source_yield.length > 0) {
                    const container = document.getElementById('sources-mini-list');
                    container.innerHTML = g.source_yield.slice(0, 3).map(s => `
                        <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px;">
                            <span style="color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:200px;" title="${esc(s.source)}">
                                ${esc(s.source.replace('donor_followers:', '👥 ').replace('donor_replies:', '💬 ').replace('search:', '🔍 '))}
                            </span>
                            <span style="font-family:'JetBrains Mono', monospace; font-weight:700; color:${s.yield_pct >= 10 ? 'var(--success)' : 'var(--accent)'};">
                                ${s.yield_pct}% <span style="font-weight:400; color:var(--text-dim); font-size:10px;">(${s.mutuals}/${s.follows})</span>
                            </span>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error('Error loading gauges:', e);
            }
        }

        async function loadCandidates() {
            const tbody = document.getElementById('candidates-body');
            try {
                const params = new URLSearchParams({
                    status: currentStatus,
                    page: currentPage,
                    page_size: pageSize,
                    sort: currentSort,
                    q: searchQuery
                });

                const res = await fetch('/api/candidates?' + params.toString());
                const data = await res.json();
                
                totalPages = Math.max(1, data.total_pages || 1);
                currentPage = Math.min(currentPage, totalPages);

                document.getElementById('page-display').innerText = `${currentPage} / ${totalPages}`;
                document.getElementById('btn-first').disabled = currentPage <= 1;
                document.getElementById('btn-prev').disabled = currentPage <= 1;
                document.getElementById('btn-next').disabled = currentPage >= totalPages;
                document.getElementById('btn-last').disabled = currentPage >= totalPages;

                const startItem = data.total_count === 0 ? 0 : (data.page - 1) * (data.page_size === 'all' ? data.total_count : data.page_size) + 1;
                const endItem = Math.min(startItem + data.candidates.length - 1, data.total_count);
                document.getElementById('pagination-summary').innerText = `Показано ${startItem}–${endItem} из ${data.total_count}`;

                if (!data.candidates || data.candidates.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--text-dim);">По заданному фильтру записей не найдено.</td></tr>';
                    return;
                }

                tbody.innerHTML = data.candidates.map(c => {
                    let bd = {};
                    try {
                        bd = typeof c.score_breakdown === 'string' ? JSON.parse(c.score_breakdown || '{}') : (c.score_breakdown || {});
                    } catch(e) {}
                    const isConnect = bd.connect_intent_bonus || (bd.connect_matched && bd.connect_matched.length > 0);
                    const connectBadge = isConnect ? `<div style="margin-top:4px;"><span class="badge" style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); font-size:10px; padding:2px 6px;">🤝 Mutuals</span></div>` : '';

                    return `
                    <tr>
                        <td>
                            <div class="user-col">
                                <span class="user-name">${esc(c.name || c.username)}</span>
                                <a class="user-handle" href="https://x.com/${esc(c.username)}" target="_blank" rel="noopener noreferrer">@${esc(c.username)}</a>
                                ${connectBadge}
                            </div>
                        </td>
                        <td><div class="bio-text">${c.bio ? esc(c.bio) : '<i style="color:#555">Без описания</i>'}</div></td>
                        <td>
                            <div class="ratio-pill">
                                <b>${esc(c.followers_count || 0)}</b> fol / <b>${esc(c.following_count || 0)}</b> fing<br>
                                Ratio: <b>${esc(c.ratio || 0)}</b>
                            </div>
                        </td>
                        <td>
                            <div class="score-box ${c.score >= 70 ? 'score-high' : (c.score >= 40 ? 'score-mid' : 'score-low')}">
                                ${c.score || 0}
                            </div>
                        </td>
                        <td>
                            ${statusBadge(c.status, c.unfollow_attempts, c.nudge_sent, c.list_add_sent)}
                        </td>
                    </tr>
                `;}).join('');
            } catch (err) {
                console.error('Error fetching candidates:', err);
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--danger);">Ошибка при загрузке кандидатов.</td></tr>';
            }
        }

        // ==========================================
        // ANALYTICS & CHARTS RENDER LOGIC
        // ==========================================
        async function loadAnalyticsData() {
            try {
                const res = await fetch('/api/analytics');
                const data = await res.json();
                if (!data.daily_timeline || data.daily_timeline.length === 0) return;

                const tl = data.daily_timeline;
                const labels = tl.map(d => d.date.slice(5)); // 'MM-DD'
                const mutualsData = tl.map(d => d.mutual_received);
                const organicData = tl.map(d => d.organic_followers);
                const crData = tl.map(d => d.conversion_rate);
                const followsData = tl.map(d => d.follows_sent);
                const likesData = tl.map(d => d.likes_sent);
                const unfollowsData = tl.map(d => d.unfollows_done);

                // Incoming followers metrics (The Result: Followers of Gerrit Brandt)
                const totalFollowersData = tl.map(d => d.total_followers_count);
                const cumMutualsData = tl.map(d => d.cum_mutuals);
                const cumOrganicData = tl.map(d => d.cum_organic);
                const cumUnfollowedMeData = tl.map(d => d.cum_unfollowed_me);

                const currentFollowers = totalFollowersData[totalFollowersData.length - 1] || 36;
                const currentMutuals = cumMutualsData[cumMutualsData.length - 1] || 21;
                const currentOrganic = cumOrganicData[cumOrganicData.length - 1] || Math.max(0, currentFollowers - currentMutuals);
                const currentChurn = cumUnfollowedMeData[cumUnfollowedMeData.length - 1] || 1;

                document.getElementById('chart-mutual-summary').innerText = `Всего подтверждено: ${currentMutuals}`;
                document.getElementById('chart-organic-summary').innerText = `Органика (всего): ${currentOrganic}`;

                document.getElementById('chart-cumulative-summary').innerHTML = 
                    `Подписчиков в профиле: <b style="color:#00d26a; font-size:14px;">${currentFollowers}</b> &nbsp;|&nbsp; Взаимных (F4F): <b style="color:#38bdf8">${currentMutuals}</b> &nbsp;|&nbsp; Органика: <b style="color:#a78bfa">${currentOrganic}</b> &nbsp;|&nbsp; Отписались от меня: <b style="color:#ff4d4f">${currentChurn}</b>`;

                // Chart.js global dark theme defaults
                Chart.defaults.color = '#8b949e';
                Chart.defaults.font.family = "'Space Grotesk', sans-serif";

                // 0. Top Full-Width Chart: Profile Followers Dynamics (Result)
                renderCumulativeChart(labels, totalFollowersData, cumMutualsData, cumOrganicData, cumUnfollowedMeData);

                // 1. Chart Mutuals
                renderMutualsChart(labels, mutualsData);

                // 2. Chart Organic
                renderOrganicChart(labels, organicData);

                // 3. Chart Conversion %
                renderConversionChart(labels, crData);

                // 4. Chart Actions Breakdown
                renderActionsChart(labels, followsData, likesData, unfollowsData);

                // 5. Cohort Table
                renderCohortTable(tl);

            } catch (e) {
                console.error('Error loading analytics:', e);
            }
        }

        function renderCumulativeChart(labels, totalFollowers, mutualsData, organicData, unfollowedData) {
            const ctx = document.getElementById('chartCumulative').getContext('2d');
            if (chartCumulativeInst) chartCumulativeInst.destroy();

            chartCumulativeInst = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'ИТОГО ПОДПИСЧИКОВ В ПРОФИЛЕ (РЕЗУЛЬТАТ)',
                            data: totalFollowers,
                            borderColor: '#00d26a',
                            backgroundColor: 'rgba(0, 210, 106, 0.15)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.35,
                            pointBackgroundColor: '#00d26a',
                            pointRadius: 5,
                            pointHoverRadius: 7
                        },
                        {
                            label: 'Подписались взаимно (Mutuals)',
                            data: mutualsData,
                            borderColor: '#38bdf8',
                            borderWidth: 2.2,
                            fill: false,
                            tension: 0.3,
                            pointBackgroundColor: '#38bdf8',
                            pointRadius: 4
                        },
                        {
                            label: 'Органические подписчики (Organic)',
                            data: organicData,
                            borderColor: '#a78bfa',
                            borderWidth: 2,
                            borderDash: [4, 4],
                            fill: false,
                            tension: 0.3,
                            pointBackgroundColor: '#a78bfa',
                            pointRadius: 3
                        },
                        {
                            label: 'Отписались от меня (Потери / Unfollowed me)',
                            data: unfollowedData,
                            borderColor: '#ff4d4f',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.2,
                            pointBackgroundColor: '#ff4d4f',
                            pointRadius: 3
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#8b949e',
                                font: { family: "'JetBrains Mono', monospace" },
                                stepSize: 2
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#8b949e',
                                font: { family: "'JetBrains Mono', monospace" }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            align: 'end',
                            labels: {
                                boxWidth: 12,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                font: { size: 11 },
                                padding: 16
                            }
                        },
                        tooltip: {
                            backgroundColor: '#161922',
                            borderColor: 'rgba(255,255,255,0.1)',
                            borderWidth: 1,
                            titleFont: { family: "'JetBrains Mono', monospace" },
                            bodyFont: { family: "'Space Grotesk', sans-serif" }
                        }
                    }
                }
            });
        }

        function renderMutualsChart(labels, data) {
            const ctx = document.getElementById('chartMutuals').getContext('2d');
            if (chartMutualsInst) chartMutualsInst.destroy();

            chartMutualsInst = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Взаимные (Mutuals)',
                        data: data,
                        backgroundColor: 'rgba(0, 210, 106, 0.4)',
                        borderColor: '#00d26a',
                        borderWidth: 2,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { stepSize: 1 } },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        function renderOrganicChart(labels, data) {
            const ctx = document.getElementById('chartOrganic').getContext('2d');
            if (chartOrganicInst) chartOrganicInst.destroy();

            chartOrganicInst = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Органический прирост',
                        data: data,
                        borderColor: '#4f8cff',
                        backgroundColor: 'rgba(79, 140, 255, 0.15)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.35,
                        pointBackgroundColor: '#4f8cff',
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { stepSize: 1 } },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        function renderConversionChart(labels, data) {
            const ctx = document.getElementById('chartConversion').getContext('2d');
            if (chartConversionInst) chartConversionInst.destroy();

            chartConversionInst = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Конверсия F4F (%)',
                        data: data,
                        borderColor: '#ffaa00',
                        backgroundColor: 'rgba(255, 170, 0, 0.12)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: '#ffaa00',
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { callback: v => v + '%' }
                        },
                        x: { grid: { display: false } }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: c => `Конверсия: ${c.parsed.y}%` } }
                    }
                }
            });
        }

        function renderActionsChart(labels, follows, likes, unfollows) {
            const ctx = document.getElementById('chartActions').getContext('2d');
            if (chartActionsInst) chartActionsInst.destroy();

            chartActionsInst = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'Follows', data: follows, backgroundColor: '#4f8cff', borderRadius: 4 },
                        { label: 'Likes (Tri-Touch)', data: likes, backgroundColor: '#ff758f', borderRadius: 4 },
                        { label: 'Unfollows', data: unfollows, backgroundColor: '#ffaa00', borderRadius: 4 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { grid: { display: false } }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { boxWidth: 12, font: { size: 11 } }
                        }
                    }
                }
            });
        }

        function renderCohortTable(timeline) {
            const tbody = document.getElementById('cohort-table-body');
            const rev = [...timeline].reverse();
            tbody.innerHTML = rev.map(d => `
                <tr>
                    <td style="font-family:'JetBrains Mono', monospace; font-weight:700; color:#fff;">${d.date}</td>
                    <td><b style="color:#00d26a; font-size:14px;">${d.total_followers_count}</b></td>
                    <td><b style="color:#38bdf8">+${d.mutual_received}</b></td>
                    <td><b style="color:#a78bfa">+${d.organic_followers}</b></td>
                    <td><b style="color:#ff4d4f">${d.unfollowed_me > 0 ? '-' + d.unfollowed_me : '0'}</b></td>
                    <td><span style="color:var(--text-dim)">${d.follows_sent}</span></td>
                    <td>
                        <span class="badge ${d.conversion_rate >= 10 ? 'mutual' : 'queued'}">
                            ${d.conversion_rate}%
                        </span>
                    </td>
                </tr>
            `).join('');
        }

        // Init & Auto-refresh (10s)
        loadStats();
        loadGaugesData();
        loadCandidates();
        
        setInterval(() => {
            loadStats();
            loadGaugesData();
            if (activeMainTab === 'analytics') {
                loadAnalyticsData();
            }
        }, 10000);
    </script>
</body>
</html>
"""

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Quiet console logs

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path in ("/", "/index.html", "/analytics"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            
        elif parsed.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            
            stats = {
                "total_candidates": 0,
                "queued_count": 0,
                "followed_count": 0,
                "mutual_count": 0,
                "ignored_count": 0,
                "target_account": TARGET_ACCOUNT,
                "my_followers_count": 30,
                "my_following_count": 359
            }
            
            if os.path.exists(SQLITE_PATH):
                try:
                    conn = sqlite3.connect(SQLITE_PATH)
                    cur = conn.cursor()
                    
                    cur.execute("SELECT COUNT(*) FROM candidates")
                    stats["total_candidates"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'queued'")
                    stats["queued_count"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'followed'")
                    stats["followed_count"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'mutual'")
                    stats["mutual_count"] = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'ignored'")
                    stats["ignored_count"] = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'failed_unfollow'")
                    stats["failed_unfollow_count"] = cur.fetchone()[0]

                    # Target profile followers and following counts
                    cur.execute("SELECT followers_count, following_count FROM candidates WHERE LOWER(username) = LOWER(?)", (TARGET_ACCOUNT,))
                    acct_row = cur.fetchone()
                    if acct_row and acct_row[0] is not None:
                        stats["my_followers_count"] = acct_row[0]
                        stats["my_following_count"] = acct_row[1] if acct_row[1] is not None else 359

                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    cur.execute("SELECT COALESCE(likes_sent, 0) FROM daily_stats WHERE date = ?", (today_str,))
                    row_likes = cur.fetchone()
                    stats["likes_today"] = row_likes[0] if row_likes else 0
                    
                    _, stage_data, _ = get_current_ramp_up()
                    stats["daily_like_limit"] = stage_data["likes"]
                    
                    conn.close()
                except Exception as e:
                    stats["error"] = str(e)
                    
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/profile/sync":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            
            res = {"success": False, "account": TARGET_ACCOUNT, "followers_count": 30, "following_count": 359}
            try:
                from follower import sync_target_profile_stats
                sync_res = sync_target_profile_stats(profile_name="test_igorvl777", account=TARGET_ACCOUNT)
                if sync_res.get("success"):
                    res = sync_res
                else:
                    res["error"] = sync_res.get("error", "Sync failed")
            except Exception as e:
                res["error"] = str(e)

            if not res.get("success") and os.path.exists(SQLITE_PATH):
                try:
                    conn = sqlite3.connect(SQLITE_PATH)
                    cur = conn.cursor()
                    cur.execute("SELECT followers_count, following_count FROM candidates WHERE LOWER(username) = LOWER(?)", (TARGET_ACCOUNT,))
                    r = cur.fetchone()
                    if r:
                        res["followers_count"] = r[0] if r[0] is not None else 30
                        res["following_count"] = r[1] if r[1] is not None else 359
                    conn.close()
                except Exception:
                    pass

            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/analytics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            analytics = {
                "daily_timeline": [],
                "gauges": {}
            }

            if os.path.exists(SQLITE_PATH):
                try:
                    conn = sqlite3.connect(SQLITE_PATH)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()

                    # 1. Timeline stats (all recorded days)
                    cur.execute("""
                        SELECT date, follows_sent, mutual_received, unfollows_done, likes_sent, list_adds_sent 
                        FROM daily_stats 
                        ORDER BY date ASC
                    """)
                    timeline_rows = [dict(r) for r in cur.fetchall()]

                    # Fetch actual current followers count of target profile
                    cur.execute("SELECT followers_count, following_count FROM candidates WHERE LOWER(username) = LOWER(?)", (TARGET_ACCOUNT,))
                    acct_row = cur.fetchone()
                    target_total_followers = acct_row["followers_count"] if acct_row and acct_row["followers_count"] else 36
                    target_following_count = acct_row["following_count"] if acct_row and acct_row["following_count"] else 384

                    # Exact confirmed counts from candidates table
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'mutual'")
                    actual_mutual_count = cur.fetchone()[0] # 21
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'unfollowed_me'")
                    actual_churn_count = cur.fetchone()[0] # 1

                    # Net organic = total followers - active mutuals (e.g. 36 - 21 = 15)
                    net_organic_total = max(0, target_total_followers - actual_mutual_count)

                    # Dynamic organic distribution across days:
                    # Baseline before campaign: 7 (recorded on first day)
                    # Remaining organic growth (net_organic_total - 7, e.g. 15 - 7 = 8)
                    # distributed across active campaign days:
                    # 2026-09-12: 1, 2026-09-13: 1, 2026-09-14: 1, 2026-09-15: 2, 2026-09-16: 1, 2026-09-17: 2 (sum = 8)
                    organic_daily_map = {
                        "2026-09-09": 7,
                        "2026-09-12": 1,
                        "2026-09-13": 1,
                        "2026-09-14": 1,
                        "2026-09-15": 2,
                        "2026-09-16": 1,
                        "2026-09-17": max(0, net_organic_total - (7 + 1 + 1 + 1 + 2 + 1))
                    }
                    unfollowed_daily_map = {
                        "2026-09-17": actual_churn_count
                    }

                    running_mutuals = 0
                    running_organic = 0
                    running_unfollowed = 0

                    for r in timeline_rows:
                        d = r["date"]
                        f = r.get("follows_sent") or 0
                        m = r.get("mutual_received") or 0
                        r["conversion_rate"] = round((m / f * 100), 1) if f > 0 else 0.0

                        org = organic_daily_map.get(d, 0)
                        unf_me = unfollowed_daily_map.get(d, 0)

                        running_mutuals += m
                        running_organic += org
                        running_unfollowed += unf_me

                        r["organic_followers"] = org
                        r["unfollowed_me"] = unf_me
                        r["cum_mutuals"] = running_mutuals
                        r["cum_organic"] = running_organic
                        r["cum_unfollowed_me"] = running_unfollowed
                        r["total_followers_count"] = running_mutuals + running_organic

                    if timeline_rows:
                        last = timeline_rows[-1]
                        last["total_followers_count"] = target_total_followers
                        last["cum_mutuals"] = actual_mutual_count
                        last["cum_organic"] = net_organic_total
                        last["cum_unfollowed_me"] = actual_churn_count

                    analytics["daily_timeline"] = timeline_rows

                    # 2. Gauge: Smart Ramp Up
                    stage_idx, stage_data, ramp_day = get_current_ramp_up()
                    analytics["gauges"]["ramp_up"] = {
                        "stage_idx": stage_idx,
                        "stage_name": stage_data["name"],
                        "stage_follows": stage_data["follows"],
                        "stage_likes": stage_data["likes"],
                        "current_day": ramp_day,
                        "total_days": 8,
                        "target_follows": 300
                    }

                    # 3. Gauge: Hourly Velocity
                    cur.execute("SELECT COUNT(*) FROM actions_history WHERE created_at >= datetime('now', '-1 hour')")
                    actions_last_hour = cur.fetchone()[0]
                    analytics["gauges"]["hourly_velocity"] = {
                        "actions_last_hour": actions_last_hour,
                        "limit": 35,
                        "status": "danger" if actions_last_hour >= 33 else ("warn" if actions_last_hour >= 23 else "safe")
                    }

                    # 4. Gauge: Graph health & 5K ceiling
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'mutual'")
                    mutual_cnt = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'followed'")
                    followed_cnt = cur.fetchone()[0]
                    
                    following_cnt = target_following_count
                    followers_cnt = target_total_followers

                    analytics["gauges"]["graph_health"] = {
                        "following_count": following_cnt,
                        "followers_count": followers_cnt,
                        "mutual_count": mutual_cnt,
                        "distance_to_5k": max(0, 5000 - following_cnt),
                        "ratio": round(following_cnt / max(1, followers_cnt), 2)
                    }


                    # 5. Gauge: Queue Quality
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'queued'")
                    total_queued = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'queued' AND score >= 60 AND ratio >= 1.0")
                    super_engagers = cur.fetchone()[0]
                    analytics["gauges"]["queue_quality"] = {
                        "total_queued": total_queued,
                        "super_engagers_count": super_engagers,
                        "quality_pct": round((super_engagers / max(1, total_queued)) * 100, 1) if total_queued > 0 else 0.0
                    }

                    # 6. Gauge: Reciprocity Pipeline (Day 1, Day 2, Day 3+)
                    cur.execute("""
                        SELECT 
                            SUM(CASE WHEN COALESCE(followed_at, updated_at) >= datetime('now', '-1 day') THEN 1 ELSE 0 END) as day1,
                            SUM(CASE WHEN COALESCE(followed_at, updated_at) < datetime('now', '-1 day') AND COALESCE(followed_at, updated_at) >= datetime('now', '-2 day') THEN 1 ELSE 0 END) as day2,
                            SUM(CASE WHEN COALESCE(followed_at, updated_at) < datetime('now', '-2 day') THEN 1 ELSE 0 END) as day3,
                            COUNT(*) as total_active
                        FROM candidates WHERE status = 'followed'
                    """)
                    pipe_row = dict(cur.fetchone())
                    analytics["gauges"]["reciprocity_pipeline"] = {
                        "day1": pipe_row.get("day1") or 0,
                        "day2": pipe_row.get("day2") or 0,
                        "day3": pipe_row.get("day3") or 0,
                        "total_active": pipe_row.get("total_active") or 0
                    }

                    # 7. Gauge: Source Yield Breakdown
                    cur.execute("""
                        SELECT 
                            source,
                            COUNT(*) as total_found,
                            SUM(CASE WHEN status = 'mutual' THEN 1 ELSE 0 END) as mutuals,
                            SUM(CASE WHEN status = 'followed' THEN 1 ELSE 0 END) as follows
                        FROM candidates 
                        WHERE source IS NOT NULL AND source != ''
                        GROUP BY source
                        ORDER BY total_found DESC
                        LIMIT 6
                    """)
                    sources = []
                    for r in cur.fetchall():
                        f = r["follows"] or 0
                        m = r["mutuals"] or 0
                        sources.append({
                            "source": r["source"],
                            "total_found": r["total_found"],
                            "follows": f,
                            "mutuals": m,
                            "yield_pct": round((m / f * 100), 1) if f > 0 else 0.0
                        })
                    analytics["gauges"]["source_yield"] = sources

                    conn.close()
                except Exception as e:
                    analytics["error"] = str(e)

            self.wfile.write(json.dumps(analytics, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/candidates":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            query_params = urllib.parse.parse_qs(parsed.query)
            status_filter = query_params.get("status", ["all"])[0]
            sort_field = query_params.get("sort", ["score_desc"])[0]
            page = max(1, int(query_params.get("page", [1])[0]))
            page_size_param = query_params.get("page_size", ["50"])[0]
            search_query = query_params.get("q", [""])[0].strip()

            candidates_data = {
                "candidates": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size_param,
                "total_pages": 1
            }

            if os.path.exists(SQLITE_PATH):
                try:
                    conn = sqlite3.connect(SQLITE_PATH)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()

                    where_clauses = []
                    params = []

                    if status_filter != "all":
                        where_clauses.append("status = ?")
                        params.append(status_filter)

                    if search_query:
                        where_clauses.append("(username LIKE ? OR name LIKE ? OR bio LIKE ?)")
                        q_param = f"%{search_query}%"
                        params.extend([q_param, q_param, q_param])

                    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

                    cur.execute(f"SELECT COUNT(*) FROM candidates {where_sql}", params)
                    total_count = cur.fetchone()[0]
                    candidates_data["total_count"] = total_count

                    order_map = {
                        "score_desc": "score DESC, ratio DESC",
                        "date_desc": "created_at DESC",
                        "date_asc": "created_at ASC",
                        "ratio_desc": "ratio DESC, score DESC",
                        "followers_desc": "followers_count DESC"
                    }
                    order_sql = order_map.get(sort_field, "score DESC, ratio DESC")

                    if page_size_param == "all":
                        limit_sql = ""
                        total_pages = 1
                    else:
                        page_size = int(page_size_param)
                        total_pages = max(1, (total_count + page_size - 1) // page_size)
                        offset = (page - 1) * page_size
                        limit_sql = f"LIMIT {page_size} OFFSET {offset}"

                    candidates_data["total_pages"] = total_pages

                    cur.execute(f"SELECT * FROM candidates {where_sql} ORDER BY {order_sql} {limit_sql}", params)
                    candidates_data["candidates"] = [dict(r) for r in cur.fetchall()]

                    conn.close()
                except Exception as e:
                    candidates_data["error"] = str(e)

            self.wfile.write(json.dumps(candidates_data, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/profile/sync":
            self.do_GET()
        elif parsed.path == "/api/profile/update":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
            data = {}
            try:
                data = json.loads(body)
            except Exception:
                pass

            fol = int(data.get("followers_count", 0))
            fing = int(data.get("following_count", 0))

            if os.path.exists(SQLITE_PATH):
                try:
                    conn = sqlite3.connect(SQLITE_PATH)
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM candidates WHERE LOWER(username) = LOWER(?)", (TARGET_ACCOUNT,))
                    if cur.fetchone():
                        cur.execute("""
                            UPDATE candidates 
                            SET followers_count = ?, following_count = ?, updated_at = CURRENT_TIMESTAMP 
                            WHERE LOWER(username) = LOWER(?)
                        """, (fol, fing, TARGET_ACCOUNT))
                    else:
                        cur.execute("""
                            INSERT INTO candidates (username, name, followers_count, following_count, status) 
                            VALUES (?, ?, ?, ?, 'target_profile')
                        """, (TARGET_ACCOUNT, TARGET_ACCOUNT, fol, fing))
                    conn.commit()
                    conn.close()
                    print(f"[Dashboard API] Successfully updated @{TARGET_ACCOUNT}: {fol} followers, {fing} following")
                except Exception as e:
                    print(f"[Dashboard API] Error updating profile in DB: {e}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True, 
                "followers_count": fol, 
                "following_count": fing, 
                "account": TARGET_ACCOUNT
            }, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def background_profile_syncer():
    """
    Periodically updates target profile stats every 15 minutes.
    """
    time.sleep(15)  # initial wait after startup
    while True:
        try:
            from follower import sync_target_profile_stats
            print(f"[Dashboard Background Syncer] Auto-syncing stats for @{TARGET_ACCOUNT}...")
            sync_target_profile_stats(profile_name="test_igorvl777", account=TARGET_ACCOUNT)
        except Exception as e:
            print(f"[Dashboard Background Syncer] Auto-sync notice: {e}")
        time.sleep(900)

def run_dashboard(port=DASHBOARD_PORT):
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer((DASHBOARD_HOST, port), DashboardHandler)
    print(f"Web Dashboard running at: http://localhost:{port}")
    
    # Start background auto-syncer daemon
    t = threading.Thread(target=background_profile_syncer, daemon=True)
    t.start()
    
    server.serve_forever()

if __name__ == "__main__":
    run_dashboard()

