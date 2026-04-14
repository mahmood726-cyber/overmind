from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from overmind.config import AppConfig, default_db_path
from overmind.core.orchestrator import Orchestrator

_BROKEN_PIPE_STREAM = None
_PIPE_ERROR_ERRNOS = {22, 32}
_PIPE_ERROR_WINERRORS = {109, 232}


def _silence_broken_pipe() -> None:
    global _BROKEN_PIPE_STREAM
    if _BROKEN_PIPE_STREAM is not None:
        sys.stdout = _BROKEN_PIPE_STREAM
        sys.__stdout__ = _BROKEN_PIPE_STREAM
        return
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        replacement = open(os.devnull, "w", encoding=encoding)
    except OSError:
        return
    try:
        stdout_fileno = sys.stdout.fileno()
        os.dup2(replacement.fileno(), stdout_fileno)
    except (AttributeError, OSError, ValueError):
        pass
    _BROKEN_PIPE_STREAM = replacement
    sys.stdout = replacement
    sys.__stdout__ = replacement


def _emit_payload(payload: object, stream=None) -> int:
    target = sys.stdout if stream is None else stream
    try:
        json.dump(payload, target, indent=2, sort_keys=True, default=str)
        target.write("\n")
        return 0
    except BrokenPipeError:
        if stream is None or target is sys.stdout:
            _silence_broken_pipe()
            raise SystemExit(0)
        return 0
    except OSError as exc:
        if getattr(exc, "errno", None) not in _PIPE_ERROR_ERRNOS and getattr(exc, "winerror", None) not in _PIPE_ERROR_WINERRORS:
            raise
        if stream is None or target is sys.stdout:
            _silence_broken_pipe()
            raise SystemExit(0)
        return 0


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
    run_once.add_argument("--dry-run", action="store_true")

    run_loop = subparsers.add_parser("run-loop")
    run_loop.add_argument("--project-id", default=None)
    run_loop.add_argument("--iterations", type=int, default=5)
    run_loop.add_argument("--sleep-seconds", type=float, default=5.0)

    state_parser = subparsers.add_parser("show-state")
    state_parser.add_argument("--project-id", default=None)

    checkpoints_parser = subparsers.add_parser("checkpoints")
    checkpoints_parser.add_argument("--name", default=None)
    checkpoints_parser.add_argument("--limit", type=int, default=20)

    replay_parser = subparsers.add_parser("replay-checkpoint")
    replay_parser.add_argument("--checkpoint-id", type=int, default=None)
    replay_parser.add_argument("--name", default="main")
    replay_parser.add_argument("--project-id", default=None)

    restore_parser = subparsers.add_parser("restore-checkpoint")
    restore_parser.add_argument("--checkpoint-id", type=int, default=None)
    restore_parser.add_argument("--name", default="main")
    restore_parser.add_argument("--project-id", default=None)
    restore_parser.add_argument(
        "--force",
        action="store_true",
        help="Restore even if active sessions would be terminated.",
    )

    memories_parser = subparsers.add_parser("memories")
    memories_parser.add_argument("--type", default=None)
    memories_parser.add_argument("--scope", default=None)
    memories_parser.add_argument("--search", default=None)
    memories_parser.add_argument("--forget", default=None)
    memories_parser.add_argument("--stats", action="store_true")

    dream_parser = subparsers.add_parser("dream")
    dream_parser.add_argument("--dry-run", action="store_true")

    audit_parser = subparsers.add_parser("audit-history")
    audit_parser.add_argument("--project-id", required=True)

    # Wrap command: overmind wrap <claude|codex|gemini> [args...]
    wrap_parser = subparsers.add_parser("wrap")
    wrap_parser.add_argument("runner", choices=["claude", "codex", "gemini"])
    wrap_parser.add_argument("extra", nargs="*", default=[])

    # Watch command: overmind watch [--interval 30] [--iterations N]
    watch_parser = subparsers.add_parser("watch")
    watch_parser.add_argument("--interval", type=int, default=30)
    watch_parser.add_argument("--iterations", type=int, default=None)

    # Sessions command: overmind sessions
    subparsers.add_parser("sessions")

    # Daily report
    subparsers.add_parser("daily-report")

    # Batch verify
    batch_parser = subparsers.add_parser("batch-verify")
    batch_parser.add_argument("--count", type=int, default=10)
    batch_parser.add_argument("--risk", default=None, choices=["high", "medium_high", "medium"])

    eval_parser = subparsers.add_parser("eval-harness")
    eval_parser.add_argument("--project-id", default=None)

    # Mine sessions
    mine_parser = subparsers.add_parser("mine-sessions")
    mine_parser.add_argument("--count", type=int, default=30)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Commands that don't need full orchestrator
    if args.command == "wrap":
        from overmind.activation.wrap import wrap
        db_path = args.db_path or default_db_path()
        return wrap(args.runner, args.extra, db_path=db_path)

    if args.command == "watch":
        from overmind.activation.watchdog import watch
        db_path = args.db_path or default_db_path()
        watch(db_path, interval=args.interval, iterations=args.iterations)
        return 0

    if args.command == "sessions":
        from overmind.activation.session_tracker import SessionTracker
        from overmind.storage.db import StateDatabase
        db_path = args.db_path or default_db_path()
        db = StateDatabase(db_path)
        try:
            tracker = SessionTracker(db)
            tracker.cleanup_stale()
            sessions = tracker.active_sessions()
            return _emit_payload(sessions)
        finally:
            db.close()

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
                dry_run=args.dry_run,
            )
        elif args.command == "run-loop":
            payload = orchestrator.run_loop(
                iterations=args.iterations,
                sleep_seconds=args.sleep_seconds,
                focus_project_id=args.project_id,
            )
        elif args.command == "checkpoints":
            payload = orchestrator.list_checkpoints(name=args.name, limit=args.limit)
        elif args.command == "replay-checkpoint":
            payload = orchestrator.replay_checkpoint(
                checkpoint_id=args.checkpoint_id,
                checkpoint_name=args.name,
                focus_project_id=args.project_id,
            )
        elif args.command == "restore-checkpoint":
            payload = orchestrator.restore_checkpoint(
                checkpoint_id=args.checkpoint_id,
                checkpoint_name=args.name,
                focus_project_id=args.project_id,
                force=args.force,
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
        elif args.command == "audit-history":
            payload = orchestrator.audit_loop.project_history(args.project_id)
        elif args.command == "daily-report":
            from overmind.intelligence.daily_report import DailyReport
            reporter = DailyReport(orchestrator.db, config.data_dir / "artifacts")
            report = reporter.generate()
            paths = reporter.write(report)
            payload = {"report": report, "artifacts": paths}
        elif args.command == "batch-verify":
            from overmind.intelligence.batch_verify import batch_verify
            payload = batch_verify(orchestrator, count=args.count, risk_filter=args.risk)
        elif args.command == "eval-harness":
            from overmind.intelligence.eval_harness import EvalHarness
            payload = EvalHarness(orchestrator, config.data_dir / "artifacts").run(
                focus_project_id=args.project_id
            )
        elif args.command == "mine-sessions":
            from overmind.intelligence.session_miner import SessionMiner
            miner = SessionMiner(orchestrator.db)
            payload = miner.mine_and_store(max_sessions=args.count)
        else:
            payload = orchestrator.show_state(focus_project_id=args.project_id)
        return _emit_payload(payload)
    finally:
        orchestrator.close()


if __name__ == "__main__":
    raise SystemExit(main())
