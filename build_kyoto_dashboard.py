#!/usr/bin/env python3
"""
向井小 統合ダッシュボード HTML生成スクリプト
- mukai-context-db.jsonl (84件) + mukai-email-data.jsonl (20件) を読み取り
- HTMLにインライン埋め込み（TL-591: ensure_ascii=True）
- 出力: kyoto-dashboard.html
"""
import json, os, sys
from datetime import datetime

BASE = "/Users/rtano/Documents/WorkSpace "
AGENT_DIR = os.path.join(BASE, "文章_作業スペース/05_仕事_Work/教頭エージェント")
OUTPUT = os.path.join(BASE, "kyoto-hub/kyoto-dashboard.html")

# --- Load data ---
def load_jsonl(path):
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

db = load_jsonl(os.path.join(AGENT_DIR, "mukai-context-db.jsonl"))
emails_raw = load_jsonl(os.path.join(AGENT_DIR, "mukai-email-data.jsonl"))

# --- Categorize ---
persons = []
decisions = []
rules = []

for r in db:
    t = r.get("type", "")
    if t == "person":
        # Categorize persons
        role = r.get("role", "")
        org = r.get("org", "")
        if "児童" in role:
            r["cat"] = "student"
        elif org == "PTA" or "PTA" in role:
            r["cat"] = "pta"
        elif org in ("来賓・地域",) or "区長" in role or "スクールガード" in role or "協議会" in role or "民生委員" in role or "芳向会" in role or "コミュニティー" in role or "むむむ" in role or "むかい農園" in role:
            r["cat"] = "guest"
        else:
            r["cat"] = "staff"
        persons.append(r)
    elif t == "decision":
        decisions.append(r)
    elif t == "rule":
        rules.append(r)

# Build email lookup: topic -> email data
email_map = {}
for e in emails_raw:
    topic = e.get("topic", "")
    email_map[topic] = {
        "subject": e.get("subject", ""),
        "sender": e.get("sender", ""),
        "date": e.get("date", ""),
        "body": e.get("body", ""),
        "attachments": e.get("attachments", [])
    }

# Topic name mapping: db.jsonl -> email-data.jsonl (reconcile name differences)
TOPIC_MAP = {
    "特別支援新担研 名簿提出": "特別支援新担研 名簿",
    "いじめ対応情報管理システム年度更新": "いじめシステム年度更新",
    "くろしお教研 部会希望調査": "くろしお教研 部会希望",
    "研修関連システム年度初め利用": "研修システム ログイン確認",
}

# Rename decision topics to match email data
for d in decisions:
    old_topic = d.get("topic", "")
    if old_topic in TOPIC_MAP:
        d["topic"] = TOPIC_MAP[old_topic]

# Prepare RAW data for embedding (simplified for JS)
raw_js = []
for p in persons:
    item = {"type": "person", "name": p.get("name",""), "reading": p.get("reading",""),
            "role": p.get("role",""), "cat": p["cat"]}
    if p.get("from"):
        item["from"] = p["from"]
    if p.get("note"):
        item["note"] = p["note"]
    if p.get("gender"):
        item["gender"] = p["gender"]
    if p.get("contact"):
        item["contact"] = p["contact"]
    raw_js.append(item)

for d in decisions:
    item = {"type": "decision", "topic": d.get("topic",""), "content": d.get("content",""),
            "deadline": d.get("deadline",""), "source": d.get("source","")}
    raw_js.append(item)

for r in rules:
    item = {"type": "rule", "topic": r.get("topic",""), "content": r.get("content",""),
            "source": r.get("source","")}
    raw_js.append(item)

# JSON encode with ensure_ascii=True (TL-591)
raw_json = json.dumps(raw_js, ensure_ascii=True)
email_json = json.dumps(email_map, ensure_ascii=True)

# Stats
cat_counts = {"staff": 0, "student": 0, "guest": 0, "pta": 0}
for p in persons:
    cat_counts[p["cat"]] += 1

print(f"Persons: {len(persons)} (staff={cat_counts['staff']}, student={cat_counts['student']}, guest={cat_counts['guest']}, pta={cat_counts['pta']})")
print(f"Decisions: {len(decisions)}")
print(f"Rules: {len(rules)}")
print(f"Emails: {len(email_map)}")

# --- Generate HTML ---
html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>向井小 教頭ダッシュボード — R8年度</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#FAF9F6;--surface:#fff;--border:rgba(45,38,33,.07);--border-mid:rgba(45,38,33,.12);
  --text:#2d2621;--text-sec:#6b6560;--text-dim:#a8a29e;
  --accent:#4A7C59;--accent-bg:rgba(74,124,89,.07);
  --green:#4A7C59;--blue:#5B7DB1;--amber:#C8934A;--pink:#B85A7A;--red:#C45D5D;--purple:#7c3aed;--teal:#0d9488;
}}
body{{font-family:'Inter','Noto Sans JP',sans-serif;background:var(--bg);color:var(--text);padding:24px 32px;line-height:1.6}}
h1{{font-size:1.4rem;font-weight:700;margin-bottom:4px}}
.subtitle{{color:var(--text-sec);font-size:.85rem;margin-bottom:20px}}
.stats{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
.stat{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 20px;min-width:100px;transition:transform .15s}}
.stat:hover{{transform:translateY(-2px)}}
.stat-num{{font-size:1.6rem;font-weight:700;line-height:1}}
.stat-label{{font-size:.72rem;color:var(--text-sec);margin-top:2px}}

/* Tabs */
.tab-bar{{display:flex;gap:0;margin-bottom:20px;border-bottom:2px solid var(--border);align-items:stretch}}
.tab-btn{{padding:10px 18px;border:none;background:transparent;font-size:.85rem;cursor:pointer;transition:all .2s;font-family:inherit;font-weight:600;color:var(--text-dim);border-bottom:2px solid transparent;margin-bottom:-2px;display:flex;align-items:center;gap:6px}}
.tab-btn:hover{{color:var(--text);background:var(--accent-bg)}}
.tab-btn.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.tab-btn .tab-count{{font-size:.7rem;background:var(--border);color:var(--text-sec);padding:1px 6px;border-radius:8px;font-weight:700}}
.tab-btn.active .tab-count{{background:var(--accent);color:#fff}}
.search{{padding:6px 14px;border:1px solid var(--border-mid);border-radius:20px;font-size:.8rem;width:200px;outline:none;font-family:inherit}}
.search:focus{{border-color:var(--accent)}}

/* Tables */
table{{width:100%;border-collapse:collapse;background:var(--surface);border-radius:12px;overflow:hidden;border:1px solid var(--border)}}
thead th{{background:var(--bg);font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--text-sec);padding:10px 14px;text-align:left;border-bottom:1px solid var(--border-mid)}}
tbody td{{padding:10px 14px;font-size:.85rem;border-bottom:1px solid var(--border);vertical-align:top}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover{{background:rgba(74,124,89,.02)}}
.name{{font-weight:600}}
.reading{{color:var(--text-dim);font-size:.75rem}}
.note{{color:var(--text-sec);font-size:.75rem;max-width:320px}}
.tag{{display:inline-block;font-size:.65rem;padding:1px 6px;border-radius:8px;font-weight:500}}
.tag-instant{{background:#e8f5e9;color:#2e7d32}}
.tag-deadline{{background:#fff3e0;color:#e65100}}
.tag-slow{{background:#f3e5f5;color:#7b1fa2}}
.tag-male{{background:#e3f2fd;color:#1565c0}}
.tag-female{{background:#fce4ec;color:#c62828}}

/* Briefing */
.briefing-section{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:20px 24px;margin-bottom:16px}}
.briefing-section h3{{font-size:.9rem;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.briefing-item{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);align-items:flex-start}}
.briefing-item:last-child{{border-bottom:none}}
.briefing-date{{font-size:.75rem;font-weight:700;min-width:50px;color:var(--accent)}}
.briefing-topic{{font-size:.85rem;font-weight:600}}
.briefing-content{{font-size:.75rem;color:var(--text-sec);margin-top:2px;line-height:1.4}}
.briefing-badge{{font-size:.6rem;padding:2px 8px;border-radius:6px;font-weight:700;display:inline-block;margin-left:8px}}
.overdue-badge{{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}}
.today-badge{{background:#fff7ed;color:#ea580c;border:1px solid #fed7aa}}
.week-badge{{background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe}}

/* Modal */
.modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000;align-items:center;justify-content:center;backdrop-filter:blur(4px)}}
.modal-overlay.open{{display:flex}}
.modal{{background:#fff;border-radius:16px;max-width:700px;width:90%;max-height:85vh;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.2);display:flex;flex-direction:column}}
.modal-header{{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:flex-start;gap:12px}}
.modal-header h2{{font-size:1rem;font-weight:700;line-height:1.3}}
.modal-close{{background:none;border:none;font-size:1.2rem;cursor:pointer;color:var(--text-dim);padding:4px 8px;border-radius:6px}}
.modal-close:hover{{background:var(--border)}}
.modal-meta{{padding:8px 20px;background:var(--bg);font-size:.75rem;color:var(--text-sec);display:flex;gap:16px;border-bottom:1px solid var(--border)}}
.modal-body{{padding:20px;overflow-y:auto;flex:1;font-size:.85rem;line-height:1.7;white-space:pre-wrap;font-family:'Noto Sans JP',sans-serif}}
.modal-atts{{padding:12px 20px;border-top:1px solid var(--border);background:var(--bg)}}
.modal-atts-title{{font-size:.7rem;font-weight:600;color:var(--text-sec);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em}}
.modal-att{{font-size:.8rem;padding:4px 0;display:flex;align-items:center;gap:6px}}
.modal-att::before{{content:'\\1F4CE';font-size:.7rem}}

.updated{{color:var(--text-dim);font-size:.7rem;margin-top:24px;text-align:right}}

@media print{{body{{padding:12px}}.tab-bar,.search,.stats{{display:none}}table{{font-size:.75rem}}}}
</style>
</head>
<body>
<h1>向井小 教頭ダッシュボード</h1>
<p class="subtitle">R8年度 統合コンテキストDB ({len(persons)}人 + {len(decisions)}件タスク + {len(rules)}件ルール + {len(email_map)}件メール)</p>
<div class="stats" id="stats"></div>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
  <div class="tab-bar" id="tabBar"></div>
  <input class="search" id="search" type="text" placeholder="検索..." autocomplete="off">
</div>

<div id="content"></div>

<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-header"><h2 id="modalTitle"></h2><button class="modal-close" onclick="closeModal()">&#10005;</button></div>
    <div class="modal-meta"><span id="modalSender"></span><span id="modalDate"></span></div>
    <div class="modal-body" id="modalBody"></div>
    <div class="modal-atts" id="modalAtts" style="display:none"><div class="modal-atts-title">添付ファイル</div><div id="modalAttList"></div></div>
  </div>
</div>

<p class="updated" id="updated"></p>

<script id="rawData" type="application/json">{raw_json}</script>
<script id="emailData" type="application/json">{email_json}</script>

<script>
// === Data ===
const RAW = JSON.parse(document.getElementById('rawData').textContent);
var EMAIL_DATA = {{}};
try{{ EMAIL_DATA = JSON.parse(document.getElementById('emailData').textContent); }} catch(e) {{}}

const TODAY = new Date(); TODAY.setHours(0,0,0,0);
const START_DATE = new Date('2026-04-01'); START_DATE.setHours(0,0,0,0);
const DAY_N = Math.round((TODAY - START_DATE) / 86400000) + 1;
const CURRENT_MONTH = (TODAY.getMonth() + 1);

function diffDays(dl){{ const d = new Date(dl); d.setHours(0,0,0,0); return Math.round((d - TODAY) / 86400000); }}
function fmtDate(dl){{ const d = new Date(dl); return (d.getMonth()+1) + '/' + d.getDate(); }}

// === Completion ===
const DONE_KEY = 'mukai-db-done';
function getDone(){{ try {{ return JSON.parse(localStorage.getItem(DONE_KEY) || '[]'); }} catch(e) {{ return []; }} }}
function setDone(arr){{ localStorage.setItem(DONE_KEY, JSON.stringify(arr)); }}
function toggleDone(topic, ev){{
  ev.stopPropagation();
  const d = getDone();
  const i = d.indexOf(topic);
  if(i >= 0) d.splice(i, 1); else d.push(topic);
  setDone(d);
  render(currentTab, currentQuery);
}}
let showDone = true;

// === Categorize ===
const persons = RAW.filter(r => r.type === 'person');
const decisions = RAW.filter(r => r.type === 'decision');
const rules = RAW.filter(r => r.type === 'rule');
const cats = {{ staff: 0, student: 0, guest: 0, pta: 0 }};
persons.forEach(p => cats[p.cat]++);

// === Gyouji ===
const gyouji = [
  {{month:'4月',num:4,items:[{{event:'入学式',who:'全員'}},{{event:'家庭訪問(案内・調整)',who:'教頭・各担任'}},{{event:'春の遠足',who:'脇'}}]}},
  {{month:'5月',num:5,items:[{{event:'体力テスト',who:'内山'}},{{event:'第1回Q-U',who:'脇'}},{{event:'第1回避難訓練',who:'教頭'}}]}},
  {{month:'6月',num:6,items:[{{event:'心肺蘇生法',who:'教頭'}},{{event:'プール清掃・管理',who:'東'}},{{event:'水泳指導計画',who:'内山'}},{{event:'おさすり作り',who:'教頭'}}]}},
  {{month:'7月',num:7,items:[{{event:'防犯教室',who:'教頭'}},{{event:'交通安全教室',who:'教頭'}},{{event:'個別懇談会',who:'教頭'}}]}},
  {{month:'8月',num:8,items:[{{event:'平和学習会',who:'各担任'}}]}},
  {{month:'9月',num:9,items:[{{event:'薬物乱用教室',who:'教頭'}}]}},
  {{month:'10月',num:10,items:[{{event:'運動会',who:'内山'}},{{event:'第2回Q-U',who:'脇'}},{{event:'第2回避難訓練',who:'教頭'}}]}},
  {{month:'11月',num:11,items:[{{event:'修学旅行(社会見学)',who:'脇'}},{{event:'秋の遠足',who:'上ノ坊'}},{{event:'聖光園慰問',who:'上ノ坊'}},{{event:'校内ジョギング',who:'脇'}}]}},
  {{month:'12月',num:12,items:[{{event:'しめ縄作り',who:'教頭'}},{{event:'焼きいも大会',who:'内山'}},{{event:'個別懇談会',who:'教頭'}},{{event:'餅つき大会(学習参観)',who:'教頭'}}]}},
  {{month:'1月',num:1,items:[{{event:'防火学習',who:'教頭'}},{{event:'なわとび大会',who:'内山'}}]}},
  {{month:'2月',num:2,items:[{{event:'6年生を送る会',who:'上ノ坊'}},{{event:'第3回避難訓練',who:'教頭'}}]}},
  {{month:'3月',num:3,items:[{{event:'卒業式',who:'教頭'}}]}},
  {{month:'通年',num:0,items:[{{event:'畑管理',who:'内山'}},{{event:'花壇管理',who:'内山'}},{{event:'PTA',who:'教頭'}},{{event:'防災関係',who:'教頭'}}]}}
];
const whoColors = {{'教頭':'#4A7C59','内山':'#5B7DB1','脇':'#C8934A','上ノ坊':'#B85A7A','東':'#0d9488','各担任':'#7c3aed','全員':'#64748b','教頭・各担任':'#4A7C59'}};
const rulesOnly = rules.filter(r => !r.topic.startsWith('行事担当'));

// === Stats ===
const done = getDone();
const totalTasks = decisions.length;
const doneCount = decisions.filter(d => done.includes(d.topic)).length;
document.getElementById('stats').innerHTML = `
  <div class="stat"><div class="stat-num" style="color:var(--accent)">${{DAY_N}}</div><div class="stat-label">赴任${{DAY_N}}日目</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--red)">${{totalTasks - doneCount}}</div><div class="stat-label">未完了タスク</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--accent)">${{doneCount}}</div><div class="stat-label">完了</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--green)">${{cats.staff}}</div><div class="stat-label">教職員</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--blue)">${{cats.student}}</div><div class="stat-label">児童</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--amber)">${{cats.guest}}</div><div class="stat-label">来賓・地域</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--pink)">${{cats.pta}}</div><div class="stat-label">PTA</div></div>
`;

// === Tabs ===
const tabDefs = [
  {{id:'briefing',label:'ブリーフィング',count:''}},
  {{id:'deadline',label:'締切・タスク',count:decisions.length - doneCount}},
  {{id:'gyouji',label:'行事担当',count:gyouji.reduce((s,g) => s + g.items.length, 0)}},
  {{id:'person',label:'人物',count:persons.length}},
  {{id:'rule',label:'ルール',count:rulesOnly.length}}
];

let currentTab = 'briefing';
let currentQuery = '';

function buildTabs(){{
  const bar = document.getElementById('tabBar');
  bar.innerHTML = '';
  tabDefs.forEach(t => {{
    const btn = document.createElement('button');
    btn.className = 'tab-btn' + (currentTab === t.id ? ' active' : '');
    btn.dataset.tab = t.id;
    btn.innerHTML = t.label + (t.count !== '' ? ` <span class="tab-count">${{t.count}}</span>` : '');
    btn.onclick = () => {{ currentTab = t.id; currentQuery = ''; document.getElementById('search').value = ''; buildTabs(); render(currentTab, currentQuery); }};
    bar.appendChild(btn);
  }});
}}

// === Render ===
function render(tab, query){{
  const el = document.getElementById('content');
  let html = '';
  const q = (query || '').toLowerCase();

  // --- Tab 1: Briefing ---
  if(tab === 'briefing'){{
    const todayStr = TODAY.toLocaleDateString('ja-JP', {{year:'numeric',month:'long',day:'numeric',weekday:'short'}});
    html += `<div style="font-size:1.1rem;font-weight:700;margin-bottom:16px">${{todayStr}} &mdash; 赴任${{DAY_N}}日目</div>`;

    // Overdue
    const overdue = decisions.filter(d => diffDays(d.deadline) < 0 && !getDone().includes(d.topic))
      .sort((a,b) => a.deadline.localeCompare(b.deadline));
    if(overdue.length){{
      html += `<div class="briefing-section" style="border-left:3px solid var(--red)"><h3 style="color:var(--red)">超過タスク <span class="briefing-badge overdue-badge">${{overdue.length}}件</span></h3>`;
      overdue.forEach(d => {{
        const dd = -diffDays(d.deadline);
        html += `<div class="briefing-item"><div class="briefing-date" style="color:var(--red)">${{fmtDate(d.deadline)}}</div><div><div class="briefing-topic">${{d.topic}} <span class="briefing-badge overdue-badge">${{dd}}日超過</span></div><div class="briefing-content">${{d.content}}</div></div></div>`;
      }});
      html += `</div>`;
    }}

    // Today
    const todayTasks = decisions.filter(d => diffDays(d.deadline) === 0 && !getDone().includes(d.topic));
    if(todayTasks.length){{
      html += `<div class="briefing-section" style="border-left:3px solid var(--amber)"><h3 style="color:var(--amber)">今日の締切 <span class="briefing-badge today-badge">${{todayTasks.length}}件</span></h3>`;
      todayTasks.forEach(d => {{
        html += `<div class="briefing-item"><div class="briefing-date" style="color:var(--amber)">TODAY</div><div><div class="briefing-topic">${{d.topic}}</div><div class="briefing-content">${{d.content}}</div></div></div>`;
      }});
      html += `</div>`;
    }}

    // This week (1-7 days)
    const weekTasks = decisions.filter(d => {{
      const dd = diffDays(d.deadline);
      return dd >= 1 && dd <= 7 && !getDone().includes(d.topic);
    }}).sort((a,b) => a.deadline.localeCompare(b.deadline));
    if(weekTasks.length){{
      html += `<div class="briefing-section" style="border-left:3px solid var(--purple)"><h3 style="color:var(--purple)">今週の締切 <span class="briefing-badge week-badge">${{weekTasks.length}}件</span></h3>`;
      weekTasks.forEach(d => {{
        const dd = diffDays(d.deadline);
        html += `<div class="briefing-item"><div class="briefing-date">${{fmtDate(d.deadline)}}</div><div><div class="briefing-topic">${{d.topic}} <span style="font-size:.7rem;color:var(--text-dim)">${{dd}}日後</span></div><div class="briefing-content">${{d.content}}</div></div></div>`;
      }});
      html += `</div>`;
    }}

    // Summary stats
    const allDone = getDone();
    const undone = decisions.filter(d => !allDone.includes(d.topic)).length;
    const doneN = decisions.filter(d => allDone.includes(d.topic)).length;
    html += `<div class="briefing-section"><h3>統計サマリー</h3>`;
    html += `<div style="display:flex;gap:20px">`;
    html += `<div><span style="font-size:2rem;font-weight:800;color:var(--red)">${{undone}}</span><span style="font-size:.8rem;color:var(--text-sec);margin-left:4px">未完了</span></div>`;
    html += `<div><span style="font-size:2rem;font-weight:800;color:var(--accent)">${{doneN}}</span><span style="font-size:.8rem;color:var(--text-sec);margin-left:4px">完了</span></div>`;
    html += `<div><span style="font-size:2rem;font-weight:800;color:var(--text)">${{decisions.length}}</span><span style="font-size:.8rem;color:var(--text-sec);margin-left:4px">全件</span></div>`;
    html += `</div></div>`;

    // No overdue, no today, no week = all clear
    if(!overdue.length && !todayTasks.length && !weekTasks.length){{
      html += `<div class="briefing-section" style="text-align:center;padding:40px"><div style="font-size:2rem;margin-bottom:8px">&#10003;</div><div style="font-size:1rem;font-weight:600;color:var(--accent)">今週の直近タスクなし</div></div>`;
    }}
  }}

  // --- Tab 2: Deadline/Tasks (Pokemon Card style) ---
  if(tab === 'deadline'){{
    const done = getDone();
    const allDls = decisions.filter(d => {{
      if(q && !(d.topic + d.content).toLowerCase().includes(q)) return false;
      return true;
    }}).sort((a,b) => a.deadline.localeCompare(b.deadline));
    const doneCount = allDls.filter(d => done.includes(d.topic)).length;
    const dls = showDone ? allDls : allDls.filter(d => !done.includes(d.topic));

    // Toggle bar
    html += `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">`;
    html += `<div style="font-size:.8rem;color:var(--text-sec)">残り <b style="color:var(--text)">${{allDls.length - doneCount}}</b> 件 / 完了 <b style="color:var(--accent)">${{doneCount}}</b> 件</div>`;
    html += `<button onclick="showDone=!showDone;render(currentTab,currentQuery)" style="padding:6px 14px;border:1px solid var(--border-mid);border-radius:8px;background:${{showDone?'var(--surface)':'var(--accent-bg)'}};font-size:.75rem;cursor:pointer;font-family:inherit;color:${{showDone?'var(--text-sec)':'var(--accent)'}};font-weight:600">${{showDone?'完了済みを隠す':'完了済みも表示'}}</button>`;
    html += `</div>`;

    // Rarity
    function rarity(dd){{
      if(dd < 0) return {{r:'OVERDUE',color:'#dc2626',bg:'#fff',glow:'0 0 0 2px #dc2626',border:'#dc2626',star:'\u2605\u2605\u2605\u2605\u2605',accent:'#fef2f2'}};
      if(dd <= 1) return {{r:'UR',color:'#ea580c',bg:'#fff',glow:'0 0 0 2px #ea580c',border:'#ea580c',star:'\u2605\u2605\u2605\u2605',accent:'#fff7ed'}};
      if(dd <= 3) return {{r:'SSR',color:'#d97706',bg:'#fff',glow:'0 0 0 2px #d97706',border:'#d97706',star:'\u2605\u2605\u2605',accent:'#fffbeb'}};
      if(dd <= 7) return {{r:'SR',color:'#7c3aed',bg:'#fff',glow:'0 4px 16px rgba(0,0,0,.08)',border:'#7c3aed',star:'\u2605\u2605',accent:'#f5f3ff'}};
      if(dd <= 14) return {{r:'R',color:'#2563eb',bg:'#fff',glow:'0 2px 8px rgba(0,0,0,.04)',border:'#e2e8f0',star:'\u2605',accent:'#eff6ff'}};
      return {{r:'N',color:'#6b7280',bg:'#fff',glow:'0 2px 8px rgba(0,0,0,.04)',border:'#e2e8f0',star:'',accent:'#f9fafb'}};
    }}

    function cardType(topic){{
      if(/提出|名簿|報告|調査|シート/.test(topic)) return {{type:'提出',icon:'\U0001F4C4',tc:'#ef4444'}};
      if(/会議|教頭会|総会|協議/.test(topic)) return {{type:'会議',icon:'\U0001F3DB',tc:'#8b5cf6'}};
      if(/学力|学調|みえスタ/.test(topic)) return {{type:'学調',icon:'\U0001F4CA',tc:'#f59e0b'}};
      if(/PTA|互助|スポ振/.test(topic)) return {{type:'PTA',icon:'\U0001F91D',tc:'#ec4899'}};
      if(/入学|始業|卒業/.test(topic)) return {{type:'式典',icon:'\U0001F393',tc:'#14b8a6'}};
      if(/研修|システム|ライセンス/.test(topic)) return {{type:'ICT',icon:'\U0001F4BB',tc:'#3b82f6'}};
      return {{type:'業務',icon:'\U0001F4CB',tc:'#6b7280'}};
    }}

    html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px">`;
    dls.forEach(d => {{
      const dd = diffDays(d.deadline);
      const isDone = done.includes(d.topic);
      const ra = isDone ? {{r:'DONE',color:'#9ca3af',bg:'#f9fafb',glow:'none',border:'#d1d5db',star:'',accent:'#f3f4f6'}} : rarity(dd);
      const ct = cardType(d.topic);
      const dlabel = isDone ? '完了' : dd < 0 ? `${{-dd}}日超過` : dd === 0 ? 'TODAY' : dd === 1 ? '明日' : `${{dd}}日`;
      const mon = parseInt(d.deadline.slice(5,7));
      const day = parseInt(d.deadline.slice(8,10));
      const hasEmail = !!EMAIL_DATA[d.topic];
      const topicSafe = d.topic.replace(/'/g,"&#39;");

      html += `<div style="background:${{ra.bg}};border:2px solid ${{ra.border}};border-radius:16px;padding:0;color:var(--text);position:relative;overflow:hidden;box-shadow:${{ra.glow}};transition:transform .2s;cursor:${{hasEmail?'pointer':'default'}};${{isDone?'opacity:.55;':''}}" onmouseover="this.style.transform='scale(1.03)'" onmouseout="this.style.transform=''" ${{hasEmail?'onclick="openMailModal(this.dataset.topic)"':''}} data-topic="${{d.topic}}">`;
      // Preview area with icon
      html += `<div style="width:100%;aspect-ratio:16/9;background:${{ra.accent}};display:flex;align-items:center;justify-content:center;border-bottom:1px solid ${{ra.border}}30;position:relative">`;
      html += `<span style="font-size:2.5rem">${{ct.icon}}</span>`;
      html += `<span style="position:absolute;top:8px;right:8px;font-size:.6rem;font-weight:800;color:#fff;background:${{ra.color}};padding:2px 8px;border-radius:6px;letter-spacing:.05em">${{ra.r}}</span>`;
      html += `<span style="position:absolute;top:8px;left:8px;font-size:.6rem;font-weight:700;padding:2px 8px;border-radius:6px;background:#fff;color:${{ct.tc}};border:1px solid ${{ct.tc}}40">${{ct.type}}</span>`;
      html += `</div>`;
      // Card body
      html += `<div style="padding:12px 14px">`;
      html += `<div style="font-size:.95rem;font-weight:800;margin-bottom:4px;line-height:1.3;${{isDone?'text-decoration:line-through;color:var(--text-dim)':''}}">${{d.topic}}</div>`;
      html += `<div style="font-size:.72rem;color:var(--text-sec);margin-bottom:10px;line-height:1.4;min-height:32px">${{d.content.length > 70 ? d.content.slice(0,70) + '\\u2026' : d.content}}</div>`;
      // Footer
      html += `<div style="display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid var(--border);padding-top:8px">`;
      html += `<div><div style="font-size:.55rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:.1em">Deadline</div><div style="font-size:1.1rem;font-weight:800;color:${{ra.color}};line-height:1">${{mon}}/${{day}}</div></div>`;
      html += `<div style="text-align:right"><div style="font-size:1.3rem;font-weight:900;color:${{ra.color}};line-height:1">${{dlabel}}</div><div style="font-size:.55rem;color:var(--text-dim);letter-spacing:.05em">${{ra.star}}</div></div>`;
      html += `</div></div>`;
      // Source + Done button + Email link
      html += `<div style="font-size:.55rem;color:var(--text-dim);padding:0 14px 8px;display:flex;justify-content:space-between;align-items:center">`;
      if(hasEmail) html += `<span style="color:var(--accent);font-weight:600">\U0001F4E7 \u30e1\u30fc\u30eb\u8a73\u7d30 \u2192</span>`;
      else html += `<span></span>`;
      html += `<div style="display:flex;align-items:center;gap:8px">`;
      html += `<span>${{d.source || ''}}</span>`;
      const escapedTopic = d.topic.replace(/'/g, "\\\\'");
      html += `<button onclick="toggleDone('${{escapedTopic}}',event)" style="font-size:.65rem;padding:2px 8px;border-radius:6px;border:1px solid ${{isDone?'var(--accent)':'var(--border-mid)'}};background:${{isDone?'var(--accent)':'var(--surface)'}};color:${{isDone?'#fff':'var(--text-sec)'}};cursor:pointer;font-weight:600;white-space:nowrap">${{isDone?'\\u2713 完了':'完了'}}</button>`;
      html += `</div></div></div>`;
    }});
    html += `</div>`;
  }}

  // --- Tab 3: Gyouji ---
  if(tab === 'gyouji'){{
    // Who counts
    const whoCounts = {{}};
    gyouji.forEach(g => g.items.forEach(it => {{ whoCounts[it.who] = (whoCounts[it.who] || 0) + 1; }}));
    html += `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">`;
    Object.entries(whoCounts).sort((a,b) => b[1] - a[1]).forEach(([w,n]) => {{
      const c = whoColors[w] || 'var(--text)';
      html += `<div style="background:var(--surface);border:1px solid var(--border);border-left:3px solid ${{c}};border-radius:8px;padding:8px 14px"><span style="font-weight:700;color:${{c}}">${{w}}</span><span style="margin-left:8px;font-size:1.2rem;font-weight:700">${{n}}</span><span style="font-size:.7rem;color:var(--text-dim)">件</span></div>`;
    }});
    html += `</div>`;

    // Monthly cards
    html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px">`;
    gyouji.forEach(g => {{
      const filtered = g.items.filter(it => {{ if(!q) return true; return (it.event + it.who).toLowerCase().includes(q); }});
      if(!filtered.length) return;
      const isNow = (g.num === CURRENT_MONTH);
      html += `<div style="background:var(--surface);border:1px solid ${{isNow ? 'var(--accent)' : 'var(--border)'}};border-radius:14px;padding:16px;${{isNow ? 'box-shadow:0 0 0 2px rgba(74,124,89,.15)' : ''}}">`;
      html += `<div style="font-size:1.1rem;font-weight:700;margin-bottom:10px;${{isNow ? 'color:var(--accent)' : ''}}">${{g.month}}${{isNow ? ' \\u2190今月' : ''}}</div>`;
      filtered.forEach(it => {{
        const c = whoColors[it.who] || 'var(--text)';
        html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid var(--border)">`;
        html += `<span style="font-size:.85rem">${{it.event}}</span>`;
        html += `<span style="font-size:.72rem;font-weight:600;padding:1px 8px;border-radius:6px;background:${{c}}18;color:${{c}};white-space:nowrap;margin-left:6px">${{it.who}}</span>`;
        html += `</div>`;
      }});
      html += `</div>`;
    }});
    html += `</div>`;
  }}

  // --- Tab 4: Person ---
  if(tab === 'person'){{
    const personSecs = [
      {{key:'staff',title:'教職員',color:'var(--green)'}},
      {{key:'student',title:'児童',color:'var(--blue)'}},
      {{key:'guest',title:'来賓・地域',color:'var(--amber)'}},
      {{key:'pta',title:'PTA役員',color:'var(--pink)'}}
    ];
    // Sub-tabs
    if(!window._personSub) window._personSub = 'staff';
    html += `<div style="display:flex;gap:8px;margin-bottom:16px">`;
    personSecs.forEach(sec => {{
      const cnt = persons.filter(p => p.cat === sec.key).length;
      const active = window._personSub === sec.key;
      html += `<button onclick="window._personSub='${{sec.key}}';render('person',document.getElementById('search').value)" style="padding:6px 14px;border:1px solid ${{active ? sec.color : 'var(--border-mid)'}};border-radius:8px;background:${{active ? sec.color + '15' : 'var(--surface)'}};font-size:.8rem;cursor:pointer;font-family:inherit;color:${{active ? sec.color : 'var(--text-sec)'}};font-weight:600">${{sec.title}} (${{cnt}})</button>`;
    }});
    html += `</div>`;

    // Current section
    const sec = personSecs.find(s => s.key === window._personSub);
    const items = persons.filter(p => p.cat === sec.key).filter(p => {{
      if(!q) return true;
      return (p.name + (p.reading||'') + p.role + (p.note||'')).toLowerCase().includes(q);
    }});
    if(items.length){{
      html += `<div><div style="font-size:1rem;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:8px;color:${{sec.color}}">${{sec.title}} <span style="font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:500;background:${{sec.color}}15;color:${{sec.color}}">${{items.length}}</span></div>`;
      html += `<table><thead><tr><th>#</th><th>氏名</th><th>役職</th>`;
      if(sec.key === 'student') html += `<th>性別</th>`;
      if(sec.key === 'staff') html += `<th>異動元</th>`;
      html += `<th>備考</th></tr></thead><tbody>`;
      items.forEach((d, i) => {{
        html += `<tr><td>${{i+1}}</td><td><span class="name">${{d.name}}</span><br><span class="reading">${{d.reading || ''}}</span></td><td>${{d.role}}</td>`;
        if(sec.key === 'student'){{
          const gc = d.gender === '男' ? 'tag-male' : 'tag-female';
          html += `<td><span class="tag ${{gc}}">${{d.gender}}</span></td>`;
        }}
        if(sec.key === 'staff') html += `<td class="note">${{d.from || ''}}</td>`;
        html += `<td class="note">${{d.note || ''}}</td></tr>`;
      }});
      html += `</tbody></table></div>`;
    }}
  }}

  // --- Tab 5: Rules ---
  if(tab === 'rule'){{
    const rs = rulesOnly.filter(r => {{ if(!q) return true; return (r.topic + r.content).toLowerCase().includes(q); }});
    if(rs.length){{
      html += `<div><div style="font-size:1rem;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:8px;color:var(--purple)">運用ルール <span style="font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:500;background:rgba(124,58,237,.1);color:var(--purple)">${{rs.length}}</span></div>`;
      html += `<table><thead><tr><th>#</th><th>トピック</th><th>内容</th><th>出典</th></tr></thead><tbody>`;
      rs.forEach((r, i) => {{
        html += `<tr><td>${{i+1}}</td><td class="name">${{r.topic}}</td><td class="note" style="max-width:500px">${{r.content}}</td><td class="note">${{r.source || ''}}</td></tr>`;
      }});
      html += `</tbody></table></div>`;
    }}
  }}

  el.innerHTML = html;
}}

// === Email Modal ===
function openMailModal(topic){{
  const d = EMAIL_DATA[topic];
  if(!d){{ alert('このカードにはメールデータが紐づいていません（引き継ぎ正本由来）'); return; }}
  document.getElementById('modalTitle').textContent = d.subject;
  document.getElementById('modalSender').textContent = 'From: ' + d.sender;
  document.getElementById('modalDate').textContent = d.date;
  document.getElementById('modalBody').textContent = d.body;
  const attsEl = document.getElementById('modalAtts');
  const attList = document.getElementById('modalAttList');
  if(d.attachments && d.attachments.length){{
    attsEl.style.display = '';
    attList.innerHTML = d.attachments.map(a => `<div class="modal-att">${{a}}</div>`).join('');
  }} else {{ attsEl.style.display = 'none'; }}
  document.getElementById('modalOverlay').classList.add('open');
}}
function closeModal(){{ document.getElementById('modalOverlay').classList.remove('open'); }}
document.addEventListener('keydown', e => {{ if(e.key === 'Escape') closeModal(); }});

// === Search ===
document.getElementById('search').addEventListener('input', e => {{
  currentQuery = e.target.value;
  render(currentTab, currentQuery);
}});

// === Init ===
buildTabs();
render('briefing', '');
document.getElementById('updated').textContent = '最終更新: ' + new Date().toLocaleString('ja-JP');
</script>
</body>
</html>'''

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nGenerated: {OUTPUT}")
print(f"Size: {len(html):,} bytes")
