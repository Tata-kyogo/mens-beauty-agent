# mens-beauty-agent

メンズ美容市場アカウントの Threads 運用自動化エージェント。
20代男性の課金心理・清潔感・不利回避・見た目コンプレックス消費をテーマに、1テーマ4本の投稿を自動生成・投稿準備する。

---

## ファイル構成

```
mens-beauty-agent/
├── generate.sh            # メイン実行スクリプト（これを叩く）
├── research.py            # テーマ候補の管理とローテーション
├── write_posts.py         # 1テーマから4本生成（Claude CLI 使用）
├── quality_check.py       # 文字数・硬さ・類似度チェック
├── publish_threads.py     # Threads API への投稿
├── analyze_posts.py       # 反応分析スケルトン（将来実装）
├── main.py                # 旧版（参照用、現在は非推奨）
├── requirements.txt
├── .env                   # 認証情報（git管理外）
├── .env.example           # 認証情報テンプレート
├── prompts/
│   └── system.txt         # Claude へのシステムプロンプト
├── data/
│   ├── topics_bank.txt       # テーマ発想の参考例リスト（Claude が参照）
│   ├── topics_used.txt       # 使用済みテーマ（自動更新・重複回避用）
│   ├── topic.txt             # 今回の採用テーマ（自動更新）
│   ├── topic_candidates.txt  # テーマ候補5本 + 採用マーカー（最新のみ）
│   ├── topic_reason.txt      # 採用理由の追記ログ（見返し用）
│   ├── output.txt            # 生成済み投稿（自動更新）
│   ├── post_history.json     # 投稿履歴・JSON（品質チェック等が参照）
│   └── post_history.txt      # 投稿履歴・人間可読ログ（見返し用）
└── logs/
    ├── run.log            # 実行ログ
    └── post.log           # 投稿ログ
```

---

## セットアップ

### 1. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. Claude CLI の確認

```bash
claude --version
```

インストールされていない場合は [Claude Code](https://claude.ai/code) を参照。

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集して Threads のトークンを設定:

```
THREADS_ACCESS_TOKEN=your_token_here
THREADS_USER_ID=your_user_id_here
```

> トークン未設定の場合、投稿ステップは自動スキップされる（生成・保存は実行される）。

### 4. generate.sh に実行権限を付与

```bash
chmod +x generate.sh
```

---

## 実行

### 通常実行（生成 + 品質チェック + 投稿）

```bash
bash generate.sh
```

### 個別実行

```bash
python3 research.py        # テーマ選定のみ
python3 write_posts.py     # 生成のみ
python3 quality_check.py   # 品質チェックのみ
python3 publish_threads.py # 投稿のみ（.env 設定済みの場合）
python3 analyze_posts.py   # 履歴サマリー表示
```

---

## テーマ自動選定

`research.py` が Claude CLI を使い、毎回5候補を生成して1本を自動採用する。

### 選定フロー

```
1. data/topics_used.txt + post_history.json から使用済みテーマを収集
2. data/topics_bank.txt の参考例リストを発想の起点として渡す
3. Claude が4型（課金心理 / コンプレックス解説 / 市場構造 / 今後の予測）
   をバランスよく含む5候補を生成
4. 論点が最も鋭い1本を自動採用 → topic.txt に書き出す
```

### 出力ファイル

| ファイル | 内容 |
|---------|------|
| `data/topic_candidates.txt` | 候補5本 + 採用マーカー（毎回上書き）|
| `data/topic.txt` | 採用テーマ（write_posts.py が読む）|
| `data/topic_reason.txt` | 採用理由の追記ログ（見返し用）|

### テーマのルール

- **論点の形にする**（単語・タイトルではなく疑問・命題）
  - NG: 「青ヒゲ」「メンズ脱毛の現状」
  - OK: 「青ヒゲはなぜ20代男性にとって課金対象になりやすいのか」
- **4型のバランスを保つ**: 課金心理 / コンプレックス解説 / 市場構造 / 今後の予測
- **抽象的すぎるテーマは採用しない**
- **直近15件の使用テーマとの重複を避ける**

### 参考例の追加

`data/topics_bank.txt` に1行1テーマで追記すると、次回から Claude の発想に反映される。

```
# 例
AGAはなぜ20代男性の自己評価に直結するのか
```

---

## 投稿仕様

| 項目 | 内容 |
|------|------|
| 本数 | 4本（観察 / 分解 / 断言 / 予測） |
| 文字数 | 100〜150字目安 |
| トーン | 業界観察者・冷静・断言気味 |
| 絵文字 | なし |
| ハッシュタグ | なし |

---

## Threads API トークン取得

1. [Meta Developer Portal](https://developers.facebook.com/) でアプリ作成
2. Threads API の権限を追加
3. アクセストークンと User ID を取得して `.env` に設定

---

## ログ

- `logs/run.log` — 実行履歴（テーマ選定・生成・投稿）
- `logs/post.log` — Threads 投稿の成功・失敗記録
- `data/post_history.json` — 投稿履歴 JSON（published フラグ・post_ids 含む）
- `data/post_history.txt` — 投稿履歴 テキスト（人間が見返すためのログ）
- `data/topic_reason.txt` — テーマ採用理由の追記ログ
