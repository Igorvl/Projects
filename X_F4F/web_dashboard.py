# -*- coding: utf-8 -*-
"""
Standalone Lightweight Web Dashboard & Monitoring for X F4F Engine.
Runs with Python standard library (http.server) - no heavy dependencies needed!
Provides real-time stats, candidates table, conversion metrics, and controls.
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
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0b0c10;
            --surface: #12141c;
            --surface-border: #232738;
            --text-main: #f0f3f8;
            --text-dim: #8b949e;
            --accent: #4f8cff;
            --accent-glow: rgba(79, 140, 255, 0.15);
            --success: #00d26a;
            --success-glow: rgba(0, 210, 106, 0.15);
            --warning: #ffaa00;
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
            margin-bottom: 32px;
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
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 36px;
        }

        .stat-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            padding: 24px;
            border-radius: 16px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .stat-card:hover { transform: translateY(-2px); border-color: #353b52; }

        .stat-label {
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
            margin-bottom: 12px;
        }

        .stat-value {
            font-size: 36px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        .stat-value.accent { color: var(--accent); }
        .stat-value.success { color: var(--success); }

        /* Candidates Table */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .section-title { font-size: 18px; font-weight: 700; }

        .table-container {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 16px;
            overflow: hidden;
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
        }

        td {
            padding: 16px 20px;
            border-bottom: 1px solid var(--surface-border);
            vertical-align: top;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background-color: rgba(255, 255, 255, 0.02); }

        .user-col { display: flex; flex-direction: column; gap: 4px; }
        .user-name { font-weight: 600; color: #fff; }
        .user-handle { color: var(--accent); font-family: 'JetBrains Mono', monospace; text-decoration: none; font-size: 13px; }
        .user-handle:hover { text-decoration: underline; }

        .bio-text {
            color: #d1d5db;
            font-size: 13px;
            max-width: 480px;
            line-height: 1.4;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }
        .badge.queued { background: var(--accent-glow); color: var(--accent); border: 1px solid var(--accent); }
        .badge.followed { background: rgba(255, 170, 0, 0.15); color: var(--warning); border: 1px solid var(--warning); }
        .badge.mutual { background: var(--success-glow); color: var(--success); border: 1px solid var(--success); }
        .badge.ignored { background: #1f2330; color: var(--text-dim); }

        .score-pill {
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            font-size: 15px;
            color: #00e699;
        }

        .ratio-pill {
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-dim);
            font-size: 13px;
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
        <div class="target-pill">Active Target: <span id="target-account">—</span></div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Кандидатов найдено</div>
            <div class="stat-value" id="stat-total">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">В очереди скоринга</div>
            <div class="stat-value accent" id="stat-queued">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Подписок отправлено</div>
            <div class="stat-value" id="stat-followed">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Взаимных F4F</div>
            <div class="stat-value success" id="stat-mutual">--</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Конверсия F4F</div>
            <div class="stat-value success" id="stat-cr">--%</div>
        </div>
    </div>

    <div class="section-header">
        <div class="section-title">База целевых кандидатов (Top Scored Leads)</div>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Пользователь</th>
                    <th>Bio & Позиционирование</th>
                    <th>Метрики</th>
                    <th>Score</th>
                    <th>Статус</th>
                </tr>
            </thead>
            <tbody id="candidates-body">
                <tr><td colspan="5" style="text-align:center; color: var(--text-dim);">Загрузка данных...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        // XSS protection — sanitize all user-sourced strings before DOM insertion
        function esc(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        // Safe status badge — whitelist known statuses
        const KNOWN_STATUSES = ['queued','followed','mutual','ignored','discovered','unfollowed'];
        function statusBadge(status) {
            const s = KNOWN_STATUSES.includes(status) ? status : 'ignored';
            return `<span class="badge ${s}">${esc(status)}</span>`;
        }

        async function loadData() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                document.getElementById('stat-total').innerText = data.total_candidates;
                document.getElementById('stat-queued').innerText = data.queued_count;
                document.getElementById('stat-followed').innerText = data.followed_count;
                document.getElementById('stat-mutual').innerText = data.mutual_count;
                
                // Update target account pill dynamically
                if (data.target_account) {
                    const pill = document.getElementById('target-account');
                    if (pill) pill.innerText = '@' + esc(data.target_account);
                }
                
                const cr = data.followed_count > 0 ? Math.round((data.mutual_count / data.followed_count) * 100) : 0;
                document.getElementById('stat-cr').innerText = cr + '%';

                const tbody = document.getElementById('candidates-body');
                if (!data.candidates || data.candidates.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 32px; color: var(--text-dim);">Кандидатов пока нет. Запустите цикл парсинга: python scraper.py</td></tr>';
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
                                <b>${esc(c.followers_count)}</b> fol / <b>${esc(c.following_count)}</b> fing<br>
                                Ratio: <b>${esc(c.ratio)}</b>
                            </div>
                        </td>
                        <td><div class="score-pill">${esc(c.score)}</div></td>
                        <td>${statusBadge(c.status)}</td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error('Error fetching stats:', err);
            }
        }

        loadData();
        setInterval(loadData, 5000);
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
                "target_account": TARGET_ACCOUNT,
                "candidates": []
            }
            
            if os.path.exists(SQLITE_PATH):
                try:
                    conn = sqlite3.connect(SQLITE_PATH)
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    
                    cur.execute("SELECT COUNT(*) FROM candidates")
                    stats["total_candidates"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'queued'")
                    stats["queued_count"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'followed'")
                    stats["followed_count"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT COUNT(*) FROM candidates WHERE status = 'mutual'")
                    stats["mutual_count"] = cur.fetchone()[0]
                    
                    cur.execute("SELECT * FROM candidates ORDER BY score DESC, ratio DESC LIMIT 30")
                    stats["candidates"] = [dict(r) for r in cur.fetchall()]
                    conn.close()
                except Exception as e:
                    stats["error"] = str(e)
                    
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_dashboard(port=DASHBOARD_PORT):
    server = socketserver.TCPServer((DASHBOARD_HOST, port), DashboardHandler)
    print(f"Web Dashboard running at: http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_dashboard()
