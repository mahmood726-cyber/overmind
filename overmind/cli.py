from __future__ import annotations

import argparse
import json
from pathlib import Path

from overmind.config import AppConfig
from overmind.core.orchestrator import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="overmind")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--db-path", type=Path, default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan")
    scan.add_argument("--project-id", default=None)

    audit = subparsers.add_parser("portfolio-audit")
    audit.add_argument("--project-id", default=None)

    enqueue = subparsers.add_parser("enqueue-demo")
    enqueue.add_argument("--project-id", required=True)

    run_once = subparsers.add_parser("run-once")
    run_once.add_argument("--project-id", default=None)
    run_once.add_argument("--settle-seconds", type=float, default=0.75)

    run_loop = subparsers.add_parser("run-loop")
    run_loop.add_argument("--project-id", default=None)
    run_loop.add_argument("--iterations", type=int, default=5)
    run_loop.add_argument("--sleep-seconds", type=float, default=5.0)

    subparsers.add_parser("show-state")

    memories_parser = subparsers.add_parser("memories")
    memories_parser.add_argument("--type", default=None)
    memories_parser.add_argument("--scope", default=None)
    memories_parser.add_argument("--search", default=None)
    memories_parser.add_argument("--forget", default=None)
    memories_parser.add_argument("--stats", action="store_true")

    dream_parser = subparsers.add_parser("dream")
    dream_parser.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_directory(
        config_dir=args.config_dir,
        data_dir=args.data_dir,
        db_path=args.db_path,
    )
    orchestrator = Orchestrator(config)
    try:
        if args.command == "scan":
            payload = orchestrator.scan(focus_project_id=args.project_id)
        elif args.command == "portfolio-audit":
            payload = orchestrator.portfolio_audit(focus_project_id=args.project_id)
        elif args.command == "enqueue-demo":
            payload = orchestrator.enqueue_demo(args.project_id).to_dict()
        elif args.command == "run-once":
            payload = orchestrator.run_once(
                focus_project_id=args.project_id,
                settle_seconds=args.settle_seconds,
            )
        elif args.command == "run-loop":
            payload = orchestrator.run_loop(
                iterations=args.iterations,
                sleep_seconds=args.sleep_seconds,
                focus_project_id=args.project_id,
            )
        elif args.command == "memories":
            if args.forget:
                payload = orchestrator.forget_memory(args.forget)
            elif args.stats:
                payload = orchestrator.memory_store.stats()
            else:
                payload = orchestrator.list_memories(
                    memory_type=args.type,
                    scope=args.scope,
                    search=args.search,
                )
        elif args.command == "dream":
            payload = orchestrator.dream(dry_run=args.dry_run)
        else:
            payload = orchestrator.show_state()
        print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        orchestrator.close()
