#!/usr/bin/env python3
"""X投稿のエンゲージメント指標を集計するスクリプト。

CSVまたはJSON形式の投稿データを読み込み、投稿ごとのエンゲージメント率と
全体統計（平均・中央値・最大/最小）、上位/下位投稿を計算してJSONで出力する。
"""

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

FIELD_ALIASES = {
    "text": ["text", "post", "content", "本文", "投稿"],
    "likes": ["likes", "like_count", "favorite_count", "いいね", "いいね数"],
    "reposts": ["reposts", "retweets", "retweet_count", "repost_count", "RT", "リポスト", "リポスト数"],
    "replies": ["replies", "reply_count", "返信", "返信数"],
    "impressions": ["impressions", "impression_count", "views", "view_count", "インプレッション", "インプレッション数"],
    "created_at": ["created_at", "timestamp", "date", "投稿日時"],
}


def normalize_row(raw_row):
    normalized = {}
    lower_map = {str(k).strip().lower(): v for k, v in raw_row.items()}
    for canonical, aliases in FIELD_ALIASES.items():
        value = None
        for alias in aliases:
            key = alias.lower()
            if key in lower_map and lower_map[key] not in (None, ""):
                value = lower_map[key]
                break
        normalized[canonical] = value
    return normalized


def to_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).replace(",", "").strip()
    if text == "":
        return None
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return None


def load_rows(input_path: Path):
    if input_path.suffix.lower() == ".json":
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("posts", data.get("data", []))
        return data
    with input_path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def analyze(rows, top_n):
    posts = []
    missing_impressions = 0

    for raw in rows:
        row = normalize_row(raw)
        likes = to_number(row.get("likes")) or 0
        reposts = to_number(row.get("reposts")) or 0
        replies = to_number(row.get("replies")) or 0
        impressions = to_number(row.get("impressions"))

        engagement_total = likes + reposts + replies
        engagement_rate = None
        if impressions:
            engagement_rate = round(engagement_total / impressions, 6)
        else:
            missing_impressions += 1

        posts.append({
            "text": row.get("text"),
            "likes": likes,
            "reposts": reposts,
            "replies": replies,
            "impressions": impressions,
            "created_at": row.get("created_at"),
            "engagement_total": engagement_total,
            "engagement_rate": engagement_rate,
        })

    rates = [p["engagement_rate"] for p in posts if p["engagement_rate"] is not None]
    totals = [p["engagement_total"] for p in posts]

    summary = {
        "post_count": len(posts),
        "posts_missing_impressions": missing_impressions,
        "engagement_total_mean": round(statistics.mean(totals), 3) if totals else None,
        "engagement_total_median": statistics.median(totals) if totals else None,
        "engagement_rate_mean": round(statistics.mean(rates), 6) if rates else None,
        "engagement_rate_median": round(statistics.median(rates), 6) if rates else None,
    }

    ranked_by_rate = [p for p in posts if p["engagement_rate"] is not None]
    ranked_by_rate.sort(key=lambda p: p["engagement_rate"], reverse=True)
    ranked_by_total = sorted(posts, key=lambda p: p["engagement_total"], reverse=True)

    top_key = "top_posts_by_rate" if ranked_by_rate else "top_posts_by_total"
    top_source = ranked_by_rate if ranked_by_rate else ranked_by_total

    return {
        "summary": summary,
        "posts": posts,
        top_key: top_source[:top_n],
        "bottom_posts": (ranked_by_rate if ranked_by_rate else ranked_by_total)[-top_n:][::-1],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSVまたはJSON形式の投稿データファイル")
    parser.add_argument("--top", type=int, default=5, help="上位/下位に表示する投稿数（デフォルト5）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        rows = load_rows(input_path)
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("エラー: 投稿データが空です。", file=sys.stderr)
        sys.exit(1)

    result = analyze(rows, args.top)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
