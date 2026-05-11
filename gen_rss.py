#!/usr/bin/env python3
"""
gen_rss.py - Generate RSS 2.0 + iTunes namespace feed XML for one or more podcast shows.

Reads:
  shows/{show_id}/show.yaml      — show-level metadata
  shows/{show_id}/cover.jpg      — show cover (1400×1400)
  shows/{show_id}/episodes/*.mp3 — audio files
  shows/{show_id}/episodes/*.yaml — episode-level metadata

Writes:
  shows/{show_id}/feed.xml       — RSS feed consumed by Spotify/Apple/Amazon

Spec compliance:
  - RSS 2.0 (https://cyber.harvard.edu/rss/rss.html)
  - iTunes Podcasters Connect tags (https://help.apple.com/itc/podcasts_connect/)
  - Spotify Podcasters supported tags (https://podcasters.spotify.com/support/article/360032287692)

Usage:
  python3 gen_rss.py [--show SHOW_ID | --all]
  python3 gen_rss.py --all --base-url https://uxth.github.io/podcast-feed

Author: dingqing1981 enterprise pipeline
"""
import argparse
import datetime as dt
import os
import sys
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).parent.resolve()
SHOWS_DIR = ROOT / "shows"

# Default base URL (will be overridden by --base-url or env)
DEFAULT_BASE_URL = "https://uxth.github.io/podcast-feed"


def ffprobe_duration(mp3_path: Path) -> int:
    """Return mp3 duration in seconds (int). Falls back to yaml-declared value if ffprobe unavailable."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3_path)],
            capture_output=True, text=True, timeout=10,
        )
        return int(float(result.stdout.strip()))
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return 0


def format_pub_date(iso_str: str) -> str:
    """ISO 8601 → RFC 822 (RSS spec requires this format)."""
    if isinstance(iso_str, dt.datetime):
        dt_obj = iso_str
    else:
        s = str(iso_str).replace("Z", "+00:00")
        dt_obj = dt.datetime.fromisoformat(s)
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return dt_obj.strftime("%a, %d %b %Y %H:%M:%S +0000")


def format_duration_hhmmss(seconds: int) -> str:
    """Seconds → HH:MM:SS for iTunes."""
    if seconds <= 0:
        return "0:00"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def gen_feed(show_dir: Path, base_url: str) -> str:
    """Generate full RSS XML for one show."""
    show_yaml = yaml.safe_load((show_dir / "show.yaml").read_text(encoding="utf-8"))
    show_id = show_yaml["show_id"]
    show_url = f"{base_url}/shows/{show_id}"
    cover_url = f"{show_url}/{show_yaml.get('cover_image', 'cover.jpg')}"

    # Collect episodes
    ep_files = sorted((show_dir / "episodes").glob("*.yaml"))
    episodes = []
    for ep_yaml_path in ep_files:
        ep = yaml.safe_load(ep_yaml_path.read_text(encoding="utf-8"))
        mp3_path = show_dir / "episodes" / ep.get("audio_file", f"{ep['episode_id']}.mp3")
        if not mp3_path.exists():
            print(f"⚠️  skip {ep['episode_id']}: mp3 not found {mp3_path}", file=sys.stderr)
            continue
        ep["__mp3_path"] = mp3_path
        ep["__mp3_size"] = mp3_path.stat().st_size
        if not ep.get("duration_seconds"):
            ep["duration_seconds"] = ffprobe_duration(mp3_path)
        episodes.append(ep)

    # Sort by episode_number descending (newest first per RSS convention)
    episodes.sort(key=lambda e: e.get("episode_number", 0), reverse=True)

    # Build XML
    last_build = format_pub_date(dt.datetime.now(dt.timezone.utc))
    lang = show_yaml.get("language", "en-us")
    title = escape(show_yaml["title"])
    subtitle = escape(show_yaml.get("subtitle", ""))
    description = escape(show_yaml["description"].strip())
    author = escape(show_yaml.get("author", ""))
    owner_name = escape(show_yaml.get("owner_name", author))
    owner_email = escape(show_yaml.get("owner_email", ""))
    copyright_str = escape(show_yaml.get("copyright", ""))
    website = escape(show_yaml.get("website", show_url))
    explicit = "true" if show_yaml.get("explicit", False) else "false"
    show_type = show_yaml.get("show_type", "episodic")

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"',
        '  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"',
        '  xmlns:content="http://purl.org/rss/1.0/modules/content/"',
        '  xmlns:atom="http://www.w3.org/2005/Atom"',
        '  xmlns:podcast="https://podcastindex.org/namespace/1.0">',
        '<channel>',
        f'  <atom:link href="{show_url}/feed.xml" rel="self" type="application/rss+xml" />',
        f'  <title>{title}</title>',
        f'  <link>{website}</link>',
        f'  <language>{lang}</language>',
        f'  <copyright>{copyright_str}</copyright>',
        f'  <lastBuildDate>{last_build}</lastBuildDate>',
        f'  <description><![CDATA[{show_yaml["description"].strip()}]]></description>',
        f'  <itunes:author>{author}</itunes:author>',
        f'  <itunes:summary><![CDATA[{show_yaml["description"].strip()}]]></itunes:summary>',
        f'  <itunes:subtitle>{subtitle}</itunes:subtitle>',
        f'  <itunes:owner>',
        f'    <itunes:name>{owner_name}</itunes:name>',
        f'    <itunes:email>{owner_email}</itunes:email>',
        f'  </itunes:owner>',
        f'  <itunes:image href="{cover_url}" />',
        f'  <image>',
        f'    <url>{cover_url}</url>',
        f'    <title>{title}</title>',
        f'    <link>{website}</link>',
        f'  </image>',
        f'  <itunes:explicit>{explicit}</itunes:explicit>',
        f'  <itunes:type>{show_type}</itunes:type>',
    ]

    # Categories
    for cat in show_yaml.get("itunes_category", []):
        ct = escape(cat["text"])
        sub = cat.get("subcategory")
        if sub:
            xml.append(f'  <itunes:category text="{ct}"><itunes:category text="{escape(sub)}" /></itunes:category>')
        else:
            xml.append(f'  <itunes:category text="{ct}" />')

    # AI disclosure (Podcast Index v4.0 standard tag)
    ai_disclosure = show_yaml.get("ai_content_disclosure")
    if ai_disclosure:
        # Spotify accepts free-text disclosure in <itunes:summary>; also add custom tag for future
        xml.append(f'  <!-- AI disclosure: {ai_disclosure} -->')

    # Episodes
    for ep in episodes:
        ep_id = ep["episode_id"]
        ep_title = escape(ep["title"])
        ep_desc = ep["description"].strip()
        ep_num = ep.get("episode_number", 0)
        ep_season = ep.get("season", 1)
        ep_type = ep.get("episode_type", "full")
        ep_explicit = "true" if ep.get("explicit", False) else "false"
        ep_pubdate = format_pub_date(ep["publish_date"])
        ep_dur = ep.get("duration_seconds", 0)
        ep_dur_str = format_duration_hhmmss(ep_dur)
        ep_size = ep["__mp3_size"]
        ep_mime = ep.get("audio_mime", "audio/mpeg")
        ep_mp3_url = f"{show_url}/episodes/{ep.get('audio_file', f'{ep_id}.mp3')}"
        ep_subtitle = escape(ep.get("subtitle", ""))
        ep_keywords = ",".join(ep.get("keywords", []))

        xml.extend([
            '  <item>',
            f'    <title>{ep_title}</title>',
            f'    <link>{ep_mp3_url}</link>',
            f'    <description><![CDATA[{ep_desc}]]></description>',
            f'    <content:encoded><![CDATA[{ep_desc}]]></content:encoded>',
            f'    <guid isPermaLink="false">{show_id}-{ep_id}</guid>',
            f'    <pubDate>{ep_pubdate}</pubDate>',
            f'    <enclosure url="{ep_mp3_url}" length="{ep_size}" type="{ep_mime}" />',
            f'    <itunes:title>{ep_title}</itunes:title>',
            f'    <itunes:author>{author}</itunes:author>',
            f'    <itunes:summary><![CDATA[{ep_desc}]]></itunes:summary>',
            f'    <itunes:subtitle>{ep_subtitle}</itunes:subtitle>',
            f'    <itunes:duration>{ep_dur_str}</itunes:duration>',
            f'    <itunes:episode>{ep_num}</itunes:episode>',
            f'    <itunes:season>{ep_season}</itunes:season>',
            f'    <itunes:episodeType>{ep_type}</itunes:episodeType>',
            f'    <itunes:explicit>{ep_explicit}</itunes:explicit>',
            f'    <itunes:image href="{cover_url}" />',
        ])
        if ep_keywords:
            xml.append(f'    <itunes:keywords>{escape(ep_keywords)}</itunes:keywords>')
        xml.append('  </item>')

    xml.extend(['</channel>', '</rss>'])
    return "\n".join(xml)


def main():
    parser = argparse.ArgumentParser(description="Generate RSS feeds for podcast shows")
    parser.add_argument("--show", help="Generate feed for specific show_id")
    parser.add_argument("--all", action="store_true", help="Generate all shows")
    parser.add_argument("--base-url", default=os.environ.get("PODCAST_BASE_URL", DEFAULT_BASE_URL),
                        help=f"Base URL (default: {DEFAULT_BASE_URL})")
    args = parser.parse_args()

    if not args.show and not args.all:
        parser.error("Must specify --show SHOW_ID or --all")

    show_dirs = []
    if args.all:
        show_dirs = [d for d in SHOWS_DIR.iterdir() if d.is_dir() and (d / "show.yaml").exists()]
    else:
        d = SHOWS_DIR / args.show
        if not d.exists() or not (d / "show.yaml").exists():
            parser.error(f"Show not found: {args.show}")
        show_dirs = [d]

    for show_dir in show_dirs:
        feed_xml = gen_feed(show_dir, args.base_url)
        feed_path = show_dir / "feed.xml"
        feed_path.write_text(feed_xml, encoding="utf-8")
        ep_count = len(list((show_dir / "episodes").glob("*.yaml")))
        print(f"✅ {show_dir.name}/feed.xml ({ep_count} episodes, {feed_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
