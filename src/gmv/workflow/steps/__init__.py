from __future__ import annotations

import argparse

from . import agent, project, upstream


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GMV workflow internal step runner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    upstream.register_subcommands(subparsers)
    project.register_subcommands(subparsers)
    agent.register_subcommands(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.error("missing sub-command")
    return int(func(args))
