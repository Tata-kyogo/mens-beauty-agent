"""
analyze_posts.py — Threads 投稿パフォーマンス定量分析

data/post_history.json の post_ids を使って Threads API から
like_count / reply_count を取得し、スコア・型・テーマ別に分析する。

score = like_count + (reply_count * 2)
刺さり率 = reply_count / like_count

出力: logs/analysis.txt
"""
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    import sys
    print("[ERROR] pip install requests が必要です", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
HISTORY_JSON_PATH = BASE_DIR / "data" / "post_history.json"
HISTORY_TXT_PATH = BASE_DIR / "data" / "post_history.txt"
ANALYSIS_PATH = BASE_DIR / "logs" / "analysis.txt"

THREADS_API_BASE = "https://graph.threads.net/v1.0"
API_SLEEP = 0.5  # API 連続呼び出し間のウェイト（秒）

POST_TYPES = ["観察", "分解", "断言", "予測"]

KEYWORD_GROUPS = {
    "ニキビ・肌荒れ": ["ニキビ", "肌荒れ", "ニキビ跡"],
    "毛穴":           ["毛穴", "黒ずみ", "脂浮き"],
    "青ヒゲ・脱毛":   ["青ヒゲ", "脱毛", "ひげ", "ヒゲ"],
    "AGA・薄毛":      ["AGA", "薄毛", "抜け毛"],
    "清潔感":         ["清潔感"],
    "減点回避":       ["減点", "不利回避", "損したくない", "マイナス"],
    "課金心理":       ["課金", "消費", "支出", "お金を払う"],
    "市場構造":       ["市場", "業界", "インフラ"],
    "スキンケア":     ["スキンケア", "保湿", "洗顔"],
}


# ------------------------------------------------------------------ #
#  データ読み込み
# ------------------------------------------------------------------ #

def load_history() -> list:
    if not HISTORY_JSON_PATH.exists():
        return []
    return json.loads(HISTORY_JSON_PATH.read_text(encoding="utf-8"))


def build_post_records(history: list) -> list:
    """
    post_history.json から個別投稿レコードのリストを作る。
    各レコード: {entry_topic, date, type, text, chars, post_id}
    post_id がない（未投稿）ものも含む。
    """
    records = []
    for entry in history:
        post_ids = entry.get("post_ids", [])
        for i, post in enumerate(entry.get("posts", [])):
            records.append({
                "topic":   entry["topic"],
                "date":    entry["date"],
                "type":    post["type"],
                "text":    post["text"],
                "chars":   post["chars"],
                "post_id": post_ids[i] if i < len(post_ids) else None,
            })
    return records


# ------------------------------------------------------------------ #
#  Threads API
# ------------------------------------------------------------------ #

def fetch_metrics(post_id: str, token: str) -> dict:
    """
    Threads API から like_count / reply_count を取得。
    取得できない場合は 0 を返す（クラッシュしない）。
    """
    try:
        resp = requests.get(
            f"{THREADS_API_BASE}/{post_id}",
            params={"fields": "like_count,replies_count", "access_token": token},
            timeout=15,
        )
        d = resp.json() if resp.ok else {}
    except requests.RequestException:
        d = {}

    return {
        "like_count":  int(d.get("like_count", 0)),
        "reply_count": int(d.get("replies_count", 0)),
    }


def fetch_all_metrics(records: list, token: str) -> dict:
    """post_id → metrics の辞書を返す"""
    result = {}
    targets = [r for r in records if r["post_id"]]
    print(f"  API 取得対象: {len(targets)}件")
    for i, rec in enumerate(targets, 1):
        pid = rec["post_id"]
        print(f"  [{i}/{len(targets)}] {rec['type']} / {rec['topic'][:25]}... ", end="", flush=True)
        m = fetch_metrics(pid, token)
        result[pid] = m
        print(f"like={m['like_count']}, reply={m['reply_count']}")
        time.sleep(API_SLEEP)
    return result


# ------------------------------------------------------------------ #
#  スコア計算
# ------------------------------------------------------------------ #

def calc_score(like: int, reply: int) -> int:
    return like + (reply * 2)


def engagement_rate(like: int, reply: int) -> str:
    if like == 0:
        return "—"
    return f"{reply / like * 100:.1f}%"


# ------------------------------------------------------------------ #
#  テーマ分類
# ------------------------------------------------------------------ #

def classify_topic(topic: str) -> list:
    matched = [g for g, kws in KEYWORD_GROUPS.items() if any(kw in topic for kw in kws)]
    return matched if matched else ["その他"]


# ------------------------------------------------------------------ #
#  集計
# ------------------------------------------------------------------ #

def aggregate(records: list, metrics_map: dict) -> dict:
    """型別・テーマ別の集計を返す"""
    by_type   = defaultdict(list)
    by_theme  = defaultdict(list)
    all_scored = []

    for rec in records:
        pid = rec["post_id"]
        if pid and pid in metrics_map:
            m = metrics_map[pid]
            score = calc_score(m["like_count"], m["reply_count"])
            rec["metrics"] = m
            rec["score"] = score
            rec["themes"] = classify_topic(rec["topic"])
            all_scored.append(rec)
            by_type[rec["type"]].append(score)
            for theme in rec["themes"]:
                by_theme[theme].append(score)

    type_avg  = {t: round(sum(v)/len(v), 1) for t, v in by_type.items() if v}
    theme_avg = {t: round(sum(v)/len(v), 1) for t, v in by_theme.items() if v}
    return {
        "all_scored": all_scored,
        "by_type":    type_avg,
        "by_theme":   theme_avg,
    }


# ------------------------------------------------------------------ #
#  次回提案
# ------------------------------------------------------------------ #

def suggest_next(agg: dict, history: list) -> dict:
    """スコアデータから次回テーマ3本・推奨型を提案"""
    all_scored = agg["all_scored"]
    type_avg   = agg["by_type"]
    theme_avg  = agg["by_theme"]

    used_topics = [e["topic"] for e in history]

    # 推奨型: 平均スコアが最も高い型
    best_type = max(type_avg, key=type_avg.get) if type_avg else "断言"
    # 補強型: 平均スコアが最も低い型（改善余地）
    weak_type = min(type_avg, key=type_avg.get) if type_avg else "観察"

    # スコアが高いテーマ領域
    top_themes = sorted(theme_avg, key=theme_avg.get, reverse=True)

    # 未使用のキーワードグループ
    covered = set()
    for e in history:
        covered.update(classify_topic(e["topic"]))
    unused_groups = [g for g in KEYWORD_GROUPS if g not in covered]

    suggestions = []

    # 提案1: スコアが高い型 × 未使用領域
    g1 = unused_groups[0] if unused_groups else (top_themes[0] if top_themes else "毛穴")
    kw1 = KEYWORD_GROUPS.get(g1, [""])[0]
    suggestions.append({
        "type": best_type,
        "theme": f"{kw1}への課金はなぜ「見た目改善」ではなく「不安の除去」として消費されるのか",
        "reason": (
            f"最高スコアの型【{best_type}】×「{g1}」（未使用）。"
            f"実績のある型で未開拓領域を攻める。"
        ),
    })

    # 提案2: 未使用領域 × コンプレックス解説
    g2 = unused_groups[1] if len(unused_groups) > 1 else (top_themes[1] if len(top_themes) > 1 else "青ヒゲ・脱毛")
    kw2 = KEYWORD_GROUPS.get(g2, [""])[0]
    suggestions.append({
        "type": "コンプレックス解説",
        "theme": f"{kw2}はなぜ20代男性の自己評価を静かに引き下げるのか",
        "reason": (
            f"「{g2}」領域が未使用。コンプレックス解説は共感を呼びやすく"
            f"リプライが発生しやすい型。"
        ),
    })

    # 提案3: 補強型（スコア低い型）× 強いテーマ
    g3 = top_themes[0] if top_themes else "減点回避"
    kw3 = KEYWORD_GROUPS.get(g3, [""])[0] if g3 in KEYWORD_GROUPS else g3
    suggestions.append({
        "type": weak_type,
        "theme": f"メンズ美容市場で{kw3}訴求が勝ち続ける構造的な理由",
        "reason": (
            f"【{weak_type}】の平均スコアが{type_avg.get(weak_type, 0)}点と低め。"
            f"高スコアテーマ「{g3}」で底上げを狙う。"
        ),
    })

    return {
        "suggestions": suggestions,
        "best_type":   best_type,
        "weak_type":   weak_type,
        "type_avg":    type_avg,
    }


# ------------------------------------------------------------------ #
#  レポート生成
# ------------------------------------------------------------------ #

def build_report(records: list, agg: dict, next_rec: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    w = lines.append

    w("=" * 52)
    w("投稿パフォーマンス分析レポート")
    w(f"生成日時: {ts}")
    w("=" * 52)

    all_scored = agg["all_scored"]
    unpublished = [r for r in records if not r["post_id"]]

    # ---- 基本統計 ----
    w("")
    w("【基本統計】")
    w(f"  総投稿数（取得済み）: {len(all_scored)}本")
    w(f"  未投稿・ID未取得:     {len(unpublished) + len([r for r in records if r['post_id'] and r.get('score') is None])}本")

    # ---- 投稿別スコア一覧 ----
    w("")
    w("【投稿別スコア一覧】")
    w(f"  {'日付':<12} {'型':<6} {'字数':>4}  {'Like':>5} {'Reply':>5} {'Score':>5}  {'刺さり率':>7}  テーマ")
    w("  " + "-" * 80)
    for rec in sorted(all_scored, key=lambda x: x["score"], reverse=True):
        m = rec["metrics"]
        eng = engagement_rate(m["like_count"], m["reply_count"])
        topic_short = rec["topic"][:30] + ("..." if len(rec["topic"]) > 30 else "")
        w(
            f"  {rec['date']:<12} 【{rec['type']}】 {rec['chars']:>4}字  "
            f"{m['like_count']:>5} {m['reply_count']:>5} {rec['score']:>5}点  {eng:>7}  {topic_short}"
        )

    # ---- TOP3 ----
    w("")
    w("【スコア TOP3】")
    top3 = sorted(all_scored, key=lambda x: x["score"], reverse=True)[:3]
    for i, rec in enumerate(top3, 1):
        m = rec["metrics"]
        w(f"  {i}位  【{rec['type']}】{rec['score']}点  (Like:{m['like_count']} / Reply:{m['reply_count']})")
        w(f"       {rec['topic'][:55]}")

    # ---- 型別平均スコア ----
    w("")
    w("【型別 平均スコア】")
    type_avg = agg["by_type"]
    for ptype in POST_TYPES:
        avg = type_avg.get(ptype)
        if avg is not None:
            bar = "█" * int(avg / 5)
            w(f"  {ptype:<6}  {avg:>5.1f}点  {bar}")
        else:
            w(f"  {ptype:<6}  データなし")

    # ---- テーマ別平均スコア ----
    w("")
    w("【テーマ別 平均スコア】")
    theme_avg = agg["by_theme"]
    for theme, avg in sorted(theme_avg.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(avg / 5)
        w(f"  {theme:<16}  {avg:>5.1f}点  {bar}")

    # ---- 刺さり率まとめ ----
    w("")
    w("【刺さり率（reply / like）】")
    w("  ※ リプライは能動的な関与。1%超で反応あり、5%超で強い共鳴の目安。")
    for rec in sorted(all_scored, key=lambda x: x["score"], reverse=True):
        m = rec["metrics"]
        eng = engagement_rate(m["like_count"], m["reply_count"])
        w(f"  【{rec['type']}】{rec['topic'][:30]}...  {eng}")

    # ---- 次回提案 ----
    w("")
    w("=" * 52)
    w("【次に使うべき型】")
    w("=" * 52)
    w(f"  最高スコア型: 【{next_rec['best_type']}】 平均{next_rec['type_avg'].get(next_rec['best_type'], 0)}点 → 引き続き優先")
    w(f"  要強化型:     【{next_rec['weak_type']}】 平均{next_rec['type_avg'].get(next_rec['weak_type'], 0)}点 → 1文目を短く改善")
    w("")
    w("=" * 52)
    w("【次に書くべきテーマ候補 3本】")
    w("=" * 52)
    for i, s in enumerate(next_rec["suggestions"], 1):
        w("")
        w(f"  候補{i}（{s['type']}）")
        w(f"  テーマ: {s['theme']}")
        w(f"  理由:   {s['reason']}")
    w("")

    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  メイン
# ------------------------------------------------------------------ #

def main():
    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    history = load_history()

    if not history:
        print("[INFO] data/post_history.json にデータがありません。")
        return

    records = build_post_records(history)
    published_count = sum(1 for r in records if r["post_id"])

    print(f"投稿レコード: {len(records)}本 / 投稿済み（ID有）: {published_count}本")

    # API 取得
    if not token or published_count == 0:
        if not token:
            print("[WARN] THREADS_ACCESS_TOKEN 未設定。ローカル分析のみ出力します。")
        _fallback_report(records, history)
        return

    print("Threads API からメトリクスを取得中...")
    metrics_map = fetch_all_metrics(records, token)

    agg = aggregate(records, metrics_map)
    next_rec = suggest_next(agg, history)
    report = build_report(records, agg, next_rec)

    ANALYSIS_PATH.parent.mkdir(exist_ok=True)
    ANALYSIS_PATH.write_text(report, encoding="utf-8")

    print("\n" + report)
    print(f"\n保存先: logs/analysis.txt")


def _fallback_report(records: list, history: list):
    """メトリクス未取得時の簡易レポート"""
    lines = [
        "=" * 52,
        "投稿分析レポート（メトリクス未取得）",
        f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 52,
        "",
        "【テーマ別カバレッジ】",
    ]
    from collections import Counter
    covered = Counter()
    for e in history:
        for g in classify_topic(e["topic"]):
            covered[g] += 1
    for g in KEYWORD_GROUPS:
        cnt = covered.get(g, 0)
        bar = "■" * cnt + "□" * max(0, 3 - cnt)
        lines.append(f"  {g:<20} {bar}  {cnt}件")
    lines += [
        "",
        "  → THREADS_ACCESS_TOKEN を設定して再実行するとスコア分析が有効になります。",
    ]
    report = "\n".join(lines)
    ANALYSIS_PATH.parent.mkdir(exist_ok=True)
    ANALYSIS_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n保存先: logs/analysis.txt")


if __name__ == "__main__":
    main()
