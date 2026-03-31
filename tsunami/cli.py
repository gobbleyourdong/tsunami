"""Tsunami CLI — the interface between the agent and the human.

Interactive mode: continuous conversation.
Task mode: single task, execute, deliver, exit.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

from .agent import Agent
from .config import TsunamiConfig
from .session import list_sessions, load_session
from .tools.message import set_input_callback


BANNER = """
▀▛▘▞▀▖▌ ▌▙ ▌▞▀▖▙▗▌▜▘
 ▌ ▚▄ ▌ ▌▌▌▌▙▄▌▌▘▌▐
 ▌ ▖ ▌▌ ▌▌▝▌▌ ▌▌ ▌▐
 ▘ ▝▀ ▝▀ ▘ ▘▘ ▘▘ ▘▀▘
 \033[1;38;2;74;158;255mAutonomous Execution Agent\033[0m
"""


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TSUNAMI — Autonomous Agent")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file path")
    parser.add_argument("--task", type=str, default=None, help="Single task to execute")
    parser.add_argument("--model", type=str, default=None, help="Model override (e.g. ollama:qwen2.5:72b)")
    parser.add_argument("--endpoint", type=str, default=None, help="Model endpoint override")
    parser.add_argument("--watcher", action="store_true", help="Enable the Watcher")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--api-key", type=str, default=None, help="API key for remote models")
    parser.add_argument("--sessions", action="store_true", help="List saved sessions")
    parser.add_argument("--resume", type=str, default=None, help="Resume a saved session by ID")
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Config
    config = TsunamiConfig.from_yaml(args.config)
    config = TsunamiConfig.from_env(config)

    if args.model:
        parts = args.model.split(":", 1)
        if len(parts) == 2:
            config.model_backend, config.model_name = parts
        else:
            config.model_name = parts[0]

    if args.endpoint:
        config.model_endpoint = args.endpoint

    if args.api_key:
        config.api_key = args.api_key

    if args.watcher:
        config.watcher_enabled = True

    # Session listing
    if args.sessions:
        session_dir = Path(config.workspace_dir) / ".history"
        sessions = list_sessions(session_dir)
        if not sessions:
            print("No saved sessions found.")
        else:
            print(f"{'ID':<30} {'Iterations':<12} {'Status':<10} {'Time'}")
            print("-" * 75)
            for s in sessions:
                status = "complete" if s["complete"] else "in-progress"
                t = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["timestamp"]))
                print(f"{s['id']:<30} {s['iteration']:<12} {status:<10} {t}")
        return

    # Run
    if args.task:
        asyncio.run(_run_task(config, args.task))
    elif args.resume:
        asyncio.run(_resume_session(config, args.resume))
    else:
        asyncio.run(_interactive(config))


async def _run_task(config: TsunamiConfig, task: str):
    """Execute a single task and exit."""
    agent = Agent(config)
    result = await agent.run(task)
    print(f"\n{'='*60}")
    print(result)


async def _resume_session(config: TsunamiConfig, session_id: str):
    """Resume a saved session."""
    session_dir = Path(config.workspace_dir) / ".history"
    state = load_session(session_dir, session_id)
    if state is None:
        print(f"Session not found: {session_id}")
        return

    print(f"Resumed session {session_id} ({state.iteration} iterations, "
          f"{len(state.conversation)} messages)")
    if state.plan:
        print(f"Plan: {state.plan.summary()}")

    agent = Agent(config)
    agent.state = state
    agent.session_id = session_id

    # Set up input callback
    async def get_user_input(prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input("\n> "))

    set_input_callback(get_user_input)

    # Ask user what to do next
    user_input = input("\nyou> ")
    if user_input.strip():
        await agent.run(user_input)


async def _interactive(config: TsunamiConfig):
    """Interactive conversation loop."""
    print(BANNER)
    print(f"  Model: {config.model_backend}:{config.model_name}")
    print(f"  Endpoint: {config.model_endpoint}")
    print(f"  Watcher: {'ON' if config.watcher_enabled else 'OFF'}")
    print(f"  Workspace: {config.workspace_dir}")
    print(f"  Tools: {len(__import__('manus.tools', fromlist=['build_registry']).build_registry(config).names())}")
    print()

    # Set up async input callback for message_ask
    async def get_user_input(prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input("\n> "))

    set_input_callback(get_user_input)

    while True:
        try:
            user_input = input("\n\033[1myou>\033[0m ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        stripped = user_input.strip().lower()

        if stripped in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if stripped == "/sessions":
            session_dir = Path(config.workspace_dir) / ".history"
            sessions = list_sessions(session_dir)
            if not sessions:
                print("No saved sessions.")
            else:
                for s in sessions:
                    status = "done" if s["complete"] else "active"
                    t = time.strftime("%H:%M", time.localtime(s["timestamp"]))
                    print(f"  [{status}] {s['id']} — {s['iteration']} iterations ({t})")
            continue

        if not user_input.strip():
            continue

        agent = Agent(config)
        try:
            await agent.run(user_input)
        except KeyboardInterrupt:
            print("\n[interrupted]")
        except Exception as e:
            print(f"\n\033[31m[error]\033[0m {e}")
            logging.exception("Agent error")


if __name__ == "__main__":
    main()
