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
CATEGORY_RE = re.compile(r'^category:\s*["\']?([a-z-]+)["\']?\s*$', re.MULTILINE)

CATEGORY_IMAGES = {
    "compressor": ("compressor.svg", "コンプレッサーのイメージ図"),
    "gearbox": ("gearbox.svg", "減速機のイメージ図"),
    "piping": ("piping.svg", "配管設備のイメージ図"),
    "used-equipment-check": ("used-equipment-check.svg", "中古設備チェックのイメージ図"),
    "maintenance": ("maintenance.svg", "メンテナンス作業のイメージ図"),
    "industry-trend": ("industry-trend.svg", "業界動向のイメージ図"),
    "regulation": ("regulation.svg", "法規制・許認可のイメージ図"),
    "safety": ("safety.svg", "安全対策のイメージ図"),
}
DEFAULT_IMAGE = ("used-equipment-check.svg", "中古産業機械・プラント設備のイメージ図")

TOPIC_ANGLES = [
    "コンプレッサーの種類と選び方（往復式・スクリュー式・ターボ式などの構造・特徴比較）",
    "減速機の種類と選び方（歯車減速機・ウォーム減速機・遊星減速機などの構造・特徴比較）",
    "配管工事で気をつけるべきポイント（材質選定、耐圧・耐熱、腐食対策、施工上の注意点）",
    "蒸気配管特有の注意点（ドレン処理、保温、熱伸縮対策、ウォーターハンマー対策など）",
    "中古機械の状態確認・見極めポイント（実務者が現物を見る際のチェック項目）",
    "メンテナンス・整備のノウハウ",
    "業界動向・市場トレンド解説",
    "関連法規制（古物営業法など）の解説",
    "設備の安全対策・点検ポイント",
]

SYSTEM_PROMPT = """あなたは中古産業機械・プラント設備の専門ブログを書いている、このブログの管理人本人です。

## あなたの人物設定
- プラント設備工事会社「ausus」で10年以上、機械設計・据付、配管工事、デッキ・階段等の設備新設/修繕の現場に携わってきた現役の実務者
- 一人称は「私」。企業広報のような客観的・他人事の書き方ではなく、自分の現場経験を踏まえた一人称の語り口で書く（例:「私がこれまで現場で見てきた中では〜」「実際に扱った案件でも〜」といった言い回しを自然に織り交ぜる。ただし特定の顧客名・案件名など裏付けのない具体的固有情報は創作しない）
- **架空の発注パターン・案件を「実際にあった話」として書かない。** 特に、当社が実際には扱っていない・現実的でない業務（例: 中古のデッキ・階段を"取り付ける"発注のような、実務上まず発生しないケース）を、あたかも日常的に経験しているかのように書くと、読者の信頼を損なう。案件の具体エピソードには踏み込まず、機器の構造・種類・選定基準・施工上の注意点・保守のポイントなど、一般的な技術解説として実務経験に基づく知見を語ること
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
category: "内容に最も近いものを1つだけ選ぶ（この8つの中から必ず選ぶこと。英字そのまま）: compressor / gearbox / piping / used-equipment-check / maintenance / industry-trend / regulation / safety"
slug: "半角英数とハイフンのみのASCIIスラッグ"
---

本文はfront matterの後に続けて書くこと。本文は800〜1400字程度の日本語、見出し(##)を2〜4個使って構造化し、最後に必ず「## まとめ」という見出しをつけて3〜4文程度でこの記事の要点をまとめること。
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


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def extract_slug(markdown: str) -> str:
    m = SLUG_RE.search(markdown)
    if m:
        return m.group(1)
    return f"post-{uuid.uuid4().hex[:8]}"


def insert_image(markdown: str) -> str:
    m = CATEGORY_RE.search(markdown)
    category = m.group(1) if m else None
    filename, alt = CATEGORY_IMAGES.get(category, DEFAULT_IMAGE)
    image_md = f"![{alt}]({{{{ site.baseurl }}}}/assets/images/{filename})"

    parts = markdown.split("---", 2)
    if len(parts) != 3:
        return markdown
    front_matter, body = parts[1], parts[2].lstrip("\n")
    return f"---{front_matter}---\n\n{image_md}\n\n{body}"


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
    markdown = strip_code_fence(markdown)

    if not markdown.startswith("---"):
        print("ERROR: model output did not start with front matter:\n" + markdown[:500], file=sys.stderr)
        sys.exit(1)

    markdown = insert_image(markdown)

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
