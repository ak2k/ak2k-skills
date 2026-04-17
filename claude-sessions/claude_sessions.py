"""List recent Claude Code sessions with metadata for easy resumption."""

import json
import re
import shlex
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import click

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
IDLE_THRESHOLD_SECS = 600  # 10 min — gaps longer than this aren't "active work"


def parse_timestamp(ts: object) -> datetime | None:
    """Parse a timestamp from either ISO string or epoch millis."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def extract_user_text(msg: dict) -> str | None:
    """Extract text content from a user message."""
    content = msg.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return cast(str, block.get("text", ""))
    return None


def scan_session(jsonl_path: Path) -> dict | None:
    """Extract metadata from a session JSONL file."""
    try:
        size = jsonl_path.stat().st_size
    except OSError:
        return None

    first_ts = None
    last_ts = None
    prev_ts = None
    active_secs = 0.0
    line_count = 0
    topic_texts: list[str] = []
    awaiting_topic = True
    last_user_text: str | None = None
    user_count = 0
    assistant_count = 0
    session_id = None
    cwd = None
    slug = None
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_create_tokens = 0
    cost_usd = 0.0

    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                line_count += 1
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if d.get("isApiErrorMessage"):
                    continue

                ts = parse_timestamp(d.get("timestamp"))
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    if prev_ts is not None:
                        gap = (ts - prev_ts).total_seconds()
                        if 0 < gap < IDLE_THRESHOLD_SECS:
                            active_secs += gap
                        elif gap >= IDLE_THRESHOLD_SECS:
                            awaiting_topic = True
                    prev_ts = ts
                    last_ts = ts

                if not session_id:
                    session_id = d.get("sessionId")
                if not cwd:
                    cwd = d.get("cwd")
                if not slug and d.get("slug"):
                    slug = d.get("slug")

                msg = d.get("message", {})
                msg_type = d.get("type")

                if msg_type == "user":
                    text = extract_user_text(d)
                    if text and len(text) > 5:
                        if awaiting_topic:
                            topic_texts.append(text)
                            awaiting_topic = False
                        last_user_text = text
                    user_count += 1
                elif msg_type == "assistant":
                    if msg.get("model") == "<synthetic>":
                        continue
                    assistant_count += 1

                usage = msg.get("usage")
                if usage:
                    input_tokens += usage.get("input_tokens", 0)
                    output_tokens += usage.get("output_tokens", 0)
                    cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                    cache_create_tokens += usage.get("cache_creation_input_tokens", 0)

                if d.get("costUSD"):
                    cost_usd += d["costUSD"]
    except OSError:
        return None

    if not session_id or not last_ts:
        return None

    return {
        "session_id": session_id,
        "slug": slug,
        "cwd": cwd,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "active_secs": int(active_secs),
        "line_count": line_count,
        "size_bytes": size,
        "topic_texts": topic_texts,
        "last_user_text": last_user_text,
        "user_count": user_count,
        "assistant_count": assistant_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_create_tokens": cache_create_tokens,
        "cost_usd": cost_usd,
    }


def clean_text(text: str) -> str:
    """Strip XML system tags and collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>.*?</[^>]+>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"</?[^>]+>", "", cleaned).strip()
    return " ".join(cleaned.split()) if cleaned else ""


def make_topic_summary(texts: list[str], max_len: int = 120) -> str:
    """Create a topic summary from topic pivot texts."""
    if not texts:
        return "(no user messages)"

    cleaned = [c for t in texts if (c := clean_text(t))]
    if not cleaned:
        return "(system message)"

    if len(cleaned) == 1:
        s = cleaned[0]
        return s[: max_len - 1] + "\u2026" if len(s) > max_len else s

    per_topic = max(30, max_len // len(cleaned))
    parts = []
    for c in cleaned:
        if len(c) > per_topic:
            c = c[: per_topic - 1] + "\u2026"
        parts.append(c)
    joined = " | ".join(parts)
    if len(joined) > max_len:
        joined = joined[: max_len - 1] + "\u2026"
    return joined


def format_duration(total_secs: int) -> str:
    """Format a duration in seconds as a human-readable string."""
    if total_secs < 60:
        return f"{total_secs}s"
    if total_secs < 3600:
        return f"{total_secs // 60}m"
    hours = total_secs // 3600
    mins = (total_secs % 3600) // 60
    return f"{hours}h{mins}m" if mins else f"{hours}h"


def format_tokens(n: int) -> str:
    """Format token count as human-readable."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def format_relative_time(ts: datetime) -> str:
    """Format timestamp as relative time."""
    secs = int((datetime.now(timezone.utc) - ts).total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def resume_cmd(s: dict) -> str:
    """Build a shell command to cd + resume a session."""
    return f"cd {shlex.quote(s['project_path'])} && claude --resume {s['session_id']}"


def collect_sessions(days: int, project: str | None, search: str | None, limit: int) -> list[dict]:
    """Scan session files and return matching sessions sorted by recency."""
    if not PROJECTS_DIR.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    sessions = []

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    continue
            except OSError:
                continue

            if search:
                try:
                    raw = jsonl_file.read_bytes()
                    if not re.search(re.escape(search).encode(), raw, re.IGNORECASE):
                        continue
                except OSError:
                    continue

            info = scan_session(jsonl_file)
            if not info or info["last_ts"] < cutoff:
                continue

            info["project_path"] = info.get("cwd") or project_dir.name
            if project and project.lower() not in info["project_path"].lower():
                continue
            sessions.append(info)

    sessions.sort(key=lambda s: s["last_ts"], reverse=True)
    return sessions[:limit]


def session_to_json(s: dict) -> dict:
    """Convert a session dict to JSON-serializable output."""
    return {
        "session_id": s["session_id"],
        "slug": s["slug"],
        "project_path": s["project_path"],
        "cwd": s["cwd"],
        "first_ts": s["first_ts"].isoformat() if s["first_ts"] else None,
        "last_ts": s["last_ts"].isoformat(),
        "active_time": format_duration(s["active_secs"]),
        "wall_secs": int((s["last_ts"] - s["first_ts"]).total_seconds()) if s["first_ts"] else None,
        "input_tokens": s["input_tokens"],
        "output_tokens": s["output_tokens"],
        "cache_read_tokens": s["cache_read_tokens"],
        "cache_create_tokens": s["cache_create_tokens"],
        "cost_usd": s["cost_usd"] or None,
        "lines": s["line_count"],
        "size": s["size_bytes"],
        "user_messages": s["user_count"],
        "assistant_turns": s["assistant_count"],
        "topic": make_topic_summary(s["topic_texts"]),
        "resume_cmd": resume_cmd(s),
    }


@click.command()
@click.option("-d", "--days", default=7, help="Look back this many days.")
@click.option("-n", "--limit", default=20, help="Max sessions to show.")
@click.option("-p", "--project", default=None, help="Filter by project path substring.")
@click.option("-s", "--search", default=None, help="Keyword search (case-insensitive).")
@click.option("--json-output", "as_json", is_flag=True, help="Output as JSON.")
def main(days: int, limit: int, project: str | None, search: str | None, as_json: bool) -> None:
    """List recent Claude Code sessions for easy resumption."""
    sessions = collect_sessions(days, project, search, limit)

    if as_json:
        json.dump([session_to_json(s) for s in sessions], sys.stdout, indent=2)
        print()
        return

    if not sessions:
        click.echo(f"No sessions found in the past {days} day(s).")
        return

    for i, s in enumerate(sessions):
        topic = make_topic_summary(s["topic_texts"][:1])
        active = format_duration(s["active_secs"])
        rel_time = format_relative_time(s["last_ts"])
        ctx = s["input_tokens"] + s["cache_read_tokens"] + s["cache_create_tokens"]
        tokens = f"{format_tokens(ctx)}in/{format_tokens(s['output_tokens'])}out"
        turns = f"{s['user_count']}u/{s['assistant_count']}a"
        cost = f"${s['cost_usd']:.2f}" if s["cost_usd"] else ""

        slug_part = f"  ({s['slug']})" if s["slug"] else ""
        click.echo(
            f"\033[1;36m[{i + 1}]\033[0m {rel_time:<10} "
            f"{active:<6} {tokens:<18} {turns:<10}{slug_part}"
        )
        if cost:
            click.echo(f"    {cost}")
        last = clean_text(s["last_user_text"]) if s["last_user_text"] else None
        if last and len(last) > 120:
            last = last[:119] + "\u2026"

        click.echo(f"    \033[0;33m{s['project_path']}\033[0m")
        click.echo(f"    {topic}")
        if last and last != topic.rstrip("\u2026"):
            click.echo(f"    \033[0;2mlast: {last}\033[0m")
        click.echo(f"    \033[0;32m{resume_cmd(s)}\033[0m")
        click.echo()
