# -*- coding: utf-8 -*-
"""
Database Queue Purge: Removes unrelated noise from 'queued' candidates.
Keeps only verified designers and business/founders.
"""

import sqlite3
import json
import datetime
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scorer import evaluate_candidate

db_path = os.path.join(BASE_DIR, "data", "x_growth.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
    SELECT username, bio, url, followers_count, following_count, last_active, score_breakdown, is_verified 
    FROM candidates 
    WHERE status = 'queued'
""")
rows = c.fetchall()

kept = 0
dropped = 0
dropped_reasons = {}

for r in rows:
    username = r[0]
    last_act = r[5]
    days_inact = 0
    if last_act:
        try:
            dt = datetime.datetime.strptime(str(last_act)[:19], '%Y-%m-%d %H:%M:%S')
            days_inact = (datetime.datetime.now() - dt).days
        except Exception:
            days_inact = 0

    profile_data = {
        'username': username,
        'bio': r[1] or '',
        'url': r[2] or '',
        'followers_count': r[3],
        'following_count': r[4],
        'days_inactive': days_inact,
        'is_verified': bool(r[7])
    }
    
    eval_res = evaluate_candidate(profile_data)
    new_status = eval_res['status']
    new_score = eval_res['score']
    breakdown_json = json.dumps(eval_res['breakdown'])
    
    if new_status == 'queued':
        kept += 1
        c.execute("""
            UPDATE candidates 
            SET score = ?, score_breakdown = ?, updated_at = CURRENT_TIMESTAMP
            WHERE username = ?
        """, (new_score, breakdown_json, username))
    else:
        dropped += 1
        reason = eval_res['breakdown']['reject_reasons'][0] if eval_res['breakdown']['reject_reasons'] else 'unqualified'
        dropped_reasons[reason] = dropped_reasons.get(reason, 0) + 1
        c.execute("""
            UPDATE candidates 
            SET status = 'ignored', score = ?, score_breakdown = ?, updated_at = CURRENT_TIMESTAMP
            WHERE username = ?
        """, (new_score, breakdown_json, username))

conn.commit()
conn.close()

print(f"[Purge] Finished queue purge!")
print(f"  Total processed: {len(rows)}")
print(f"  Kept in queue (Designers & Founders): {kept}")
print(f"  Dropped to ignored: {dropped}")
print("  Drop reasons:")
for r, cnt in dropped_reasons.items():
    print(f"    - {r}: {cnt}")
