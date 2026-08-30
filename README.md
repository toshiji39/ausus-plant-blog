# 中古プラント設備・機械の教科書

中古産業機械・プラント設備に関する専門ブログ。GitHub Pages（Jekyll）でホスティングし、GitHub Actions + Claude APIで毎日1本、自動で記事を生成・公開する。

## 仕組み

- `_posts/` に記事(Markdown)が溜まっていく
- `.github/workflows/daily-post.yml` が毎日07:00(JST)に `scripts/generate_post.py` を実行し、新しい記事を1本生成してpushする
- GitHub PagesがJekyllの標準プラグイン（jekyll-seo-tag, jekyll-sitemap, jekyll-feed）でビルド・公開する

## セットアップ（初回のみ・手動）

1. [console.anthropic.com](https://console.anthropic.com) でAPIキーを発行し、支払い方法を登録する
2. このリポジトリにSecretを登録する（キーはターミナルで直接入力し、チャット等には貼らないこと）
   ```bash
   gh secret set ANTHROPIC_API_KEY --repo <owner>/<repo>
   ```
3. GitHubリポジトリのSettings → Pages で、`main`ブランチ / `/(root)` からの配信を有効化する
4. 動作確認: `gh workflow run daily-post.yml` で手動実行し、Actionsのログとリポジトリへのコミットを確認する

## ローカルでの記事生成テスト

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install -r scripts/requirements.txt
python scripts/generate_post.py
```

## ローカルプレビュー（要Ruby/Bundler）

```bash
bundle install
bundle exec jekyll serve
```
