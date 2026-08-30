#!/usr/bin/env python3
"""Generate one blog post about used industrial plant equipment and write it to _posts/."""

import datetime
import json
import os
import re
import sys
import uuid
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "_posts"
TOPICS_LOG = ROOT / "_data" / "topics-log.json"
MODEL = "claude-sonnet-5"
RECENT_TITLES_LIMIT = 30

TITLE_RE = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)
SLUG_RE = re.compile(r'^slug:\s*["\']?([a-z0-9-]+)["\']?\s*$', re.MULTILINE)

TOPIC_ANGLES = [
    "中古設備の選び方・見極め方ガイド",
    "メンテナンス・整備のノウハウ",
    "業界動向・市場トレンド解説",
    "関連法規制（古物営業法など）の解説",
    "実際の活用事例・導入事例（架空の一般化されたケース）",
    "設備の種類・工法の比較記事",
    "コスト削減・中古活用のメリット解説",
    "設備の安全対策・点検ポイント",
]

SYSTEM_PROMPT = """あなたは中古産業機械・プラント設備の専門ブログを書いている、このブログの管理人本人です。

## あなたの人物設定
- プラント設備工事会社「ausus」で20年以上、機械設計・据付、配管工事、デッキ・階段等の設備新設/修繕の現場に携わってきた現役の実務者
- 一人称は「私」。企業広報のような客観的・他人事の書き方ではなく、自分の現場経験を踏まえた一人称の語り口で書く（例:「私がこれまで現場で見てきた中では〜」「実際に扱った案件でも〜」といった言い回しを自然に織り交ぜる。ただし特定の顧客名・案件名など裏付けのない具体的固有情報は創作しない）
- 想定読者: 中古の産業機械・プラント設備（機械、配管、デッキ、階段等）の購入・売却を検討している工事会社・製造業の設備担当者
- トーン: 専門的だが平易で分かりやすい。誇張や断定的な法律・financial助言は避け、必要に応じて「専門家に確認を」と促す
- 目的: SEOを意識した、検索から辿り着いた読者の役に立つ実用的な記事

## 出力形式（厳守）
Markdown全文のみを出力すること。前置き・後書き・コードフェンスは一切不要。
必ず以下の形式のYAML front matterから始めること:

---
title: "記事タイトル"
date: YYYY-MM-DD 07:00:00 +0900
description: "120字以内の要約（メタディスクリプション用）"
tags: [タグ1, タグ2, タグ3]
slug: "半角英数とハイフンのみのASCIIスラッグ"
---

本文はfront matterの後に続けて書くこと。本文は800〜1400字程度の日本語、見出し(##)を2〜4個使って構造化すること。
"""


def load_recent_titles(limit: int) -> list[str]:
    titles = []
    if not POSTS_DIR.exists():
        return titles
    files = sorted(POSTS_DIR.glob("*.md"), reverse=True)[:limit]
    for f in files:
        text = f.read_text(encoding="utf-8")
        m = TITLE_RE.search(text)
        if m:
            titles.append(m.group(1))
    return titles


def build_user_prompt(recent_titles: list[str]) -> str:
    today = datetime.date.today().isoformat()
    angles = "\n".join(f"- {a}" for a in TOPIC_ANGLES)
    avoided = "\n".join(f"- {t}" for t in recent_titles) if recent_titles else "（まだ投稿なし）"
    return f"""今日（{today}）の記事を1本書いてください。

## 切り口の例（このいずれか、または近い切り口から選ぶ）
{angles}

## 既に投稿済みのタイトル（内容が重複しないようにすること）
{avoided}

上記と話題が被らない、具体的で読者の役に立つ記事を1本、指定のfront matter形式で出力してください。
"""


def extract_slug(markdown: str) -> str:
    m = SLUG_RE.search(markdown)
    if m:
        return m.group(1)
    return f"post-{uuid.uuid4().hex[:8]}"


def append_topics_log(title: str, date: str) -> None:
    TOPICS_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if TOPICS_LOG.exists():
        log = json.loads(TOPICS_LOG.read_text(encoding="utf-8"))
    log.append({"date": date, "title": title})
    TOPICS_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    recent_titles = load_recent_titles(RECENT_TITLES_LIMIT)
    user_prompt = build_user_prompt(recent_titles)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    markdown = "".join(b.text for b in response.content if b.type == "text").strip()

    if not markdown.startswith("---"):
        print("ERROR: model output did not start with front matter:\n" + markdown[:500], file=sys.stderr)
        sys.exit(1)

    title_match = TITLE_RE.search(markdown)
    title = title_match.group(1) if title_match else "無題"
    slug = extract_slug(markdown)
    today = datetime.date.today().isoformat()

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = POSTS_DIR / f"{today}-{slug}.md"
    out_path.write_text(markdown + "\n", encoding="utf-8")

    append_topics_log(title, today)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
