"""从 loop-log-*.md 回填 loop-state.json 的 history 数组"""
import json
import os
import re
from pathlib import Path

DOCS = Path(__file__).parent.parent / "docs"
STATE = DOCS / "loop-state.json"

def extract_from_log(filepath):
    content = filepath.read_text()
    
    entry = {"file": filepath.name}
    
    # Loop number
    m = re.search(r'# Loop (\d+)', content)
    if m: entry["loop"] = int(m.group(1))
    
    # Date from filename
    m2 = re.search(r'loop-log-(\d{4}-\d{2}-\d{2})', filepath.name)
    if m2: entry["date"] = m2.group(1)
    
    # L_val
    for pat in [r'L_val[=:]\s*([\d.]+)', r'L_geo_val[=:]\s*([\d.]+)']:
        m3 = re.search(pat, content)
        if m3:
            entry["L_val"] = float(m3.group(1))
            break
    
    # TPR/FPR
    m4 = re.search(r'TPR[=:\s]+([\d.]+)', content)
    if m4: entry["TPR"] = float(m4.group(1).rstrip('%'))
    m5 = re.search(r'FPR[=:\s]+([\d.]+)', content)
    if m5: entry["FPR"] = float(m5.group(1).rstrip('%'))
    
    # Key action
    m6 = re.search(r'### \d+\.\s*(.+)', content)
    if m6: entry["action"] = m6.group(1).strip()[:100]
    
    # Had Gemini critique
    entry["had_critique"] = bool(re.search(r'[Gg]emini|批判|critique', content))
    
    # Had regression
    entry["had_regression"] = bool(re.search(r'回滚|rollback|regression|退化|broken', content, re.I))
    
    # Decision rationale (look for "## 决策" or "## 为什么" or first paragraph after "做了什么")
    m7 = re.search(r'##\s*(决策|为什么|rationale|decision)\s*\n(.+?)(?:\n##|\Z)', content, re.S | re.I)
    if m7:
        entry["rationale"] = m7.group(2).strip()[:200]
    
    return entry

logs = sorted(DOCS.glob("loop-log-*.md"))
history = []
for log in logs:
    entry = extract_from_log(log)
    if "loop" in entry:
        history.append(entry)

history.sort(key=lambda x: x.get("loop", 0))

# Update state
state = json.loads(STATE.read_text())
state["history"] = history

STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
print(f"Backfilled {len(history)} entries into loop-state.json history")

# Print summary
for h in history:
    l = h.get("L_val", "n/a")
    tpr = h.get("TPR", "n/a")
    fpr = h.get("FPR", "n/a")
    act = h.get("action", "?")[:50]
    crit = "🔍" if h.get("had_critique") else "  "
    reg = "⚠️" if h.get("had_regression") else "  "
    print(f"  L{h['loop']:>2} | L={str(l):>8} | TPR={str(tpr):>6} FPR={str(fpr):>6} | {crit}{reg} | {act}")
