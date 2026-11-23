"""Summarize local agent session transcripts (Claude Code + Codex CLI).

Reads ~/.claude/projects/**/*.jsonl and ~/.codex/sessions/**/*.jsonl and
writes only counts (no prompt text) to .cache/sessions.json, which
scripts/aggregate.py folds into data/stats.json.

Usage: python scripts/sessions.py
"""
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "sessions.json"
HOME = Path.home()


SKIP_EXES = {"cd", "export", "set", "source", ".", "true", "pushd", "popd", "unset", "alias", "Set-Location", "echo", "printf", "break", "continue", "exit", "return", "Write-Host", "Write-Output", "sleep", "Start-Sleep", "wait", "[Console]::OutputEncoding"}
TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')
LOOP_WORDS = {"do", "then", "else", "{", "("}
LOOP_HEADS = {"for", "while", "until", "if", "elif", "done", "fi", "foreach", "ForEach-Object", "Where-Object"}
WRAPPERS = {"time", "sudo", "command", "env", "nohup", "&", "call", "exec"}
SEGMENT = re.compile(r"\s*(?:&&|\|\||;|\n)\s*")


def primary_command(cmd):
    """Name the main program a shell call runs, e.g. 'git commit', 'python', 'curl', 'script'."""
    for seg in SEGMENT.split(cmd.strip()):
        seg = seg.strip().lstrip("({ ").strip()
        if not seg or seg.startswith("#"):
            continue
        # Quote-aware split so 'C:\Program Files\Git\bin\git.exe' stays one token.
        toks = [a or b or c for a, b, c in TOKEN.findall(seg)]
        while toks and toks[0] in LOOP_WORDS:
            toks.pop(0)
        if toks and toks[0] in LOOP_HEADS:
            continue
        while toks and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]) or toks[0] in WRAPPERS):
            toks.pop(0)
        if toks and toks[0] == "timeout":
            toks = toks[2:]
        if not toks:
            continue
        exe = toks[0].strip("\"'`")
        if exe in SKIP_EXES or exe.startswith("$env:") or exe.startswith("$ErrorAction") or not re.match(r"^[A-Za-z0-9_.$/~\\]", exe):
            continue
        if exe.startswith("$"):
            return "(variable)"
        base = re.split(r"[\\/]", exe)[-1]
        base = re.sub(r"\.(exe|cmd|bat)$", "", base, flags=re.I)
        if re.search(r"\.(sh|ps1)$", base, re.I) or exe.startswith("./") or exe.startswith(".\\") or exe.startswith("scripts/"):
            return "script"
        if base in ("git", "gh"):
            rest, i = toks[1:], 0
            while i < len(rest):
                if rest[i] in ("-C", "-c"):
                    i += 2
                elif rest[i].startswith("-"):
                    i += 1
                else:
                    return f"{base} {rest[i]}"
            return base
        if re.match(r"^python[0-9.]*$", base) or base == "py":
            return "python"
        return base
    return "(other)"


def claude_file(path, agg):
    prompts = tools = 0
    first = None
    sidechain = "subagents" in path.parts or path.name.startswith("agent-")
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            ts = ev.get("timestamp")
            if ts and not first:
                first = ts
            if ev.get("isSidechain"):
                sidechain = True
            msg = ev.get("message") or {}
            if ev.get("type") == "user" and not ev.get("isMeta"):
                content = msg.get("content")
                if isinstance(content, str) and not content.startswith("<"):
                    prompts += 1
                elif isinstance(content, list) and any(
                    b.get("type") == "text" and not b.get("text", "").startswith("<") for b in content
                ):
                    prompts += 1
            elif ev.get("type") == "assistant":
                for b in msg.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tools += 1
                        agg["claude_tool_names"][b.get("name", "?")] += 1
                        if b.get("name") in ("Bash", "PowerShell"):
                            agg["shell_commands"][primary_command((b.get("input") or {}).get("command") or "")] += 1
    if not first:
        return
    day = first[:10]
    kind = "subagent" if sidechain else "session"
    agg["claude_" + kind + "s"] += 1
    agg["claude_prompts"] += 0 if sidechain else prompts
    agg["claude_tool_calls"] += tools
    agg["claude_by_day"][day] += 1
    agg["claude_tools_by_day"][day] += tools


def codex_file(path, agg):
    prompts = tools = 0
    first = None
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not first and ev.get("timestamp"):
                first = ev["timestamp"]
            p = ev.get("payload") or {}
            if ev.get("type") == "event_msg" and p.get("type") == "user_message":
                prompts += 1
            elif ev.get("type") == "response_item" and p.get("type") in ("function_call", "custom_tool_call", "local_shell_call"):
                tools += 1
    if not first:
        return
    agg["codex_sessions"] += 1
    agg["codex_prompts"] += prompts
    agg["codex_tool_calls"] += tools
    agg["codex_by_day"][first[:10]] += 1


def main():
    agg = collections.defaultdict(int)
    for k in ("claude_by_day", "claude_tools_by_day", "codex_by_day", "claude_tool_names", "shell_commands"):
        agg[k] = collections.Counter()
    for p in (HOME / ".claude" / "projects").rglob("*.jsonl"):
        claude_file(p, agg)
    for p in (HOME / ".codex" / "sessions").rglob("*.jsonl"):
        codex_file(p, agg)
    agg["claude_tool_names"] = dict(agg["claude_tool_names"].most_common(60))
    agg["shell_commands"] = dict(agg["shell_commands"].most_common(150))
    OUT.write_text(json.dumps(agg, indent=1, sort_keys=True))
    print({k: v for k, v in agg.items() if isinstance(v, int)})


if __name__ == "__main__":
    main()
