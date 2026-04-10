"""Incremental session memory — running summary + extracted facts.

Prevents context amnesia by maintaining two pinned blocks:

1. **Running summary** (importance=1.0): Updated every N iterations with a
   condensed description of what happened. Format:
   "Iter 1-10: scaffolded react-app, wrote types.ts with Item/User interfaces"

2. **Facts block** (importance=0.95): Key decisions extracted from messages
   before they're compressed away. Categories:
   - files_written: paths of files created/edited
   - types_defined: interfaces, types, schemas
   - user_preferences: explicit user requests about style/behavior
   - architecture: framework choices, patterns, layout decisions

Both blocks survive compression because they're pinned with high importance.
The agent never "forgets" what it built or what the user asked for.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("tsunami.session_memory")

UPDATE_INTERVAL = 10  # update summary every N iterations


@dataclass
class SessionFacts:
    """Extracted facts from the conversation — survives compression."""
    files_written: list[str] = field(default_factory=list)
    types_defined: list[str] = field(default_factory=list)
    user_preferences: list[str] = field(default_factory=list)
    architecture: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([self.files_written, self.types_defined,
                        self.user_preferences, self.architecture])

    def to_block(self) -> str:
        """Format as a compact block for context injection."""
        sections = []
        if self.files_written:
            # Deduplicate and keep most recent (last occurrence)
            seen = {}
            for f in self.files_written:
                seen[f] = True
            unique = list(seen.keys())[-30:]  # cap at 30 most recent
            sections.append(f"Files: {', '.join(unique)}")
        if self.types_defined:
            unique = list(dict.fromkeys(self.types_defined))[-15:]
            sections.append(f"Types: {', '.join(unique)}")
        if self.user_preferences:
            unique = list(dict.fromkeys(self.user_preferences))[-10:]
            sections.append(f"User wants: {'; '.join(unique)}")
        if self.architecture:
            unique = list(dict.fromkeys(self.architecture))[-10:]
            sections.append(f"Architecture: {'; '.join(unique)}")
        return "\n".join(sections)

    def merge(self, other: SessionFacts):
        """Merge another facts block into this one."""
        self.files_written.extend(other.files_written)
        self.types_defined.extend(other.types_defined)
        self.user_preferences.extend(other.user_preferences)
        self.architecture.extend(other.architecture)


class SessionMemory:
    """Running session memory — summary + facts, pinned in context."""

    def __init__(self):
        self.summaries: list[str] = []  # "Iter 1-10: did X, Y, Z"
        self.facts = SessionFacts()
        self._last_update_iter: int = 0
        self._last_scan_index: int = 0  # conversation index of last scan

    def should_update(self, iteration: int) -> bool:
        """Check if it's time for a summary update."""
        return iteration > 0 and iteration % UPDATE_INTERVAL == 0 and iteration != self._last_update_iter

    def update_summary(self, iteration: int, messages: list) -> str | None:
        """Scan recent messages and produce a summary line.

        Args:
            iteration: current iteration number
            messages: the full conversation list (Message objects)

        Returns:
            The new summary line, or None if nothing meaningful happened.
        """
        start_iter = self._last_update_iter + 1
        end_iter = iteration

        # Scan messages since last update
        scan_start = max(self._last_scan_index, 0)
        recent = messages[scan_start:]

        if not recent:
            return None

        # Extract key actions from recent messages
        actions = []
        for m in recent:
            extracted = _extract_actions(m.role, m.content, getattr(m, 'tool_call', None))
            actions.extend(extracted)

        if not actions:
            self._last_update_iter = iteration
            self._last_scan_index = len(messages)
            return None

        # Deduplicate and cap
        unique_actions = list(dict.fromkeys(actions))[:8]
        summary_line = f"Iter {start_iter}-{end_iter}: {', '.join(unique_actions)}"

        self.summaries.append(summary_line)
        self._last_update_iter = iteration
        self._last_scan_index = len(messages)

        log.info(f"Session memory updated: {summary_line}")
        return summary_line

    def extract_facts(self, messages: list) -> SessionFacts:
        """Extract facts from a set of messages (typically before compression).

        This runs on messages that are about to be dropped, extracting
        anything worth preserving.
        """
        new_facts = SessionFacts()

        for m in messages:
            content = m.content
            role = m.role
            tool_call = getattr(m, 'tool_call', None)

            # Files written/edited
            if tool_call:
                tc = tool_call.get("function", tool_call)
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                if name in ("file_write", "file_edit") and "path" in args:
                    new_facts.files_written.append(args["path"])
                elif name == "project_init" and "scaffold" in args:
                    new_facts.architecture.append(f"scaffold: {args['scaffold']}")

            # Types defined (look for interface/type/schema patterns)
            if role == "assistant" and ("interface " in content or "type " in content):
                for match in re.finditer(r'(?:interface|type)\s+(\w+)', content):
                    new_facts.types_defined.append(match.group(1))

            # User preferences
            if role == "user":
                pref = _extract_preference(content)
                if pref:
                    new_facts.user_preferences.append(pref)

            # Architecture decisions from tool results
            if "scaffold" in content.lower() and ("created" in content.lower() or "initialized" in content.lower()):
                match = re.search(r'(?:scaffold|template)[:\s]+(\S+)', content, re.IGNORECASE)
                if match:
                    new_facts.architecture.append(f"scaffold: {match.group(1)}")

            # File write confirmations in tool results
            if role == "tool_result" and ("Wrote " in content or "Created " in content):
                for match in re.finditer(r'(?:Wrote|Created|Edited)\s+(\S+)', content):
                    path = match.group(1)
                    if '.' in path:  # likely a file, not just a word
                        new_facts.files_written.append(path)

        if not new_facts.is_empty():
            self.facts.merge(new_facts)
            log.info(f"Extracted facts: {len(new_facts.files_written)} files, "
                     f"{len(new_facts.types_defined)} types, "
                     f"{len(new_facts.user_preferences)} prefs, "
                     f"{len(new_facts.architecture)} arch")

        return new_facts

    def to_context_block(self) -> str | None:
        """Format the full session memory for context injection.

        Returns None if there's nothing to inject yet.
        """
        parts = []

        if self.summaries:
            parts.append("[SESSION MEMORY]\n" + "\n".join(self.summaries))

        if not self.facts.is_empty():
            parts.append("[KEY FACTS]\n" + self.facts.to_block())

        if not parts:
            return None

        return "\n\n".join(parts)


def _extract_actions(role: str, content: str, tool_call: dict | None) -> list[str]:
    """Extract high-level action descriptions from a message."""
    actions = []

    if tool_call:
        tc = tool_call.get("function", tool_call)
        name = tc.get("name", "")
        args = tc.get("arguments", {})

        if name == "file_write":
            path = args.get("path", "unknown")
            actions.append(f"wrote {_basename(path)}")
        elif name == "file_edit":
            path = args.get("path", "unknown")
            actions.append(f"edited {_basename(path)}")
        elif name == "project_init":
            scaffold = args.get("scaffold", "unknown")
            actions.append(f"scaffolded {scaffold}")
        elif name == "shell_exec":
            cmd = args.get("command", "")[:40]
            if "npm" in cmd:
                actions.append("ran npm command")
            elif "build" in cmd:
                actions.append("ran build")
            elif "test" in cmd:
                actions.append("ran tests")
            else:
                actions.append(f"ran: {cmd[:30]}")
        elif name == "generate_image":
            actions.append("generated image")
        elif name == "search_web":
            q = args.get("query", "")[:30]
            actions.append(f"searched: {q}")
        elif name == "message_result":
            actions.append("delivered result")
        elif name == "plan_update":
            actions.append("updated plan")

    elif role == "user":
        # User message — capture the request
        short = content[:60].replace('\n', ' ').strip()
        if short:
            actions.append(f"user said: \"{short}\"")

    return actions


def _extract_preference(content: str) -> str | None:
    """Extract an explicit user preference from their message."""
    content_lower = content.lower()

    # Look for explicit preference signals
    preference_patterns = [
        (r'(?:i want|i need|make it|should be|please use|use)\s+(.{10,60})', None),
        (r'(?:dark|light)\s*(?:mode|theme)', 'dark/light theme preference'),
        (r'(?:mobile[- ]first|responsive)', 'responsive/mobile-first'),
        (r'(?:minimalist|clean|modern|retro|brutalist)', 'style preference'),
    ]

    for pattern, label in preference_patterns:
        match = re.search(pattern, content_lower)
        if match:
            if label:
                return label
            return match.group(1).strip()[:60]

    return None


def _basename(path: str) -> str:
    """Get just the filename from a path."""
    return path.rsplit("/", 1)[-1] if "/" in path else path
