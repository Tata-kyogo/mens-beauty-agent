"""
research.py — Claude CLI によるテーマ自動生成・採用

毎回5候補を生成し、最適な1本を自動採用する。

保存先:
  data/topic_candidates.txt  候補5本 + 採用マーカー
  data/topic.txt             採用テーマ（write_posts.py が読む）
  data/topic_reason.txt      採用理由の追記ログ（見返し用）
  data/topics_used.txt       使用済みテーマ一覧（重複回避用）
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOPICS_BANK_PATH = BASE_DIR / "data" / "topics_bank.txt"
TOPICS_USED_PATH = BASE_DIR / "data" / "topics_used.txt"
TOPIC_PATH = BASE_DIR / "data" / "topic.txt"
CANDIDATES_PATH = BASE_DIR / "data" / "topic_candidates.txt"
REASON_PATH = BASE_DIR / "data" / "topic_reason.txt"
HISTORY_PATH = BASE_DIR / "data" / "post_history.json"
LOG_PATH = BASE_DIR / "logs" / "run.log"


def load_lines(path: Path) -> list:
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_used_topics() -> list:
    """topics_used.txt + post_history.json から使用済みテーマを収集"""
    used = load_lines(TOPICS_USED_PATH)
    if HISTORY_PATH.exists():
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        for entry in history:
            t = entry.get("topic", "")
            if t and t not in used:
                used.append(t)
    return used


def build_prompt(used_topics: list, seed_topics: list) -> str:
    used_section = (
        "\n".join(f"- {t}" for t in used_topics[-15:])
        if used_topics
        else "（まだ使用済みテーマはありません）"
    )
    seed_section = "\n".join(f"- {t}" for t in seed_topics) if seed_topics else ""

    return f"""あなたはメンズ美容市場アカウントのテーマ設計担当です。

【条件】
- 対象読者: 20代男性の課金心理・清潔感・不利回避・見た目コンプレックス消費に関心があるアカウント
- テーマは「論点の形」にする（単語・タイトルではなく、疑問や命題の文）
  良い例: 「青ヒゲはなぜ20代男性にとって課金対象になりやすいのか」
  悪い例: 「青ヒゲについて」「メンズ脱毛の現状」
- 以下4つの型をバランスよく混ぜる
  1. 課金心理: なぜお金を払うのか、課金の動機・心理を掘る
  2. コンプレックス解説: 悩みの正体・不利回避・自己評価への影響
  3. 市場構造: 業界・サービス・消費行動の構造を観察する
  4. 今後の予測: インフラ化・当たり前化・市場の変化方向
- テーマは具体的な論点があるものにする（抽象的すぎるテーマは不可）
- 過去と重複・類似するテーマは避ける

【使用済みテーマ（避けること）】
{used_section}

【優先的に扱いたいキーワード】
青ヒゲ、毛穴、ニキビ跡、AGA、清潔感、減点回避、メンズ美容市場の変化、20代男性の消費行動

【参考テーマ例（発想の起点として）】
{seed_section}

---

5本の候補テーマを提案し、最も論点が鋭い1本を採用してください。

出力形式（必ずこの通りに出力してください）:

【候補1】（課金心理）テーマ文
【候補2】（コンプレックス解説）テーマ文
【候補3】（市場構造）テーマ文
【候補4】（今後の予測）テーマ文
【候補5】（課金心理またはコンプレックス解説または市場構造または今後の予測）テーマ文

【採用】候補X
【理由】採用理由を1〜2行で記述（過去テーマとの差別化ポイントも含めること）"""


def parse_candidates(raw: str) -> list:
    """[(番号, タイプ, テーマ文), ...]"""
    candidates = []
    pattern = r"【候補(\d+)】（(.+?)）(.+)"
    for m in re.finditer(pattern, raw):
        candidates.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
    return candidates


def parse_selection(raw: str) -> tuple:
    """(採用番号, 理由文)"""
    sel = re.search(r"【採用】候補(\d+)", raw)
    reason = re.search(r"【理由】([\s\S]+?)(?=【|\Z)", raw)
    sel_num = int(sel.group(1)) if sel else None
    reason_text = reason.group(1).strip() if reason else ""
    return sel_num, reason_text


def main():
    seed_topics = load_lines(TOPICS_BANK_PATH)
    used_topics = load_used_topics()

    print("テーマ候補を生成中（Claude CLI）...")
    try:
        result = subprocess.run(
            ["claude", "-p", build_prompt(used_topics, seed_topics)],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Claude CLI 呼び出し失敗:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

    raw = result.stdout.strip()
    candidates = parse_candidates(raw)
    sel_num, reason = parse_selection(raw)

    if not candidates:
        print("[ERROR] 候補テーマをパースできませんでした。Claude の出力:", file=sys.stderr)
        print(raw, file=sys.stderr)
        sys.exit(1)

    # 採用テーマを特定（パース失敗時は候補1にフォールバック）
    selected = next((c for c in candidates if c[0] == sel_num), candidates[0])
    sel_num, sel_type, sel_topic = selected

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    CANDIDATES_PATH.parent.mkdir(exist_ok=True)

    # data/topic_candidates.txt（上書き: 最新候補のみ残す）
    with CANDIDATES_PATH.open("w", encoding="utf-8") as f:
        f.write(f"生成日時: {timestamp}\n\n")
        for num, t_type, t_text in candidates:
            marker = " ← 採用" if num == sel_num else ""
            f.write(f"【候補{num}】（{t_type}）{t_text}{marker}\n")
        f.write(f"\n【採用】候補{sel_num}：{sel_topic}\n")
        f.write(f"【理由】{reason}\n")

    # data/topic.txt（write_posts.py が読む）
    TOPIC_PATH.write_text(sel_topic + "\n", encoding="utf-8")

    # data/topic_reason.txt（追記: 見返し用ログ）
    with REASON_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]\n")
        f.write(f"採用: 【候補{sel_num}】（{sel_type}）{sel_topic}\n")
        f.write(f"理由: {reason}\n\n")

    # data/topics_used.txt（追記: 重複回避用）
    with TOPICS_USED_PATH.open("a", encoding="utf-8") as f:
        f.write(sel_topic + "\n")

    # logs/run.log
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [research] 採用: {sel_topic}\n")

    # ターミナル表示
    print(f"\n{'='*45}")
    print("テーマ候補:")
    for num, t_type, t_text in candidates:
        marker = " ← 採用" if num == sel_num else ""
        print(f"  候補{num}（{t_type}）: {t_text}{marker}")
    print(f"\n採用テーマ: {sel_topic}")
    print(f"採用理由: {reason}")
    print(f"{'='*45}")


if __name__ == "__main__":
    main()
