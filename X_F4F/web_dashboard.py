# -*- coding: utf-8 -*-
"""
Standalone Lightweight Web Dashboard & Monitoring for X F4F Engine.
Runs with Python standard library (http.server) - no heavy dependencies needed!
Provides real-time stats, multi-page pagination, status filtering, sorting, and search.
"""

import http.server
import socketserver
import json
import sqlite3
import os
import urllib.parse
from config import SQLITE_PATH, DASHBOARD_PORT, DASHBOARD_HOST, TARGET_ACCOUNT

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X F4F Growth Engine | Control & Analytics</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
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
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Space Grotesk', -apple-system, sans-serif;
            padding: 32px 48px;
            line-height: 1.5;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 24px;
            margin-bottom: 28px;
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

        h1 { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
        .subtitle { color: var(--text-dim); font-size: 14px; margin-top: 2px; }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .target-pill {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 8px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
        }
        .target-pill span { color: var(--accent); font-weight: 600; }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }

        .stat-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 20px;
            border-radius: 14px;
            position: relative;
            cursor: pointer;
            user-select: none;
            transition: all 0.2s ease;
        }
        .stat-card:hover { transform: translateY(-2px); border-color: #3b425b; background: var(--surface-hover); }
        .stat-card.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), 0 8px 24px var(--accent-glow); }

        .stat-label {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        .stat-value.accent { color: var(--accent); }
        .stat-value.warning { color: var(--warning); }
        .stat-value.success { color: var(--success); }

        /* Filter & Controls Bar */
        .controls-bar {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 16px 20px;
            border-radius: 14px;
            margin-bottom: 20px;
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
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
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

        .filter-count {
            background: rgba(255, 255, 255, 0.08);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
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
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-family: 'Space Grotesk', sans-serif;
            width: 220px;
            outline: none;
            transition: border-color 0.15s;
        }
        .search-input:focus { border-color: var(--accent); }

        select.control-select {
            background: #161924;
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-family: 'Space Grotesk', sans-serif;
            cursor: pointer;
            outline: none;
        }
        select.control-select:focus { border-color: var(--accent); }

        /* Candidates Table */
        .table-container {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            overflow: hidden;
            margin-bottom: 20px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }

        th {
            background: #161922;
            padding: 14px 20px;
            font-weight: 600;
            color: var(--text-dim);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--surface-border);
            user-select: none;
        }

        td {
            padding: 14px 20px;
            border-bottom: 1px solid var(--surface-border);
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background-color: rgba(255, 255, 255, 0.02); }

        .user-col { display: flex; flex-direction: column; gap: 3px; }
        .user-name { font-weight: 600; color: #fff; font-size: 14px; }
        .user-handle { color: var(--accent); font-family: 'JetBrains Mono', monospace; text-decoration: none; font-size: 13px; }
        .user-handle:hover { text-decoration: underline; }

        .bio-text {
            color: #d1d5db;
            font-size: 13px;
            max-width: 460px;
            line-height: 1.4;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
        }
        .badge.queued { background: var(--accent-glow); color: var(--accent); border: 1px solid var(--accent); }
        .badge.followed { background: rgba(255, 170, 0, 0.15); color: var(--warning); border: 1px solid var(--warning); }
        .badge.mutual { background: var(--success-glow); color: var(--success); border: 1px solid var(--success); }
        .badge.ignored { background: #1a1d28; color: var(--text-dim); border: 1px solid #292e40; }
        .badge.unfollowed { background: rgba(255, 77, 79, 0.15); color: var(--danger); border: 1px solid var(--danger); }

        .score-pill {
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            font-size: 15px;
            color: #00e699;
        }
        .score-pill.low { color: var(--text-dim); }

        .ratio-pill {
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-dim);
            font-size: 12px;
            line-height: 1.4;
        }
        .ratio-pill b { color: #d1d5db; }

        /* Pagination Footer */
        .pagination-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 14px 20px;
            border-radius: 12px;
            font-size: 13px;
            color: var(--text-dim);
        }

        .page-buttons {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-page {
            background: #161924;
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .btn-page:hover:not(:disabled) { background: var(--accent); color: #fff; border-color: var(--accent); }
        .btn-page:disabled { opacity: 0.35; cursor: not-allowed; }

        .page-info {
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
            padding: 0 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo-title">
            <div class="logo-badge">𝕏</div>
            <div>
                <h1>F4F Growth & Outreach Engine</h1>
                <div class="subtitle">Autonomous Targeting • Precision Bio Scoring • Real-time Monitoring</div>
            </div>
        </div>
        <div class="header-actions">
            <div class="target-pill">Active Target: <span id="target-account">—</span></div>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card" onclick="setStatusFilter('all')" id="card-all">
            <div class="stat-label">Кандидатов найдено</div>
            <div class="stat-value" id="stat-total">--</div>
        </div>
        <div class="stat-card" onclick="setStatusFilter('queued')" id="card-queued">
            <div class="stat-label">В очереди скоринга</div>
            <div class="stat-value accent" id="stat-queued">--</div>
        </div>
        <div class="stat-card" onclick="setStatusFilter('followed')" id="card-followed">
            <div class="stat-label">Подписок отправлено</div>
            <div class="stat-value warning" id="stat-followed">--</div>
        </div>
        <div class="stat-card" onclick="setStatusFilter('mutual')" id="card-mutual">
            <div class="stat-label">Взаимных F4F</div>
            <div class="stat-value success" id="stat-mutual">--</div>
        </div>
        <div class="stat-card" onclick="setStatusFilter('ignored')" id="card-ignored">
            <div class="stat-label">Отклонено скорингом</div>
            <div class="stat-value" id="stat-ignored" style="color:#717a8c">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Конверсия F4F</div>
            <div class="stat-value success" id="stat-cr">--%</div>
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
                ⏳ Отправленные подписки <span class="filter-count" id="count-followed">0</span>
            </button>
            <button class="filter-btn" id="filter-queued" onclick="setStatusFilter('queued')">
                📥 В очереди <span class="filter-count" id="count-queued">0</span>
            </button>
            <button class="filter-btn" id="filter-ignored" onclick="setStatusFilter('ignored')">
                🚫 Ignored <span class="filter-count" id="count-ignored">0</span>
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

    <!-- Candidates Table -->
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th style="width: 220px;">Пользователь</th>
                    <th>Bio & Позиционирование</th>
                    <th style="width: 170px;">Метрики</th>
                    <th style="width: 80px;">Score</th>
                    <th style="width: 120px;">Статус</th>
                </tr>
            </thead>
            <tbody id="candidates-body">
                <tr><td colspan="5" style="text-align:center; padding: 32px; color: var(--text-dim);">Загрузка данных...</td></tr>
            </tbody>
        </table>
    </div>

    <!-- Pagination Controls -->
    <div class="pagination-bar">
        <div id="pagination-summary">Показано 0–0 из 0</div>
        <div class="page-buttons">
            <button class="btn-page" id="btn-first" onclick="goToPage(1)">&laquo; Первая</button>
            <button class="btn-page" id="btn-prev" onclick="goToPage(currentPage - 1)">&lsaquo; Назад</button>
            <span class="page-info" id="page-display">1 / 1</span>
            <button class="btn-page" id="btn-next" onclick="goToPage(currentPage + 1)">Вперёд &rsaquo;</button>
            <button class="btn-page" id="btn-last" onclick="goToPage(totalPages)">&raquo; Последняя</button>
        </div>
    </div>

    <script>
        let currentStatus = 'all';
        let currentPage = 1;
        let pageSize = 50; // 50, 200, or 'all'
        let currentSort = 'score_desc';
        let searchQuery = '';
        let totalPages = 1;
        let searchDebounceTimer = null;

        function esc(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        const KNOWN_STATUSES = ['queued','followed','mutual','ignored','discovered','unfollowed'];
        function statusBadge(status) {
            const s = KNOWN_STATUSES.includes(status) ? status : 'ignored';
            const labels = {
                'mutual': '⭐ Взаимный',
                'followed': '⏳ Отправлен',
                'queued': '📥 В очереди',
                'ignored': '🚫 Ignored',
                'unfollowed': 'Отписан'
            };
            return `<span class="badge ${s}">${labels[s] || esc(status)}</span>`;
        }

        function setStatusFilter(status) {
            currentStatus = status;
            currentPage = 1;
            
            // Update filter buttons
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.getElementById('filter-' + status);
            if (activeBtn) activeBtn.classList.add('active');

            // Update stat cards
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

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                document.getElementById('stat-total').innerText = data.total_candidates;
                document.getElementById('stat-queued').innerText = data.queued_count;
                document.getElementById('stat-followed').innerText = data.followed_count;
                document.getElementById('stat-mutual').innerText = data.mutual_count;
                document.getElementById('stat-ignored').innerText = data.ignored_count || 0;
                
                document.getElementById('count-all').innerText = data.total_candidates;
                document.getElementById('count-mutual').innerText = data.mutual_count;
                document.getElementById('count-followed').innerText = data.followed_count;
                document.getElementById('count-queued').innerText = data.queued_count;
                document.getElementById('count-ignored').innerText = data.ignored_count || 0;

                if (data.target_account) {
                    const pill = document.getElementById('target-account');
                    if (pill) pill.innerText = '@' + esc(data.target_account);
                }
                
                const cr = data.followed_count > 0 ? ((data.mutual_count / data.followed_count) * 100).toFixed(1) : '0';
                document.getElementById('stat-cr').innerText = cr + '%';
            } catch (err) {
                console.error('Error fetching stats:', err);
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

                // Update pagination controls
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

                tbody.innerHTML = data.candidates.map(c => `
                    <tr>
                        <td>
                            <div class="user-col">
                                <span class="user-name">${esc(c.name || c.username)}</span>
                                <a class="user-handle" href="https://x.com/${esc(c.username)}" target="_blank" rel="noopener noreferrer">@${esc(c.username)}</a>
                            </div>
                        </td>
                        <td><div class="bio-text">${c.bio ? esc(c.bio) : '<i style="color:#555">Без описания</i>'}</div></td>
                        <td>
                            <div class="ratio-pill">
                                <b>${esc(c.followers_count || 0)}</b> fol / <b>${esc(c.following_count || 0)}</b> fing<br>
                                Ratio: <b>${esc(c.ratio || 0)}</b>
                            </div>
                        </td>
                        <td><div class="score-pill ${c.score < 40 ? 'low' : ''}">${esc(c.score || 0)}</div></td>
                        <td>${statusBadge(c.status)}</td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error('Error fetching candidates:', err);
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 32px; color: var(--danger);">Ошибка загрузки данных.</td></tr>';
            }
        }

        // Initial load
        loadStats();
        loadCandidates();

        // Periodically refresh stats and current view
        setInterval(loadStats, 5000);
        setInterval(loadCandidates, 15000);
    </script>
</body>
</html>
"""

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/index.html":
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
                "target_account": TARGET_ACCOUNT
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
                    
                    conn.close()
                except Exception as e:
                    stats["error"] = str(e)
                    
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))

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

                    # Count total matching
                    cur.execute(f"SELECT COUNT(*) FROM candidates {where_sql}", params)
                    total_count = cur.fetchone()[0]
                    candidates_data["total_count"] = total_count

                    # Sorting logic
                    order_map = {
                        "score_desc": "score DESC, ratio DESC",
                        "date_desc": "created_at DESC",
                        "date_asc": "created_at ASC",
                        "ratio_desc": "ratio DESC, score DESC",
                        "followers_desc": "followers_count DESC"
                    }
                    order_sql = order_map.get(sort_field, "score DESC, ratio DESC")

                    # Pagination logic
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

def run_dashboard(port=DASHBOARD_PORT):
    # Allow address reuse to avoid port bind conflicts on restarts
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer((DASHBOARD_HOST, port), DashboardHandler)
    print(f"Web Dashboard running at: http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_dashboard()
