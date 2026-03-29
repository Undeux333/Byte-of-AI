# Global News Twitter Bot

完全自動・ランニングコストゼロのTwitter（X）ボット。

## 構成

```
twitter_bot/
├── .github/workflows/bot.yml  ← GitHub Actionsの自動実行設定
├── data/state.json            ← 状態管理（自動コミット）
├── config.py                  ← 全設定
├── state_manager.py           ← 状態の読み書き
├── fetchers.py                ← ニュース収集（RSS/Reddit/HN）
├── scorer.py                  ← Geminiでスコアリング＋ツイート生成
├── image_gen.py               ← Pillowで解説カード画像生成
├── poster.py                  ← X APIで投稿
├── main.py                    ← メインパイプライン
└── requirements.txt
```

## セットアップ手順

### 1. GitHubアカウント作成・リポジトリ作成

1. [github.com](https://github.com) でアカウント作成（無料）
2. 右上「+」→「New repository」
3. Repository name: `twitter-bot`（任意）
4. **Public** を選択（Actions無制限のため）
5. 「Create repository」

### 2. コードをGitHubにアップロード

ターミナルで：
```bash
cd twitter_bot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/あなたのユーザー名/twitter-bot.git
git push -u origin main
```

### 3. GitHub SecretsにAPIキーを登録

GitHubのリポジトリページ →「Settings」→「Secrets and variables」→「Actions」→「New repository secret」

以下の5つを登録：

| Name | Value |
|------|-------|
| `GEMINI_API_KEY` | GeminiのAPIキー |
| `TWITTER_API_KEY` | TwitterのAPI Key |
| `TWITTER_API_SECRET` | TwitterのAPI Key Secret |
| `TWITTER_ACCESS_TOKEN` | TwitterのAccess Token |
| `TWITTER_ACCESS_TOKEN_SECRET` | TwitterのAccess Token Secret |

### 4. 手動で動作確認

GitHubリポジトリ →「Actions」タブ →「Twitter Bot」→「Run workflow」→「Run workflow」

ログを確認してエラーがなければ完了。

### 5. 以後は放置

毎時0分に自動実行。2時間ごとにニュース収集、毎時投稿。

## 動作フロー

```
毎時0分 GitHub Actions起動
    ↓
state.jsonを読み込み
    ↓
2時間経過？ → Yes → RSS/Reddit/HNから収集 → Geminiでスコアリング → キューに追加
    ↓
キューから1件取り出す
    ↓
Pillowで解説カード画像を生成
    ↓
本投稿（画像付き、100文字以内）
    ↓
引用リツイート（ユーモア/意見、100文字以内）
    ↓
state.jsonを更新してGitHubにコミット
```

## 投稿形式

**本投稿**（画像付き）
```
[100文字以内のパンチのある要約]
[解説カード画像]
```

**引用リツイート（サブ投稿）**
```
[100文字以内のユーモア/ホットテイク/アドバイス]
[本投稿のURL]
```

## コスト

| サービス | 使用量 | 無料枠 | コスト |
|---------|--------|--------|--------|
| GitHub Actions | ~15分/日 | 無制限（Public repo） | 無料 |
| Gemini API | ~400 req/日 | 1,500 req/日 | 無料 |
| X API | ~48 tweets/日 | 1,500 tweets/月 | 無料 |
| 画像生成（Pillow） | 毎投稿 | 無制限 | 無料 |

## ローカルテスト

```bash
pip install -r requirements.txt
cp .env.example .env
# .envにAPIキーを入力

# テスト実行（投稿なし）
python main.py --dry-run

# 本番実行
python main.py
```
