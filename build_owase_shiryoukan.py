#!/usr/bin/env python3
"""
尾鷲郷土資料館 HTML Generator
owase-local-db.jsonl + image_manifest.jsonl → museum-like single HTML page
"""
import json, html as h
from pathlib import Path

BASE = Path("/Users/rtano/Documents/WorkSpace ")
OWASE_DB = BASE / "memory/owase-local-db.jsonl"
IMG_MANIFEST = BASE / "文章_作業スペース/00_受信箱_Inbox/web_images_owase/image_manifest.jsonl"
HISTORY_DB = BASE / "memory/history-japan-db.jsonl"
OUTPUT = BASE / "priority-ai-demo/owase_shiryoukan.html"
IMG_REL = "../文章_作業スペース/00_受信箱_Inbox/"

# --- Load data ---
records = [json.loads(l) for l in open(OWASE_DB)]
img_manifest = {json.loads(l)["id"]: json.loads(l) for l in open(IMG_MANIFEST)}

# history connections
history_records = []
try:
    for l in open(HISTORY_DB):
        r = json.loads(l)
        if r.get("owase_connection"):
            history_records.append(r)
except: pass

# --- Smart image matching ---
# Build keyword index for each image in manifest
def tokenize(text):
    """Extract meaningful Japanese keywords (2+ chars)"""
    import re
    # Remove common short words, keep meaningful ones
    tokens = set()
    # Split on non-word chars and spaces
    for w in re.split(r'[\s,、。・\-_/()（）\[\]]+', text.lower()):
        w = w.strip()
        if len(w) >= 2:
            tokens.add(w)
    return tokens

img_keywords = {}
for wid, mi in img_manifest.items():
    kw = set()
    for field in ['title', 'description', 'location']:
        kw |= tokenize(mi.get(field, ''))
    for t in mi.get('tags', []):
        kw |= tokenize(t)
    img_keywords[wid] = kw

# All image entries ready for matching
all_images = []
for wid, mi in img_manifest.items():
    p = mi.get('local_path', '')
    if p:
        all_images.append({
            "wid": wid,
            "p": IMG_REL + p,
            "t": mi.get("title", ""),
            "u": mi.get("source_url", ""),
            "li": mi.get("license", ""),
            "loc": mi.get("location", ""),
            "lat": mi.get("lat", ""),
            "lng": mi.get("lng", ""),
            "kw": img_keywords.get(wid, set()),
        })

# Weighted scoring: content-specific matches count more than location-only matches
# HIGH: 画像の内容（何が写っているか）と記事の主題が一致
# 食材名（ブリ、カツオ等）は含めない。料理名（梶賀のあぶり、さんま寿司等）で十分。
# 食材名を入れると「早田ブリまつり」→梶賀のあぶり写真のような地名不一致が起きる。
CONTENT_KW = {
    'ヤーヤ祭り','尾鷲節','わっぱ','ヒノキ','深層水','河津桜','石畳','シダ',
    '燻製','養殖','林業',
    'オハイブルー','三木里ビーチ','柱状節理','象の背','シダ群落',
    '食べ物','漁業',
    'さんま寿司','めはり寿司','梶賀のあぶり','曲げわっぱ',
    'イタダキ市','尾鷲イタダキ市','三田火力','発電所',
    '学校','小学校','尾鷲小学校',
    '御神木','大楠','楠木',
    '尾鷲小唄',
    '尾鷲魚市場','水産',
    '尾鷲駅',
    '尾鷲ヒノキ','尾鷲わっぱ','曲げわっぱ','伝統工芸',
    '柱状節理','天然記念物',
}
# MEDIUM: 具体的な場所名（場所が合えば関連性は高い）
LOCATION_KW = {
    '九鬼','梶賀','三木浦','三木里','須賀利','向井','早田','賀田','曽根',
    '馬越峠','天狗倉山','便石山','八鬼山','ツヅラト峠','楯ヶ崎','九木崎',
    'オハイ','弁財島','中村山','尾鷲神社','夢古道','魚市場',
    '熊野古道','伊勢路',
    '尾鷲湾','尾鷲港',
    '金剛寺',
}
# LOW: 広すぎるキーワード（単独ではマッチさせない）
GENERIC_KW = {
    '尾鷲','三重県','三重','尾鷲市','海','山','川','風景','港','神社','祭り',
    '漁港','漁師町','九鬼水軍','九鬼湾','世界遺産','竹林',
    '朝市','花火','記念碑','魚','競り','駅','展望','市街',  # 汎用すぎる内容語
}

def weighted_score(overlap):
    """Content match=4, Location match=2, Generic=0.3"""
    score = 0
    for kw in overlap:
        if kw in CONTENT_KW:
            score += 4
        elif kw in LOCATION_KW:
            score += 2
        elif kw in GENERIC_KW:
            score += 0.3
        else:
            score += 0.5
    return score

def match_images_for_record(r, max_imgs=3):
    """Score all images against a record using weighted matching."""
    record_kw = tokenize(r.get("title", ""))
    for t in r.get("tags", []):
        record_kw |= tokenize(t)
    # Also extract from first 200 chars of content for extra keywords
    record_kw |= tokenize(r.get("content", "")[:200])

    if not record_kw:
        return []

    scored = []
    for img in all_images:
        overlap = record_kw & img["kw"]
        if overlap:
            score = weighted_score(overlap)
            scored.append((score, img))

    scored.sort(key=lambda x: -x[0])
    return scored[:max_imgs]

# --- Prepare JS data ---
# POLICY: weighted score >= 2.0
# = location keyword 1つ以上（その場所の写真なら記事に合う）
# generic keyword だけでは絶対にマッチしない (0.3 x 6 = 1.8 < 2.0)
MIN_MATCH_SCORE = 2.0

js_data = []
match_stats = {"confident": 0, "rejected_low": 0, "none": 0}
for r in records:
    matches = match_images_for_record(r)

    # Filter: only keep matches with score >= threshold
    confident_matches = [(score, img) for score, img in matches if score >= MIN_MATCH_SCORE]

    if confident_matches:
        match_stats["confident"] += 1
        imgs = [{
            "p": m[1]["p"],
            "t": m[1]["t"],
            "id": m[1]["wid"],
            "u": m[1]["u"],
            "li": m[1]["li"],
            "loc": m[1].get("loc", ""),
        } for m in confident_matches]
    else:
        if matches:
            match_stats["rejected_low"] += 1
        else:
            match_stats["none"] += 1
        imgs = []  # No image — honest is better than wrong
        imgs = []

    js_data.append({
        "id": r["id"],
        "c": r["category"],
        "t": r["title"],
        "x": r["content"],
        "e": r.get("edu_use", ""),
        "tg": r.get("tags", []),
        "im": imgs,
        "s": r.get("source", ""),
        "su": r.get("source_url", ""),
    })

print(f"  Image matching: confident(score>={MIN_MATCH_SCORE})={match_stats['confident']}, rejected_low={match_stats['rejected_low']}, no_match={match_stats['none']}")

# history data
js_history = []
for r in history_records:
    js_history.append({
        "id": r["id"],
        "era": r.get("era", ""),
        "t": r.get("title", ""),
        "oc": r.get("owase_connection", ""),
        "x": r.get("content", "")[:300],
    })

# Category config
CAT_ORDER = ["geography","nature","history","culture","food","industry",
             "tourism","people","education","society","energy","disaster","archive","modern"]
CAT_META = {
    "geography": {"n":"地理","i":"fa-solid fa-earth-asia","cl":"#5B7DB1","d":"三重県南部、海と山に囲まれたまち"},
    "nature":    {"n":"自然","i":"fa-solid fa-leaf","cl":"#4A7C59","d":"熊野古道、原生林、多様な生態系"},
    "history":   {"n":"歴史","i":"fa-solid fa-scroll","cl":"#8B7355","d":"九鬼水軍、熊野古道、千年の物語"},
    "culture":   {"n":"文化","i":"fa-solid fa-masks-theater","cl":"#B85A7A","d":"尾鷲節、祭り、暮らしの風景"},
    "food":      {"n":"食","i":"fa-solid fa-fish","cl":"#C8934A","d":"ブリ、さんま、ひもの、海の幸山の幸"},
    "industry":  {"n":"産業","i":"fa-solid fa-anchor","cl":"#6B8E7B","d":"漁業、林業、養殖、深層水"},
    "tourism":   {"n":"観光","i":"fa-solid fa-camera","cl":"#5B9BD5","d":"絶景スポット、温泉、トレッキング"},
    "people":    {"n":"人物","i":"fa-solid fa-users","cl":"#7B68A8","d":"尾鷲を支えた人々の記録"},
    "education": {"n":"教育","i":"fa-solid fa-graduation-cap","cl":"#4A90C8","d":"校外学習、教材、学びの資源"},
    "society":   {"n":"社会","i":"fa-solid fa-city","cl":"#6B7B8D","d":"人口、経済、まちづくり"},
    "energy":    {"n":"エネルギー","i":"fa-solid fa-bolt","cl":"#D4A840","d":"再生可能エネルギー、深層水"},
    "disaster":  {"n":"防災","i":"fa-solid fa-triangle-exclamation","cl":"#C45D5D","d":"東南海地震、津波、防災の知恵"},
    "archive":   {"n":"アーカイブ","i":"fa-solid fa-box-archive","cl":"#8B7B6B","d":"歴史資料、記録写真"},
    "modern":    {"n":"現代","i":"fa-solid fa-microchip","cl":"#5B8FA8","d":"現代産業、技術革新"},
}

# Stats
total = len(records)
with_img = sum(1 for r in records if r.get("web_images"))
total_imgs = len(img_manifest)
cat_counts = {}
for r in records:
    c = r["category"]
    cat_counts[c] = cat_counts.get(c, 0) + 1

# Pick hero images (best photos per category)
hero_candidates = []
for r in records:
    if r.get("web_images") and r["category"] in ("geography","nature","tourism"):
        hero_candidates.append(IMG_REL + r["web_images"][0]["path"])
hero_imgs = hero_candidates[:6] if hero_candidates else []

# Build overview data per category: representative images + sample titles
# Build overview using only confident image matches from js_data
cat_overview = {}
for d in js_data:
    c = d["c"]
    if c not in cat_overview:
        cat_overview[c] = {"imgs": [], "titles": []}
    if d["im"] and len(cat_overview[c]["imgs"]) < 4:
        cat_overview[c]["imgs"].append(d["im"][0]["p"])
    if len(cat_overview[c]["titles"]) < 5:
        cat_overview[c]["titles"].append(d["t"][:60])
js_cat_overview = {}
for c in CAT_ORDER:
    if c in cat_overview:
        js_cat_overview[c] = cat_overview[c]

html_out = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>尾鷲郷土資料館</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&family=Shippori+Mincho:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{font-size:16px;scroll-behavior:smooth}}
body{{font-family:'Inter','Noto Sans JP',sans-serif;min-height:100vh;transition:background .4s,color .3s}}

:root{{
  --bg:#FAF9F6;--surface:#FFFFFF;--surface-dim:#F5F3F0;--surface-container:#EDE9E3;
  --border:rgba(45,38,33,0.07);--border-mid:rgba(45,38,33,0.12);
  --text:#2d2621;--text-secondary:#6b6560;--text-dim:#a8a29e;
  --accent:#4A7C59;--accent-bg:rgba(74,124,89,0.07);
  --shadow-sm:0 2px 8px rgba(0,0,0,0.04);--shadow-md:0 4px 16px rgba(0,0,0,0.06);--shadow-lg:0 16px 40px rgba(0,0,0,0.1);
  --ease:cubic-bezier(.16,1,.3,1);
}}
body{{background:var(--bg);color:var(--text)}}
body.dark{{
  --bg:#111110;--surface:#1a1917;--surface-dim:#1e1d1b;--surface-container:#252320;
  --border:rgba(255,255,255,0.06);--border-mid:rgba(255,255,255,0.1);
  --text:#e8e4df;--text-secondary:#b5afa8;--text-dim:#6b6560;
  --accent:#7aad8a;--accent-bg:rgba(122,173,138,.1);
  --shadow-sm:0 2px 8px rgba(0,0,0,0.15);--shadow-md:0 4px 16px rgba(0,0,0,0.2);--shadow-lg:0 16px 40px rgba(0,0,0,0.3);
}}

/* Grain */
body::before{{
  content:"";position:fixed;inset:0;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity:0.03;pointer-events:none;z-index:9999;
}}

/* Hero */
.hero{{
  position:relative;height:420px;overflow:hidden;
  display:flex;align-items:flex-end;
}}
.hero-bg{{position:absolute;inset:0;background-size:cover;background-position:center;transition:opacity 1.5s ease}}
.hero-overlay{{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,0.75) 0%,rgba(0,0,0,0.15) 60%,rgba(0,0,0,0.3) 100%)}}
.hero-content{{position:relative;z-index:2;padding:40px 48px;width:100%}}
.hero-title{{font-family:'Shippori Mincho',serif;font-size:2.8rem;font-weight:700;color:#fff;margin-bottom:8px;letter-spacing:0.05em}}
.hero-sub{{font-size:1rem;color:rgba(255,255,255,0.8);margin-bottom:16px;font-weight:400}}
.hero-stats{{display:flex;gap:24px}}
.hero-stat{{display:flex;flex-direction:column;align-items:center}}
.hero-stat-num{{font-family:'Cormorant Garamond',serif;font-size:2rem;font-weight:700;color:#fff;line-height:1}}
.hero-stat-label{{font-size:0.7rem;color:rgba(255,255,255,0.7);margin-top:2px;font-weight:600;letter-spacing:0.05em}}

/* Top bar */
.topbar{{
  position:sticky;top:0;z-index:100;
  background:rgba(250,249,246,0.9);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-bottom:1px solid var(--border);padding:10px 32px;
  display:flex;align-items:center;gap:12px;
}}
body.dark .topbar{{background:rgba(17,17,16,0.9)}}
.topbar-back{{
  display:flex;align-items:center;gap:6px;color:var(--accent);text-decoration:none;font-size:14px;font-weight:600;
  padding:6px 12px;border-radius:8px;border:none;background:transparent;cursor:pointer;
  transition:background .2s;
}}
.topbar-back:hover{{background:var(--accent-bg)}}
.search-box{{
  flex:1;max-width:360px;padding:7px 12px 7px 32px;
  border:1px solid var(--border);border-radius:8px;background:var(--surface);
  color:var(--text);font-family:inherit;font-size:14px;outline:none;
  background-image:url('data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2214%22 height=%2214%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23a8a29e%22 stroke-width=%222%22><circle cx=%2211%22 cy=%2211%22 r=%228%22/><path d=%22m21 21-4.3-4.3%22/></svg>');
  background-repeat:no-repeat;background-position:10px center;
}}
.search-box:focus{{border-color:var(--accent)}}
.theme-btn{{
  width:34px;height:34px;border-radius:8px;border:1px solid var(--border);
  background:var(--surface);color:var(--text-dim);cursor:pointer;
  display:flex;align-items:center;justify-content:center;transition:all .2s;
}}
.theme-btn:hover{{border-color:var(--accent);color:var(--accent)}}

/* Category pills */
.cat-bar{{
  padding:12px 32px;display:flex;gap:6px;flex-wrap:wrap;
  border-bottom:1px solid var(--border);background:var(--bg);
}}
.cat-pill{{
  padding:5px 14px;border-radius:20px;border:1px solid var(--border);
  background:var(--surface);color:var(--text-secondary);font-size:13px;font-weight:600;
  cursor:pointer;transition:all .25s var(--ease);display:flex;align-items:center;gap:5px;
  font-family:inherit;
}}
.cat-pill:hover{{border-color:var(--accent);color:var(--accent);background:var(--accent-bg)}}
.cat-pill.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.cat-pill .cnt{{font-size:11px;opacity:0.7;font-weight:700}}

/* Content area */
.content{{max-width:1400px;margin:0 auto;padding:24px 32px}}

/* ===== OVERVIEW GRID (館内案内) ===== */
.overview-section{{margin-bottom:32px}}
.overview-heading{{
  font-family:'Shippori Mincho',serif;font-size:1.3rem;font-weight:700;
  margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;
}}
.overview-heading span{{font-size:13px;font-weight:500;color:var(--text-dim);font-family:'Inter','Noto Sans JP',sans-serif}}
.overview-grid{{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  grid-auto-rows:auto;
  gap:14px;
}}
.ov-card{{
  position:relative;border-radius:14px;overflow:hidden;cursor:pointer;
  background:var(--surface);border:1px solid var(--border);
  transition:all .35s var(--ease);display:flex;flex-direction:column;
}}
.ov-card:hover{{transform:translateY(-3px);box-shadow:var(--shadow-lg)}}
.ov-card.large{{grid-column:span 2;grid-row:span 2}}
.ov-card-photos{{
  display:grid;gap:2px;width:100%;overflow:hidden;
}}
.ov-card-photos.single{{grid-template-columns:1fr}}
.ov-card-photos.duo{{grid-template-columns:1fr 1fr}}
.ov-card-photos.trio{{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}}
.ov-card-photos.trio img:first-child{{grid-row:span 2}}
.ov-card-photos.quad{{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}}
.ov-card-photos img{{
  width:100%;height:100%;object-fit:cover;display:block;
  transition:transform .6s ease;
}}
.ov-card:hover .ov-card-photos img{{transform:scale(1.04)}}
.ov-card-photos.single{{aspect-ratio:16/9}}
.ov-card-photos.duo,.ov-card-photos.trio,.ov-card-photos.quad{{aspect-ratio:16/9}}
.ov-card.large .ov-card-photos{{aspect-ratio:16/10}}
.ov-card-body{{padding:14px 16px 16px;flex:1;display:flex;flex-direction:column}}
.ov-card-top{{display:flex;align-items:center;gap:8px;margin-bottom:6px}}
.ov-card-icon{{
  width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;
  font-size:14px;color:#fff;flex-shrink:0;
}}
.ov-card-name{{font-size:16px;font-weight:700}}
.ov-card-count{{
  margin-left:auto;font-family:'Cormorant Garamond',serif;font-size:1.5rem;font-weight:700;
  color:var(--text-dim);line-height:1;
}}
.ov-card-desc{{font-size:12.5px;color:var(--text-secondary);margin-bottom:8px}}
.ov-card-titles{{display:flex;flex-direction:column;gap:2px;flex:1}}
.ov-card-titles span{{
  font-size:12px;color:var(--text-dim);line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;
}}
.ov-card-titles span::before{{content:"\\2014\\00a0";opacity:0.4}}
.ov-card-enter{{
  display:flex;align-items:center;gap:4px;
  font-size:12px;font-weight:600;color:var(--accent);margin-top:8px;
  transition:gap .2s;
}}
.ov-card:hover .ov-card-enter{{gap:8px}}

/* Stats bar */
.stats-bar{{
  display:flex;gap:24px;padding:20px 28px;margin-bottom:24px;
  background:var(--surface);border:1px solid var(--border);border-radius:14px;
  flex-wrap:wrap;
}}
.stat-item{{display:flex;flex-direction:column;align-items:center;min-width:80px}}
.stat-num{{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:700;color:var(--text);line-height:1}}
.stat-label{{font-size:11px;font-weight:600;color:var(--text-dim);letter-spacing:0.05em;margin-top:2px}}

/* ===== CONCIERGE ===== */
.concierge{{
  margin-bottom:28px;background:var(--surface);border:1px solid var(--border);border-radius:16px;
  padding:24px 28px;
}}
.concierge-title{{
  font-family:'Shippori Mincho',serif;font-size:1.1rem;font-weight:700;
  margin-bottom:4px;display:flex;align-items:center;gap:8px;
}}
.concierge-sub{{font-size:13px;color:var(--text-dim);margin-bottom:16px}}
.concierge-input-wrap{{
  display:flex;gap:8px;margin-bottom:14px;
}}
.concierge-input{{
  flex:1;padding:10px 16px;border:1px solid var(--border-mid);border-radius:10px;
  background:var(--bg);color:var(--text);font-family:inherit;font-size:15px;outline:none;
  transition:border-color .2s;
}}
.concierge-input:focus{{border-color:var(--accent)}}
.concierge-input::placeholder{{color:var(--text-dim)}}
.concierge-send{{
  padding:10px 20px;border-radius:10px;border:none;
  background:var(--accent);color:#fff;font-family:inherit;font-size:14px;font-weight:600;
  cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:6px;
}}
.concierge-send:hover{{filter:brightness(1.1)}}
.concierge-courses{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:0}}
.concierge-course{{
  padding:6px 14px;border-radius:20px;border:1px solid var(--border);
  background:var(--bg);color:var(--text-secondary);font-size:13px;font-weight:500;
  cursor:pointer;transition:all .2s;font-family:inherit;
  display:flex;align-items:center;gap:5px;
}}
.concierge-course:hover{{border-color:var(--accent);color:var(--accent);background:var(--accent-bg)}}

/* Concierge response */
.concierge-response{{
  margin-top:20px;padding-top:18px;border-top:1px solid var(--border);
  animation:fadeUp .4s var(--ease);
}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.concierge-answer{{
  font-size:15px;line-height:1.7;color:var(--text);margin-bottom:16px;
}}
.concierge-answer strong{{color:var(--accent)}}
.concierge-picks{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}}
.concierge-pick{{
  display:flex;gap:12px;padding:12px;border-radius:12px;
  background:var(--bg);border:1px solid var(--border);cursor:pointer;
  transition:all .25s var(--ease);align-items:flex-start;
}}
.concierge-pick:hover{{border-color:var(--accent);background:var(--accent-bg);transform:translateY(-1px)}}
.concierge-pick-img{{
  width:72px;height:54px;border-radius:8px;object-fit:cover;flex-shrink:0;background:var(--surface-dim);
}}
.concierge-pick-body{{flex:1;min-width:0}}
.concierge-pick-cat{{font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;color:#fff;display:inline-block;margin-bottom:3px}}
.concierge-pick-title{{font-size:13.5px;font-weight:700;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.concierge-pick-excerpt{{font-size:12px;color:var(--text-dim);line-height:1.4;margin-top:2px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.concierge-typing{{display:flex;align-items:center;gap:4px;padding:8px 0}}
.concierge-typing span{{width:6px;height:6px;border-radius:50%;background:var(--accent);opacity:0.3;animation:typingDot 1.2s ease-in-out infinite}}
.concierge-typing span:nth-child(2){{animation-delay:0.2s}}
.concierge-typing span:nth-child(3){{animation-delay:0.4s}}
@keyframes typingDot{{0%,60%,100%{{opacity:0.3;transform:translateY(0)}}30%{{opacity:1;transform:translateY(-4px)}}}}

/* ===== MAP VIEW ===== */
.map-container{{width:100%;height:calc(100vh - 200px);min-height:500px;border-radius:16px;overflow:hidden;border:1px solid var(--border)}}
.map-sidebar{{
  position:absolute;top:10px;right:10px;z-index:1000;
  width:320px;max-height:calc(100% - 20px);overflow-y:auto;
  background:var(--surface);border-radius:12px;border:1px solid var(--border);
  box-shadow:var(--shadow-lg);
}}
.map-sidebar-header{{padding:12px 16px;border-bottom:1px solid var(--border);font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px}}
.map-sidebar-list{{max-height:400px;overflow-y:auto}}
.map-sidebar-item{{
  display:flex;gap:10px;padding:10px 14px;cursor:pointer;transition:background .15s;
  border-bottom:1px solid var(--border);align-items:flex-start;
}}
.map-sidebar-item:hover{{background:var(--accent-bg)}}
.map-sidebar-item img{{width:52px;height:40px;border-radius:6px;object-fit:cover;flex-shrink:0}}
.map-sidebar-item-body{{flex:1;min-width:0}}
.map-sidebar-item-title{{font-size:12.5px;font-weight:600;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.3}}
.map-sidebar-item-cat{{font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;color:#fff;display:inline-block;margin-top:2px}}
.leaflet-popup-content{{font-family:'Inter','Noto Sans JP',sans-serif;font-size:13px;line-height:1.5}}
.leaflet-popup-content strong{{font-size:14px}}

@media(max-width:960px){{
  .overview-grid{{grid-template-columns:repeat(2,1fr)}}
  .ov-card.large{{grid-column:span 2;grid-row:span 1}}
  .map-sidebar{{width:100%;position:relative;top:0;right:0;border-radius:0 0 12px 12px}}
}}
@media(max-width:600px){{
  .overview-grid{{grid-template-columns:1fr}}
  .ov-card.large{{grid-column:span 1}}
}}

/* Room header */
.room-header{{
  margin:32px 0 16px;padding:20px 24px;border-radius:16px;
  background:var(--surface);border:1px solid var(--border);
  display:flex;align-items:center;gap:16px;
}}
.room-header:first-child{{margin-top:0}}
.room-icon{{
  width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;
  font-size:1.2rem;color:#fff;flex-shrink:0;
}}
.room-info h2{{font-size:1.2rem;font-weight:700;margin-bottom:2px}}
.room-info p{{font-size:13px;color:var(--text-secondary)}}
.room-count{{margin-left:auto;font-family:'Cormorant Garamond',serif;font-size:1.8rem;font-weight:700;color:var(--text-dim);line-height:1}}

/* Card grid */
.card-grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;
  margin-bottom:8px;
}}
.card{{
  background:var(--surface);border:1px solid var(--border);border-radius:14px;
  overflow:hidden;cursor:pointer;transition:all .35s var(--ease);
}}
.card:hover{{transform:translateY(-3px);box-shadow:var(--shadow-lg)}}
.card-img{{
  width:100%;aspect-ratio:16/10;object-fit:cover;background:var(--surface-dim);
  display:block;
}}
.card-img-placeholder{{
  width:100%;aspect-ratio:16/10;background:var(--surface-dim);
  display:flex;align-items:center;justify-content:center;
}}
.card-img-placeholder i{{font-size:2rem;color:var(--text-dim);opacity:0.3}}
.card-body{{padding:14px 16px 16px}}
.card-cat{{
  display:inline-block;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:5px;
  margin-bottom:6px;color:#fff;
}}
.card-title{{font-size:15px;font-weight:700;line-height:1.4;margin-bottom:6px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.card-excerpt{{
  font-size:13px;color:var(--text-secondary);line-height:1.6;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
}}
.card-tags{{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}}
.card-tag{{font-size:10.5px;padding:1px 6px;border-radius:4px;background:var(--surface-dim);color:var(--text-dim)}}

/* Detail modal */
.modal-overlay{{
  position:fixed;inset:0;z-index:1000;
  background:rgba(0,0,0,0.5);backdrop-filter:blur(4px);
  opacity:0;pointer-events:none;transition:opacity .3s;
  display:flex;justify-content:flex-end;
}}
.modal-overlay.open{{opacity:1;pointer-events:auto}}
.modal-panel{{
  width:640px;max-width:90vw;height:100vh;background:var(--bg);
  overflow-y:auto;transform:translateX(100%);transition:transform .4s var(--ease);
  box-shadow:-8px 0 32px rgba(0,0,0,0.15);
}}
.modal-overlay.open .modal-panel{{transform:translateX(0)}}
.modal-close{{
  position:sticky;top:12px;float:right;margin:12px 12px 0 0;
  width:36px;height:36px;border-radius:8px;border:1px solid var(--border);
  background:var(--surface);color:var(--text-dim);cursor:pointer;z-index:10;
  display:flex;align-items:center;justify-content:center;transition:all .2s;
}}
.modal-close:hover{{border-color:var(--accent);color:var(--accent)}}
.modal-gallery{{position:relative;width:100%;aspect-ratio:16/10;background:#111;overflow:hidden}}
.modal-gallery img{{width:100%;height:100%;object-fit:contain;transition:opacity .4s}}
.modal-gallery-nav{{
  position:absolute;top:50%;transform:translateY(-50%);
  width:36px;height:36px;border-radius:50%;border:none;
  background:rgba(255,255,255,0.15);backdrop-filter:blur(8px);
  color:#fff;cursor:pointer;font-size:14px;
  display:flex;align-items:center;justify-content:center;transition:all .2s;
}}
.modal-gallery-nav:hover{{background:rgba(255,255,255,0.3)}}
.modal-gallery-nav.left{{left:12px}}
.modal-gallery-nav.right{{right:12px}}
.modal-gallery-counter{{
  position:absolute;bottom:8px;right:12px;
  font-size:12px;color:rgba(255,255,255,0.7);
  background:rgba(0,0,0,0.4);padding:2px 8px;border-radius:4px;
}}
.modal-body{{padding:24px 28px 40px}}
.modal-cat-badge{{
  display:inline-block;font-size:11px;font-weight:700;padding:3px 10px;border-radius:6px;
  color:#fff;margin-bottom:10px;
}}
.modal-title{{font-family:'Shippori Mincho',serif;font-size:1.4rem;font-weight:700;line-height:1.5;margin-bottom:16px}}
.modal-content{{font-size:14.5px;line-height:1.9;color:var(--text);margin-bottom:24px;white-space:pre-wrap}}
.modal-section{{margin-bottom:20px}}
.modal-section-title{{
  font-size:12px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:0.08em;
  margin-bottom:8px;display:flex;align-items:center;gap:6px;
}}
.modal-edu{{
  font-size:13.5px;line-height:1.8;color:var(--text-secondary);
  padding:16px;border-radius:10px;background:var(--accent-bg);
}}
.modal-tags{{display:flex;gap:5px;flex-wrap:wrap}}
.modal-tag{{font-size:12px;padding:3px 10px;border-radius:6px;background:var(--surface-dim);color:var(--text-secondary);font-weight:500}}
.modal-source{{font-size:12px;color:var(--text-dim);margin-top:12px}}

/* History timeline */
.timeline{{display:flex;flex-direction:column;gap:12px;margin-top:12px}}
.timeline-item{{
  display:flex;gap:14px;padding:14px 16px;border-radius:12px;
  background:var(--surface);border:1px solid var(--border);transition:all .2s;
}}
.timeline-item:hover{{border-color:var(--accent);background:var(--accent-bg)}}
.timeline-era{{
  flex-shrink:0;width:56px;height:56px;border-radius:10px;
  background:linear-gradient(135deg,#8B7355,#A0896A);
  display:flex;align-items:center;justify-content:center;
  font-size:12px;font-weight:700;color:#fff;text-align:center;line-height:1.2;
}}
.timeline-body h4{{font-size:14px;font-weight:700;margin-bottom:4px}}
.timeline-body p{{font-size:13px;color:var(--text-secondary);line-height:1.6}}

/* Scroll top */
.scroll-top{{
  position:fixed;bottom:24px;right:24px;z-index:90;
  width:42px;height:42px;border-radius:50%;border:1px solid var(--border);
  background:var(--surface);color:var(--text-dim);cursor:pointer;
  box-shadow:var(--shadow-md);display:flex;align-items:center;justify-content:center;
  opacity:0;transition:all .3s;pointer-events:none;
}}
.scroll-top.show{{opacity:1;pointer-events:auto}}
.scroll-top:hover{{color:var(--accent);border-color:var(--accent)}}

/* Loading skeleton */
.skeleton{{animation:pulse 1.5s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}

/* Print */
@media print{{
  .topbar,.cat-bar,.modal-overlay,.scroll-top,.theme-btn,.search-box{{display:none!important}}
  .hero{{height:200px}}
  .card-grid{{grid-template-columns:repeat(2,1fr)}}
}}

/* Responsive */
@media(max-width:768px){{
  .hero{{height:300px}}
  .hero-title{{font-size:2rem}}
  .hero-content{{padding:24px}}
  .topbar{{padding:10px 16px}}
  .cat-bar{{padding:10px 16px}}
  .content{{padding:16px}}
  .card-grid{{grid-template-columns:1fr}}
  .modal-panel{{width:100vw;max-width:100vw}}
}}
</style>
</head>
<body>

<!-- Hero -->
<div class="hero" id="hero">
  <div class="hero-bg" id="heroBg" style="background-image:url('{hero_imgs[0] if hero_imgs else ""}')"></div>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <div class="hero-title">尾鷲郷土資料館</div>
    <div class="hero-sub">三重県尾鷲市 — 海と山と雨のまちの記憶</div>
    <div class="hero-stats">
      <div class="hero-stat"><div class="hero-stat-num">{total}</div><div class="hero-stat-label">ARTICLES</div></div>
      <div class="hero-stat"><div class="hero-stat-num">{total_imgs}</div><div class="hero-stat-label">PHOTOS</div></div>
      <div class="hero-stat"><div class="hero-stat-num">{len(CAT_ORDER)}</div><div class="hero-stat-label">ROOMS</div></div>
      <div class="hero-stat"><div class="hero-stat-num">{len(history_records)}</div><div class="hero-stat-label">HISTORY</div></div>
    </div>
  </div>
</div>

<!-- Sticky topbar -->
<div class="topbar">
  <a href="kyoto-dashboard-improved.html" class="topbar-back"><i class="fa-solid fa-arrow-left"></i> ダッシュボードへ</a>
  <input type="text" class="search-box" id="searchBox" placeholder="記事・タグ・場所を検索..." oninput="handleSearch(this.value)">
  <div style="flex:1"></div>
  <span id="resultCount" style="font-size:13px;color:var(--text-dim);font-weight:600"></span>
  <button class="theme-btn" onclick="toggleTheme()" title="テーマ切替"><i class="fa-solid fa-circle-half-stroke"></i></button>
</div>

<!-- Category bar -->
<div class="cat-bar" id="catBar"></div>

<!-- Main content -->
<div class="content" id="mainContent"></div>

<!-- Detail modal -->
<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-panel" id="modalPanel">
    <button class="modal-close" onclick="closeModal()"><i class="fa-solid fa-xmark"></i></button>
    <div class="modal-gallery" id="modalGallery"></div>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<!-- Scroll to top -->
<button class="scroll-top" id="scrollTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})"><i class="fa-solid fa-arrow-up"></i></button>

<script>
// ═══ DATA ═══
const DATA = {json.dumps(js_data, ensure_ascii=False, separators=(',', ':'))};
const HISTORY = {json.dumps(js_history, ensure_ascii=False, separators=(',', ':'))};
const CAT_ORDER = {json.dumps(CAT_ORDER)};
const CAT_META = {json.dumps(CAT_META, ensure_ascii=False, separators=(',', ':'))};
const CAT_OVERVIEW = {json.dumps(js_cat_overview, ensure_ascii=False, separators=(',', ':'))};

// ═══ STATE ═══
let activeCat = 'all';
let searchQuery = '';
let modalImgIdx = 0;
let modalImgs = [];
let heroIdx = 0;

// ═══ HERO SLIDESHOW ═══
const heroImgs = {json.dumps(hero_imgs[:8], ensure_ascii=False)};
if (heroImgs.length > 1) {{
  setInterval(() => {{
    heroIdx = (heroIdx + 1) % heroImgs.length;
    const bg = document.getElementById('heroBg');
    bg.style.opacity = '0';
    setTimeout(() => {{
      bg.style.backgroundImage = `url(${{heroImgs[heroIdx]}})`;
      bg.style.opacity = '1';
    }}, 800);
  }}, 6000);
}}

// ═══ THEME ═══
function toggleTheme() {{
  document.body.classList.toggle('dark');
  localStorage.setItem('owase-theme', document.body.classList.contains('dark') ? 'dark' : 'light');
}}
if (localStorage.getItem('owase-theme') === 'dark') document.body.classList.add('dark');

// ═══ CATEGORY BAR ═══
function renderCatBar() {{
  const el = document.getElementById('catBar');
  const counts = {{}};
  DATA.forEach(r => counts[r.c] = (counts[r.c] || 0) + 1);
  let html = `<button class="cat-pill ${{activeCat==='all'?'active':''}}" onclick="setCat('all')"><i class="fa-solid fa-grip"></i> すべて <span class="cnt">${{DATA.length}}</span></button>`;
  CAT_ORDER.forEach(c => {{
    const m = CAT_META[c];
    if (!m || !counts[c]) return;
    html += `<button class="cat-pill ${{activeCat===c?'active':''}}" onclick="setCat('${{c}}')" style="${{activeCat===c?`background:${{m.cl}};border-color:${{m.cl}}`:''}}"><i class="${{m.i}}" style="font-size:12px"></i> ${{m.n}} <span class="cnt">${{counts[c]}}</span></button>`;
  }});
  // History connection tab
  if (HISTORY.length) {{
    html += `<button class="cat-pill ${{activeCat==='history-connection'?'active':''}}" onclick="setCat('history-connection')" style="${{activeCat==='history-connection'?'background:#8B7355;border-color:#8B7355':''}}"><i class="fa-solid fa-link" style="font-size:12px"></i> 歴史接続 <span class="cnt">${{HISTORY.length}}</span></button>`;
  }}
  // Map view
  html += `<button class="cat-pill ${{activeCat==='map'?'active':''}}" onclick="setCat('map')" style="${{activeCat==='map'?'background:#5B7DB1;border-color:#5B7DB1':''}}"><i class="fa-solid fa-map-location-dot" style="font-size:12px"></i> 地図</button>`;
  el.innerHTML = html;
}}

function setCat(c) {{
  activeCat = c;
  renderCatBar();
  renderContent();
  window.scrollTo({{top: document.querySelector('.content').offsetTop - 120, behavior: 'smooth'}});
}}

// ═══ SEARCH ═══
function handleSearch(q) {{
  searchQuery = q.toLowerCase();
  renderContent();
}}

function matchSearch(r) {{
  if (!searchQuery) return true;
  const hay = (r.t + ' ' + r.x + ' ' + (r.tg||[]).join(' ') + ' ' + r.c).toLowerCase();
  return searchQuery.split(/\\s+/).every(w => hay.includes(w));
}}

// ═══ RENDER ═══
function renderContent() {{
  const el = document.getElementById('mainContent');

  if (activeCat === 'history-connection') {{
    renderHistoryView(el);
    return;
  }}
  if (activeCat === 'map') {{
    renderMapView(el);
    return;
  }}

  const filtered = DATA.filter(r => {{
    if (activeCat !== 'all' && r.c !== activeCat) return false;
    return matchSearch(r);
  }});

  document.getElementById('resultCount').textContent = filtered.length < DATA.length ? `${{filtered.length}}件` : '';

  if (activeCat === 'all' && !searchQuery) {{
    // === OVERVIEW MODE: 館内案内 ===
    const counts = {{}};
    DATA.forEach(r => counts[r.c] = (counts[r.c] || 0) + 1);
    const totalRecords = DATA.length;
    const totalWithImg = DATA.filter(r => r.im.length > 0).length;

    let html = `
      <div class="concierge" id="conciergePanel">
        <div class="concierge-title"><i class="fa-solid fa-compass" style="color:var(--accent)"></i> 尾鷲コンシェルジュ</div>
        <div class="concierge-sub">尾鷲について何でも聞いてください。955件の記事から答えを探します。</div>
        <div class="concierge-input-wrap">
          <input type="text" class="concierge-input" id="conciergeInput" placeholder="例: 尾鷲で有名な食べ物は？" onkeydown="if(event.key==='Enter')askConcierge()">
          <button class="concierge-send" onclick="askConcierge()"><i class="fa-solid fa-paper-plane"></i> 聞く</button>
        </div>
        <div class="concierge-courses">
          <button class="concierge-course" onclick="askPreset('intro')"><i class="fa-solid fa-info-circle" style="font-size:12px"></i> 尾鷲ってどんなまち？</button>
          <button class="concierge-course" onclick="askPreset('food')"><i class="fa-solid fa-utensils" style="font-size:12px"></i> おすすめグルメ</button>
          <button class="concierge-course" onclick="askPreset('nature')"><i class="fa-solid fa-mountain-sun" style="font-size:12px"></i> 自然を歩く</button>
          <button class="concierge-course" onclick="askPreset('history')"><i class="fa-solid fa-landmark" style="font-size:12px"></i> 歴史を辿る</button>
          <button class="concierge-course" onclick="askPreset('disaster')"><i class="fa-solid fa-shield-halved" style="font-size:12px"></i> 防災を学ぶ</button>
          <button class="concierge-course" onclick="askPreset('kids')"><i class="fa-solid fa-children" style="font-size:12px"></i> 子どもに見せたい</button>
          <button class="concierge-course" onclick="askPreset('random')"><i class="fa-solid fa-shuffle" style="font-size:12px"></i> 今日のおすすめ</button>
        </div>
        <div id="conciergeResponse"></div>
      </div>

      <div class="stats-bar">
        <div class="stat-item"><div class="stat-num">${{totalRecords}}</div><div class="stat-label">ARTICLES</div></div>
        <div class="stat-item"><div class="stat-num">${{totalWithImg}}</div><div class="stat-label">WITH PHOTO</div></div>
        <div class="stat-item"><div class="stat-num">${{CAT_ORDER.length}}</div><div class="stat-label">CATEGORIES</div></div>
        <div class="stat-item"><div class="stat-num">${{HISTORY.length}}</div><div class="stat-label">HISTORY LINKS</div></div>
      </div>
      <div class="overview-section">
        <div class="overview-heading"><i class="fa-solid fa-map" style="color:var(--accent)"></i> 展示室一覧 <span>- クリックで各展示室へ</span></div>
        <div class="overview-grid">
    `;

    // Large cards: food, nature, tourism, culture (top 4 by count)
    const largeSet = new Set(['food','nature','tourism','culture']);

    CAT_ORDER.forEach((c, idx) => {{
      const m = CAT_META[c];
      const ov = CAT_OVERVIEW[c];
      if (!m || !ov) return;
      const cnt = counts[c] || 0;
      const isLarge = largeSet.has(c) && idx < 7;
      const imgs = ov.imgs || [];
      const titles = ov.titles || [];

      // Photo mosaic
      let photoClass = 'single';
      let photoCount = 1;
      if (isLarge && imgs.length >= 4) {{ photoClass = 'quad'; photoCount = 4; }}
      else if (isLarge && imgs.length >= 3) {{ photoClass = 'trio'; photoCount = 3; }}
      else if (imgs.length >= 2) {{ photoClass = 'duo'; photoCount = 2; }}

      let photoHtml = '';
      if (imgs.length > 0) {{
        photoHtml = `<div class="ov-card-photos ${{photoClass}}">`;
        for (let i = 0; i < Math.min(photoCount, imgs.length); i++) {{
          photoHtml += `<img loading="lazy" src="${{imgs[i]}}" alt="">`;
        }}
        photoHtml += '</div>';
      }} else {{
        photoHtml = `<div class="ov-card-photos single" style="background:var(--surface-dim);display:flex;align-items:center;justify-content:center"><i class="${{m.i}}" style="font-size:2.5rem;color:var(--text-dim);opacity:0.2"></i></div>`;
      }}

      const titlesHtml = titles.slice(0, isLarge ? 5 : 3).map(t => `<span>${{t}}</span>`).join('');

      html += `
        <div class="ov-card${{isLarge ? ' large' : ''}}" onclick="setCat('${{c}}')">
          ${{photoHtml}}
          <div class="ov-card-body">
            <div class="ov-card-top">
              <div class="ov-card-icon" style="background:${{m.cl}}"><i class="${{m.i}}"></i></div>
              <div class="ov-card-name">${{m.n}}</div>
              <div class="ov-card-count">${{cnt}}</div>
            </div>
            <div class="ov-card-desc">${{m.d}}</div>
            <div class="ov-card-titles">${{titlesHtml}}</div>
            <div class="ov-card-enter">展示室に入る <i class="fa-solid fa-arrow-right" style="font-size:10px"></i></div>
          </div>
        </div>
      `;
    }});

    // History connection card
    if (HISTORY.length) {{
      html += `
        <div class="ov-card" onclick="setCat('history-connection')">
          <div class="ov-card-photos single" style="background:linear-gradient(135deg,#8B7355 0%,#A0896A 50%,#6B5B4B 100%);display:flex;align-items:center;justify-content:center">
            <i class="fa-solid fa-link" style="font-size:3rem;color:rgba(255,255,255,0.3)"></i>
          </div>
          <div class="ov-card-body">
            <div class="ov-card-top">
              <div class="ov-card-icon" style="background:#8B7355"><i class="fa-solid fa-link"></i></div>
              <div class="ov-card-name">歴史接続</div>
              <div class="ov-card-count">${{HISTORY.length}}</div>
            </div>
            <div class="ov-card-desc">6年社会科「日本の歴史」×尾鷲のつながり</div>
            <div class="ov-card-titles">
              <span>縄文〜現代の各時代と尾鷲の接点</span>
              <span>九鬼水軍、熊野古道、尾鷲ヒノキ</span>
            </div>
            <div class="ov-card-enter">タイムラインを見る <i class="fa-solid fa-arrow-right" style="font-size:10px"></i></div>
          </div>
        </div>
      `;
    }}

    html += '</div></div>';
    el.innerHTML = html;
  }} else if (activeCat === 'all' && searchQuery) {{
    // Search results flat grid
    let html = `<div class="card-grid">${{filtered.map(r => renderCard(r)).join('')}}</div>`;
    if (!filtered.length) html += `<div style="text-align:center;padding:60px;color:var(--text-dim);font-size:15px">該当する記事がありません</div>`;
    el.innerHTML = html;
    lazyLoad();
  }} else {{
    // Flat grid
    let html = '';
    if (activeCat !== 'all') {{
      const m = CAT_META[activeCat];
      html += `<div class="room-header" style="margin-top:0">
        <div class="room-icon" style="background:${{m.cl}}"><i class="${{m.i}}"></i></div>
        <div class="room-info"><h2>${{m.n}}</h2><p>${{m.d}}</p></div>
        <div class="room-count">${{filtered.length}}</div>
      </div>`;
    }}
    html += `<div class="card-grid">${{filtered.map(r => renderCard(r)).join('')}}</div>`;
    if (!filtered.length) html += `<div style="text-align:center;padding:60px;color:var(--text-dim);font-size:15px">該当する記事がありません</div>`;
    el.innerHTML = html;
  }}

  // Lazy load images
  lazyLoad();
}}

function renderRoom(cat, meta, items) {{
  const showItems = items.slice(0, 9); // Show first 9
  const hasMore = items.length > 9;
  return `
    <div class="room-header" id="room-${{cat}}">
      <div class="room-icon" style="background:${{meta.cl}}"><i class="${{meta.i}}"></i></div>
      <div class="room-info"><h2>${{meta.n}}</h2><p>${{meta.d}}</p></div>
      <div class="room-count">${{items.length}}</div>
    </div>
    <div class="card-grid">${{showItems.map(r => renderCard(r)).join('')}}</div>
    ${{hasMore ? `<div style="text-align:center;margin:8px 0 24px"><button onclick="setCat('${{cat}}')" style="padding:8px 24px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--accent);font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s" onmouseover="this.style.background='var(--accent-bg)'" onmouseout="this.style.background='var(--surface)'">${{items.length}}件すべて見る <i class="fa-solid fa-arrow-right" style="font-size:12px;margin-left:4px"></i></button></div>` : ''}}
  `;
}}

// Location detection from tags/title
const LOC_NAMES = ['九鬼','馬越峠','三木里','賀田','弁財島','須賀利','梶賀','曽根','天狗倉山','便石山','八鬼山','向井','三木浦','古江','早田','大曽根浦','行野浦','中村山','熊野古道'];
function detectLocation(r) {{
  const hay = r.t + ' ' + (r.tg||[]).join(' ');
  // Check image location first
  if (r.im.length && r.im[0].loc) return r.im[0].loc;
  for (const loc of LOC_NAMES) {{
    if (hay.includes(loc)) return loc;
  }}
  return '';
}}

function renderCard(r) {{
  const m = CAT_META[r.c] || {{n:'?',cl:'#888'}};
  const imgHtml = r.im.length
    ? `<img class="card-img" loading="lazy" data-src="${{r.im[0].p}}" alt="${{r.t}}" onerror="this.parentElement.innerHTML='<div class=card-img-placeholder><i class=\\'${{m.i}}\\'></i></div>'">`
    : `<div class="card-img-placeholder"><i class="${{m.i}}"></i></div>`;
  const imgCount = r.im.length > 1 ? `<span style="position:absolute;top:8px;right:8px;font-size:11px;background:rgba(0,0,0,0.5);color:#fff;padding:1px 7px;border-radius:4px"><i class="fa-solid fa-images" style="margin-right:3px"></i>${{r.im.length}}</span>` : '';
  const loc = detectLocation(r);
  const locBadge = loc ? `<span style="position:absolute;bottom:8px;left:8px;font-size:10.5px;background:rgba(0,0,0,0.55);color:#fff;padding:2px 8px;border-radius:4px;backdrop-filter:blur(4px);display:flex;align-items:center;gap:3px"><i class="fa-solid fa-map-pin" style="font-size:9px"></i>${{loc}}</span>` : '';
  const excerpt = r.x.slice(0, 120) + (r.x.length > 120 ? '...' : '');
  const tags = (r.tg || []).slice(0, 4).map(t => `<span class="card-tag">${{t}}</span>`).join('');
  return `<div class="card" onclick="openModal('${{r.id}}')">
    <div style="position:relative">${{imgHtml}}${{imgCount}}${{locBadge}}</div>
    <div class="card-body">
      <span class="card-cat" style="background:${{m.cl}}">${{m.n}}</span>
      <div class="card-title">${{r.t}}</div>
      <div class="card-excerpt">${{excerpt}}</div>
      ${{tags ? `<div class="card-tags">${{tags}}</div>` : ''}}
    </div>
  </div>`;
}}

// ═══ HISTORY VIEW ═══
function renderHistoryView(el) {{
  document.getElementById('resultCount').textContent = '';
  let html = `
    <div class="room-header" style="margin-top:0">
      <div class="room-icon" style="background:#8B7355"><i class="fa-solid fa-link"></i></div>
      <div class="room-info"><h2>日本史と尾鷲の接続</h2><p>6年社会科「日本の歴史」各時代と尾鷲のつながり</p></div>
      <div class="room-count">${{HISTORY.length}}</div>
    </div>
    <div class="timeline">`;
  HISTORY.forEach(h => {{
    html += `<div class="timeline-item">
      <div class="timeline-era">${{h.era || '?'}}</div>
      <div class="timeline-body">
        <h4>${{h.t}}</h4>
        <p style="color:var(--accent);font-weight:600;font-size:13px;margin-bottom:4px">尾鷲との接続</p>
        <p>${{h.oc}}</p>
      </div>
    </div>`;
  }});
  html += '</div>';
  el.innerHTML = html;
}}

// ═══ MODAL ═══
function openModal(id) {{
  const r = DATA.find(d => d.id === id);
  if (!r) return;
  const m = CAT_META[r.c] || {{n:'?',cl:'#888'}};

  // Gallery
  modalImgs = r.im;
  modalImgIdx = 0;
  renderGallery();

  // Body
  let bodyHtml = `
    <span class="modal-cat-badge" style="background:${{m.cl}}">${{m.n}}</span>
    <div class="modal-title">${{r.t}}</div>
    <div class="modal-content">${{r.x}}</div>
  `;

  if (r.e) {{
    bodyHtml += `<div class="modal-section">
      <div class="modal-section-title"><i class="fa-solid fa-graduation-cap"></i> 教育活用</div>
      <div class="modal-edu">${{r.e}}</div>
    </div>`;
  }}

  if (r.tg && r.tg.length) {{
    bodyHtml += `<div class="modal-section">
      <div class="modal-section-title"><i class="fa-solid fa-tags"></i> タグ</div>
      <div class="modal-tags">${{r.tg.map(t => `<span class="modal-tag">${{t}}</span>`).join('')}}</div>
    </div>`;
  }}

  // Source links section
  const sourceLinks = [];
  if (r.su) sourceLinks.push({{label: '記事ソース', url: r.su}});
  // Image source links (unique)
  const seenUrls = new Set(r.su ? [r.su] : []);
  (r.im || []).forEach(img => {{
    if (img.u && !seenUrls.has(img.u)) {{
      seenUrls.add(img.u);
      const domain = img.u.split('/')[2] || '';
      const label = domain.includes('wikimedia') ? 'Wikimedia' : domain.includes('mie-eetoko') ? '三重フォトギャラリー' : domain.includes('flickr') || domain.includes('openverse') ? 'Flickr' : domain.includes('owase.lg.jp') ? '尾鷲市公式' : domain.includes('unsplash') ? 'Unsplash' : domain.includes('youtube') ? 'YouTube' : '外部リンク';
      sourceLinks.push({{label: `${{label}}: ${{img.t || '画像'}}`, url: img.u}});
    }}
  }});
  if (sourceLinks.length || r.s) {{
    bodyHtml += `<div class="modal-section">
      <div class="modal-section-title"><i class="fa-solid fa-arrow-up-right-from-square"></i> ソース・リンク</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        ${{r.s ? `<div style="font-size:12px;color:var(--text-dim);margin-bottom:4px"><i class="fa-solid fa-quote-left" style="margin-right:4px;opacity:0.5"></i>${{r.s}}</div>` : ''}}
        ${{sourceLinks.map(l => `<a href="${{l.url}}" target="_blank" rel="noopener" style="font-size:13px;color:var(--accent);text-decoration:none;display:flex;align-items:center;gap:5px;padding:4px 0;transition:opacity .2s" onmouseover="this.style.opacity='0.7'" onmouseout="this.style.opacity='1'"><i class="fa-solid fa-arrow-up-right-from-square" style="font-size:10px"></i> ${{l.label}}</a>`).join('')}}
      </div>
    </div>`;
  }}

  document.getElementById('modalBody').innerHTML = bodyHtml;
  document.getElementById('modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function renderGallery() {{
  const el = document.getElementById('modalGallery');
  if (!modalImgs.length) {{
    el.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:var(--surface-dim)"><i class="fa-solid fa-image" style="font-size:3rem;color:var(--text-dim);opacity:0.2"></i></div>';
    return;
  }}
  const img = modalImgs[modalImgIdx];
  let html = `<img src="${{img.p}}" alt="${{img.t || ''}}" style="width:100%;height:100%;object-fit:contain">`;
  if (modalImgs.length > 1) {{
    html += `<button class="modal-gallery-nav left" onclick="event.stopPropagation();galleryNav(-1)"><i class="fa-solid fa-chevron-left"></i></button>`;
    html += `<button class="modal-gallery-nav right" onclick="event.stopPropagation();galleryNav(1)"><i class="fa-solid fa-chevron-right"></i></button>`;
    html += `<div class="modal-gallery-counter">${{modalImgIdx + 1}} / ${{modalImgs.length}}</div>`;
  }}
  // Caption + source link
  let captionHtml = '';
  if (img.t) captionHtml += img.t;
  if (img.u) {{
    captionHtml += img.t ? ' ' : '';
    captionHtml += `<a href="${{img.u}}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="color:rgba(255,255,255,0.9);text-decoration:underline"><i class="fa-solid fa-arrow-up-right-from-square" style="font-size:9px"></i></a>`;
  }}
  if (img.li) captionHtml += `<span style="opacity:0.6;margin-left:6px;font-size:10px">${{img.li}}</span>`;
  if (captionHtml) {{
    html += `<div style="position:absolute;bottom:8px;left:12px;right:60px;font-size:12px;color:rgba(255,255,255,0.8);background:rgba(0,0,0,0.5);padding:4px 10px;border-radius:4px;backdrop-filter:blur(4px)">${{captionHtml}}</div>`;
  }}
  el.innerHTML = html;
}}

function galleryNav(dir) {{
  modalImgIdx = (modalImgIdx + dir + modalImgs.length) % modalImgs.length;
  renderGallery();
}}

function closeModal() {{
  document.getElementById('modal').classList.remove('open');
  document.body.style.overflow = '';
}}

// Keyboard
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') closeModal();
  if (document.getElementById('modal').classList.contains('open')) {{
    if (e.key === 'ArrowLeft') galleryNav(-1);
    if (e.key === 'ArrowRight') galleryNav(1);
  }}
}});

// ═══ MAP VIEW ═══
const LOCATIONS = [
  {{name:'尾鷲市街',lat:34.0699,lng:136.1930,kw:['尾鷲','尾鷲市','尾鷲港','尾鷲湾','尾鷲駅']}},
  {{name:'九鬼',lat:34.0438,lng:136.2205,kw:['九鬼','九鬼水軍','九鬼町']}},
  {{name:'馬越峠',lat:34.0872,lng:136.1784,kw:['馬越峠','馬越']}},
  {{name:'三木里',lat:34.0150,lng:136.1650,kw:['三木里','三木里ビーチ']}},
  {{name:'賀田',lat:34.0050,lng:136.1550,kw:['賀田','賀田湾']}},
  {{name:'弁財島',lat:34.0710,lng:136.2015,kw:['弁財島']}},
  {{name:'須賀利',lat:34.1150,lng:136.2350,kw:['須賀利']}},
  {{name:'梶賀',lat:33.9983,lng:136.1433,kw:['梶賀','あぶり']}},
  {{name:'曽根',lat:34.0033,lng:136.1383,kw:['曽根','白石湖','渡利牡蠣']}},
  {{name:'天狗倉山',lat:34.0833,lng:136.1750,kw:['天狗倉山','天狗倉']}},
  {{name:'便石山',lat:34.0750,lng:136.1650,kw:['便石山','象の背']}},
  {{name:'八鬼山',lat:34.0550,lng:136.1700,kw:['八鬼山']}},
  {{name:'向井',lat:34.0850,lng:136.1850,kw:['向井','向井地区']}},
  {{name:'三木浦',lat:34.0100,lng:136.1750,kw:['三木浦']}},
  {{name:'古江',lat:34.0067,lng:136.1600,kw:['古江']}},
  {{name:'早田',lat:34.0200,lng:136.1900,kw:['早田']}},
  {{name:'大曽根浦',lat:34.0600,lng:136.2050,kw:['大曽根浦']}},
  {{name:'行野浦',lat:34.0565,lng:136.2100,kw:['行野浦']}},
  {{name:'中村山',lat:34.0689,lng:136.1889,kw:['中村山']}},
  {{name:'熊野古道センター',lat:34.0725,lng:136.1870,kw:['熊野古道センター','夢古道']}},
];

let mapInstance = null;

function matchLocation(r) {{
  const hay = (r.t + ' ' + (r.tg||[]).join(' ')).toLowerCase();
  for (const loc of LOCATIONS) {{
    for (const kw of loc.kw) {{
      if (hay.includes(kw.toLowerCase())) return loc;
    }}
  }}
  return null;
}}

function renderMapView(el) {{
  document.getElementById('resultCount').textContent = '';

  el.innerHTML = `
    <div class="room-header" style="margin-top:0">
      <div class="room-icon" style="background:#5B7DB1"><i class="fa-solid fa-map-location-dot"></i></div>
      <div class="room-info"><h2>尾鷲マップ</h2><p>地名をクリックすると関連記事が表示されます</p></div>
    </div>
    <div style="position:relative">
      <div id="leafletMap" class="map-container"></div>
      <div class="map-sidebar" id="mapSidebar" style="display:none"></div>
    </div>
  `;

  // Destroy old map
  if (mapInstance) {{ mapInstance.remove(); mapInstance = null; }}

  // Create map
  const map = L.map('leafletMap', {{zoomControl: true}}).setView([34.05, 136.18], 12);
  mapInstance = map;

  // Tile layer
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18
  }}).addTo(map);

  // Group records by location
  const locGroups = {{}};
  DATA.forEach(r => {{
    const loc = matchLocation(r);
    if (loc) {{
      const key = loc.name;
      if (!locGroups[key]) locGroups[key] = {{loc, records: []}};
      locGroups[key].records.push(r);
    }}
  }});

  // Add markers
  const markers = [];
  Object.values(locGroups).forEach(g => {{
    const cnt = g.records.length;
    const marker = L.marker([g.loc.lat, g.loc.lng]).addTo(map);
    marker.bindTooltip(`${{g.loc.name}} (${{cnt}})`, {{direction: 'top', offset: [0, -8]}});
    marker.on('click', () => showMapSidebar(g.loc.name, g.records));
    markers.push(marker);
  }});

  // Fit bounds
  if (markers.length) {{
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
  }}

  // Show summary
  const totalMapped = Object.values(locGroups).reduce((s,g) => s + g.records.length, 0);
  const unmapped = DATA.length - totalMapped;
}}

function showMapSidebar(name, records) {{
  const sb = document.getElementById('mapSidebar');
  sb.style.display = 'block';

  let html = `<div class="map-sidebar-header"><i class="fa-solid fa-map-pin" style="color:var(--accent)"></i> ${{name}} <span style="font-weight:400;color:var(--text-dim);font-size:12px;margin-left:auto">${{records.length}}件</span></div>`;
  html += '<div class="map-sidebar-list">';
  records.slice(0, 20).forEach(r => {{
    const m = CAT_META[r.c] || {{n:'?',cl:'#888'}};
    const imgHtml = r.im.length ? `<img src="${{r.im[0].p}}" alt="">` : '';
    html += `<div class="map-sidebar-item" onclick="openModal('${{r.id}}')">
      ${{imgHtml}}
      <div class="map-sidebar-item-body">
        <div class="map-sidebar-item-title">${{r.t}}</div>
        <span class="map-sidebar-item-cat" style="background:${{m.cl}}">${{m.n}}</span>
      </div>
    </div>`;
  }});
  if (records.length > 20) {{
    html += `<div style="padding:10px 14px;font-size:12px;color:var(--text-dim);text-align:center">...他${{records.length - 20}}件</div>`;
  }}
  html += '</div>';
  sb.innerHTML = html;
}}

// ═══ CONCIERGE ═══
const KEYWORD_MAP = {{
  '食': ['food'], 'グルメ': ['food'], '食べ物': ['food'], 'ご飯': ['food'], '料理': ['food'],
  'ブリ': ['food','industry'], 'さんま': ['food'], 'ひもの': ['food'], '寿司': ['food'],
  'カツオ': ['food'], 'イセエビ': ['food'], '弁当': ['food'], 'めはり': ['food'],
  '自然': ['nature'], '森': ['nature'], '山': ['nature'], '木': ['nature','industry'],
  '海': ['nature','geography'], '花': ['nature'], '動物': ['nature'], '生態系': ['nature'],
  '歴史': ['history','archive'], '水軍': ['history'], '九鬼': ['history','culture'],
  '古道': ['history','tourism'], '熊野': ['history','tourism','nature'],
  '文化': ['culture'], '祭り': ['culture'], '祭': ['culture'], '民謡': ['culture'],
  '尾鷲節': ['culture'], 'わっぱ': ['culture','food'], '伝統': ['culture'],
  '観光': ['tourism'], 'スポット': ['tourism'], 'ビーチ': ['tourism'],
  '温泉': ['tourism'], 'トレッキング': ['tourism'], '絶景': ['tourism'],
  '産業': ['industry'], '漁業': ['industry'], '林業': ['industry'], '養殖': ['industry'],
  'ヒノキ': ['industry'], '深層水': ['industry','energy'],
  '防災': ['disaster','society'], '地震': ['disaster'], '津波': ['disaster'],
  '東南海': ['disaster','archive'], 'ハザード': ['disaster'],
  '教育': ['education'], '学校': ['education'], '授業': ['education'], '校外学習': ['education'],
  '人口': ['society'], 'まちづくり': ['society'], '過疎': ['society'], '移住': ['modern','society'],
  'エネルギー': ['energy'], '水力': ['energy'], '発電': ['energy'],
  '写真': ['archive'], 'アーカイブ': ['archive'],
  '子ども': ['education','tourism'], '小学生': ['education'],
}};

const PRESET_QUERIES = {{
  intro: {{
    q: '尾鷲の基本',
    answer: '尾鷲市は<strong>三重県南部</strong>の人口約1.6万人のまち。面積の90%が山林、年間降水量4,000mm（日本有数）、リアス式海岸に10の漁港。<strong>海と山と雨</strong>が織りなす、どこにもない風景があります。',
    cats: ['geography'],
    sort: 'id',
  }},
  food: {{
    q: '尾鷲のグルメ',
    answer: '尾鷲の食の主役は<strong>黒潮が運ぶ海の幸</strong>。ブリ・カツオ・さんま・イセエビ、そして漁師町の保存食「梶賀のあぶり」。山の幸では尾鷲わっぱに詰めるお弁当文化も。<strong>272件</strong>の食の記事からおすすめを紹介します。',
    cats: ['food'],
    sort: 'random',
  }},
  nature: {{
    q: '尾鷲の自然',
    answer: '市域の<strong>90%が山林</strong>。世界遺産・熊野古道の石畳、国指定天然記念物の暖地性シダ群落、黒潮が育む豊かな海。日本有数の多雨が生み出す<strong>緑のダム</strong>と清流。',
    cats: ['nature','geography'],
    sort: 'random',
  }},
  history: {{
    q: '尾鷲の歴史',
    answer: '縄文の貝塚から<strong>九鬼水軍</strong>の鉄甲船、世界遺産・<strong>熊野古道</strong>、400年続く尾鷲林業まで。小さなまちに千年の物語が詰まっています。',
    cats: ['history','archive'],
    sort: 'id',
  }},
  disaster: {{
    q: '尾鷲の防災',
    answer: '1944年の<strong>昭和東南海地震</strong>では津波が尾鷲を襲いました。南海トラフ地震の想定は津波最大17m・到達15分。<strong>過去に学び、未来に備える</strong>尾鷲の防災を紹介します。',
    cats: ['disaster','archive'],
    sort: 'id',
  }},
  kids: {{
    q: '子どもに見せたい',
    answer: '<strong>教科書に出てくるテーマ</strong>が尾鷲にはたくさん。リアス式海岸、林業、気候、熊野古道。校外学習や総合の時間で使える資料を集めました。',
    cats: ['education','tourism','nature','geography'],
    sort: 'edu',
  }},
  random: {{
    q: '今日のおすすめ',
    answer: '955件の中から<strong>今日のおすすめ</strong>をランダムに選びました。思わぬ発見があるかもしれません。',
    cats: null,
    sort: 'random',
  }},
}};

function askConcierge() {{
  const input = document.getElementById('conciergeInput');
  const q = input.value.trim();
  if (!q) return;
  showConciergeResponse(q);
}}

function askPreset(key) {{
  const preset = PRESET_QUERIES[key];
  if (!preset) return;
  const input = document.getElementById('conciergeInput');
  input.value = preset.q;
  showConciergeResponse(preset.q, preset);
}}

function showConciergeResponse(query, preset) {{
  const el = document.getElementById('conciergeResponse');

  // Show typing
  el.innerHTML = '<div class="concierge-response"><div class="concierge-typing"><span></span><span></span><span></span></div></div>';

  setTimeout(() => {{
    let results = [];
    let answerText = '';

    if (preset) {{
      answerText = preset.answer;
      if (preset.cats) {{
        results = DATA.filter(r => preset.cats.includes(r.c));
      }} else {{
        results = [...DATA];
      }}
      if (preset.sort === 'random') {{
        // Seeded by date for "today's" picks
        const seed = new Date().toDateString();
        results = shuffleSeeded(results, seed);
      }} else if (preset.sort === 'edu') {{
        results = results.filter(r => r.e).sort((a,b) => b.e.length - a.e.length);
      }}
    }} else {{
      // Free-form query: score records
      const scored = scoreRecords(query);
      results = scored.map(s => s.r);
      const topCats = getTopCats(scored.slice(0, 10));
      const n = scored.length;
      if (n === 0) {{
        answerText = `「${{query}}」に一致する記事は見つかりませんでした。別のキーワードで試してみてください。`;
      }} else if (n <= 5) {{
        answerText = `「<strong>${{query}}</strong>」に関連する記事が<strong>${{n}}件</strong>見つかりました。`;
      }} else {{
        answerText = `「<strong>${{query}}</strong>」に関連する記事が<strong>${{n}}件</strong>見つかりました。${{topCats}}の分野に多くヒットしています。`;
      }}
    }}

    const picks = results.slice(0, 6);
    let html = '<div class="concierge-response">';
    html += `<div class="concierge-answer">${{answerText}}</div>`;

    if (picks.length) {{
      html += '<div class="concierge-picks">';
      picks.forEach(r => {{
        const m = CAT_META[r.c] || {{n:'?',cl:'#888'}};
        const imgHtml = r.im.length ? `<img class="concierge-pick-img" src="${{r.im[0].p}}" alt="">` : `<div class="concierge-pick-img" style="display:flex;align-items:center;justify-content:center"><i class="${{m.i}}" style="color:var(--text-dim);opacity:0.3"></i></div>`;
        const excerpt = r.x.slice(0, 80) + (r.x.length > 80 ? '...' : '');
        html += `<div class="concierge-pick" onclick="openModal('${{r.id}}')">
          ${{imgHtml}}
          <div class="concierge-pick-body">
            <span class="concierge-pick-cat" style="background:${{m.cl}}">${{m.n}}</span>
            <div class="concierge-pick-title">${{r.t}}</div>
            <div class="concierge-pick-excerpt">${{excerpt}}</div>
          </div>
        </div>`;
      }});
      html += '</div>';
    }}

    if (results.length > 6) {{
      html += `<div style="text-align:center;margin-top:12px"><button onclick="searchFromConcierge()" style="padding:6px 18px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--accent);font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s" onmouseover="this.style.background='var(--accent-bg)'" onmouseout="this.style.background='var(--surface)'">${{results.length}}件すべて見る <i class="fa-solid fa-arrow-right" style="font-size:11px"></i></button></div>`;
    }}

    html += '</div>';
    el.innerHTML = html;
  }}, 600);
}}

function scoreRecords(query) {{
  const words = query.toLowerCase().split(/\\s+/).filter(w => w.length > 0);
  const catBoost = new Set();
  words.forEach(w => {{
    Object.entries(KEYWORD_MAP).forEach(([k, cats]) => {{
      if (w.includes(k.toLowerCase()) || k.toLowerCase().includes(w)) {{
        cats.forEach(c => catBoost.add(c));
      }}
    }});
  }});

  const scored = [];
  DATA.forEach(r => {{
    let score = 0;
    const hay = (r.t + ' ' + r.x + ' ' + (r.tg||[]).join(' ') + ' ' + r.e).toLowerCase();

    words.forEach(w => {{
      // Title match (high weight)
      if (r.t.toLowerCase().includes(w)) score += 10;
      // Tag match
      if ((r.tg||[]).some(t => t.toLowerCase().includes(w))) score += 7;
      // Content match
      const contentMatches = (hay.match(new RegExp(w.replace(/[.*+?^${{}}()|[\\]\\\\]/g,'\\\\$&'), 'gi')) || []).length;
      score += Math.min(contentMatches * 2, 10);
      // Edu use match
      if (r.e.toLowerCase().includes(w)) score += 3;
    }});

    // Category boost from keyword map
    if (catBoost.has(r.c)) score += 5;

    // Bonus for having images
    if (r.im.length > 0) score += 1;

    if (score > 0) scored.push({{r, score}});
  }});

  scored.sort((a,b) => b.score - a.score);
  return scored;
}}

function getTopCats(scored) {{
  const catCount = {{}};
  scored.forEach(s => catCount[s.r.c] = (catCount[s.r.c]||0) + 1);
  const top = Object.entries(catCount).sort((a,b) => b[1] - a[1]).slice(0, 2);
  return top.map(([c]) => `<strong>${{(CAT_META[c]||{{n:c}}).n}}</strong>`).join('・');
}}

function shuffleSeeded(arr, seed) {{
  const a = [...arr];
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = ((h << 5) - h + seed.charCodeAt(i)) | 0;
  for (let i = a.length - 1; i > 0; i--) {{
    h = (h * 16807 + 1) & 0x7fffffff;
    const j = h % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }}
  return a;
}}

function searchFromConcierge() {{
  const q = document.getElementById('conciergeInput').value.trim();
  if (q) {{
    document.getElementById('searchBox').value = q;
    handleSearch(q);
    window.scrollTo({{top: document.querySelector('.topbar').offsetTop, behavior: 'smooth'}});
  }}
}}

// ═══ LAZY LOAD ═══
function lazyLoad() {{
  const imgs = document.querySelectorAll('img[data-src]');
  const obs = new IntersectionObserver((entries) => {{
    entries.forEach(e => {{
      if (e.isIntersecting) {{
        e.target.src = e.target.dataset.src;
        e.target.removeAttribute('data-src');
        obs.unobserve(e.target);
      }}
    }});
  }}, {{rootMargin: '200px'}});
  imgs.forEach(img => obs.observe(img));
}}

// ═══ SCROLL TOP ═══
window.addEventListener('scroll', () => {{
  document.getElementById('scrollTop').classList.toggle('show', window.scrollY > 600);
}});

// ═══ INIT ═══
renderCatBar();
renderContent();
</script>
</body>
</html>'''

OUTPUT.write_text(html_out, encoding='utf-8')
print(f"Generated: {OUTPUT}")
print(f"  Records: {total} ({with_img} with images)")
print(f"  Images: {total_imgs}")
print(f"  Categories: {len(CAT_ORDER)}")
print(f"  History connections: {len(history_records)}")
print(f"  File size: {OUTPUT.stat().st_size / 1024:.0f} KB")
