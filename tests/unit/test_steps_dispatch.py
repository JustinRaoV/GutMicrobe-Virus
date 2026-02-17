from __future__ import annotations

from gmv.workflow.steps import build_parser


def test_steps_parser_contains_preprocess() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "preprocess",
            "--r1-in",
            "a.fq",
            "--r2-in",
            "b.fq",
            "--r1-out",
            "c.fq",
            "--r2-out",
            "d.fq",
        ]
    )
    assert args.command == "preprocess"
    assert callable(args.func)
