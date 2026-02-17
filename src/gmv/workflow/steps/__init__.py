"""Workflow step dispatcher."""

from __future__ import annotations

import argparse

from gmv.workflow.steps.agent import register_agent
from gmv.workflow.steps.project import register_project
from gmv.workflow.steps.upstream import register_upstream


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GMV v3 workflow step executor")
    subparsers = parser.add_subparsers(dest="step", required=True)

    register_upstream(subparsers)
    register_project(subparsers)
    register_agent(subparsers)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


__all__ = ["build_parser", "main"]
