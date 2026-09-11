# -*- coding: utf-8 -*-
"""
Real-time Chat History Sync Daemon for Antigravity.
Watches active transcript_full.jsonl files and updates chat_history.md immediately when new lines appear.
"""
import sys
import os
import time
import glob
import json
import re
import datetime

def clean_user_message(content):
    if not content:
        return ""
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()

def format_timestamp(iso_str):
    if not iso_str:
        return ""
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(cleaned)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str

def parse_transcript(transcript_path):
    if not os.path.exists(transcript_path):
        return []
    
    entries = []
    current_actions = []
    
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            
            step_type = data.get("type")
            content = data.get("content", "")
            created_at = format_timestamp(data.get("created_at", ""))
            tool_calls = data.get("tool_calls")
            
            # Collect tool actions if present
            if tool_calls:
                for tc in tool_calls:
                    args = tc.get("args") or {}
                    summary = tc.get("toolSummary") or args.get("toolSummary") or args.get("Description") or tc.get("name")
                    if summary and summary not in current_actions:
                        current_actions.append(summary)
            
            if step_type == "USER_INPUT":
                user_text = clean_user_message(content)
                if not user_text:
                    continue
                
                # Filter out repetitive automated 'Continue' prompts
                is_continue = user_text.lower() in ("continue", "continue.", "продолжай", "продолжить")
                if is_continue and entries and entries[-1]["role"] == "user" and entries[-1]["text"].lower() in ("continue", "continue.", "продолжай", "продолжить"):
                    # Skip duplicate continue in a row
                    continue
                
                # If there were accumulated tool actions before this user input, flush them
                if current_actions and (not entries or entries[-1]["role"] == "user"):
                    action_summary = "Выполненные операции: " + ", ".join(current_actions[:8])
                    if len(current_actions) > 8:
                        action_summary += f" и ещё {len(current_actions) - 8}..."
                    entries.append({
                        "role": "agent",
                        "time": created_at,
                        "text": f"🛠️ *[{action_summary}]*"
                    })
                    current_actions = []
                
                entries.append({
                    "role": "user",
                    "time": created_at,
                    "text": user_text
                })
                
            elif step_type == "PLANNER_RESPONSE" and content:
                agent_text = str(content).strip()
                if agent_text and agent_text != "None":
                    current_actions = []  # reset because agent gave full textual response
                    entries.append({
                        "role": "agent",
                        "time": created_at,
                        "text": agent_text
                    })
                    
    return entries

def write_markdown_history(entries, output_path, conversation_id=""):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    lines = []
    lines.append("# 📜 История переписки (Chat History)\n\n")
    if conversation_id:
        lines.append(f"> **Conversation ID**: `{conversation_id}`  \n")
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines.append(f"> **Последнее обновление**: `{now_str}`  \n")
    lines.append(f"> **Всего сообщений**: {len(entries)}\n\n")
    lines.append("---\n\n")
    
    for idx, item in enumerate(entries, 1):
        role_title = "👤 **Оператор (User)**" if item["role"] == "user" else "🤖 **Ассистент (Antigravity)**"
        time_badge = f" *[{item['time']}]*" if item["time"] else ""
        lines.append(f"### {idx}. {role_title}{time_badge}\n\n")
        lines.append(f"{item['text']}\n\n")
        lines.append("---\n\n")
        
    temp_path = output_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    if os.path.exists(output_path):
        os.replace(temp_path, output_path)
    else:
        os.rename(temp_path, output_path)

def find_active_transcripts():
    home_dir = os.path.expanduser("~")
    candidates = [
        os.path.join(home_dir, ".gemini", "antigravity-ide", "brain", "*", ".system_generated", "logs", "transcript_full.jsonl"),
        os.path.join(home_dir, ".gemini", "antigravity", "brain", "*", ".system_generated", "logs", "transcript_full.jsonl"),
        os.path.join(home_dir, ".gemini", "antigravity-cli", "brain", "*", ".system_generated", "logs", "transcript_full.jsonl")
    ]
    found = []
    for c in candidates:
        found.extend(glob.glob(c))
    found.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return found

def get_workspaces_for_conversation(cid):
    workspaces = set()
    home_dir = os.path.expanduser("~")
    log_path = os.path.join(home_dir, ".gemini", "antigravity-ide", "brain", cid, ".system_generated", "logs", "transcript_full.jsonl")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                # Only check header lines where workspace mapping is defined
                for idx, line in enumerate(f):
                    if idx > 30:
                        break
                    # Pattern for Antigravity workspace mapping: [URI] -> [CorpusName]
                    for m in re.findall(r'([a-zA-Z]:\\[^\s\r\n]+)\s*->', line):
                        m_clean = m.strip()
                        if os.path.isdir(m_clean):
                            workspaces.add(m_clean)
        except Exception:
            pass
            
    # Default fallback to current workspace if none found
    default_ws = r"c:\Projects\Business\Web_projects_NEW\X_F4F"
    if os.path.isdir(default_ws):
        workspaces.add(default_ws)
        
    return list(workspaces)

def run_daemon():
    last_processed = {}
    while True:
        try:
            transcripts = find_active_transcripts()
            if transcripts:
                for tpath in transcripts[:3]:
                    try:
                        st = os.stat(tpath)
                        sig = (st.st_mtime, st.st_size)
                        if last_processed.get(tpath) == sig:
                            continue
                        
                        last_processed[tpath] = sig
                        
                        parts = tpath.split(os.sep)
                        cid = ""
                        if "brain" in parts:
                            cid = parts[parts.index("brain") + 1]
                            
                        entries = parse_transcript(tpath)
                        if not entries:
                            continue
                            
                        targets = get_workspaces_for_conversation(cid)
                        cwd = os.getcwd()
                        if cwd and cwd not in targets:
                            targets.append(cwd)
                            
                        for ws in targets:
                            if os.path.isdir(ws):
                                out_file = os.path.join(ws, "chat_history.md")
                                write_markdown_history(entries, out_file, cid)
                    except Exception:
                        pass
        except Exception:
            pass
        
        time.sleep(1)

if __name__ == "__main__":
    run_daemon()
