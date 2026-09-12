"""Command line interface.

    gisqa examples/data/parcels_dirty.geojson --rules examples/rules.yml

Exit codes are what make this usable in CI or in a nightly load job:
    0  no errors
    1  at least one error
    2  the file or the rules could not be read
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from .core import validate_file
from .rules import LayerRules

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_UNUSABLE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gisqa",
        description="Validate a spatial layer against a written rule file.",
    )
    parser.add_argument("dataset", help="path to a vector file (GeoPackage, GeoJSON, Shapefile, ...)")
    parser.add_argument("-r", "--rules", required=True, help="path to the YAML or JSON rule file")
    parser.add_argument("-l", "--layer", help="layer name, for multi-layer sources such as GeoPackage")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json"],
        default="text",
        help="report format (default: text)",
    )
    parser.add_argument("-o", "--output", help="write the report to this file instead of stdout")
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="exit non-zero when there are warnings but no errors",
    )
    parser.add_argument("--no-colour", action="store_true", help="disable ANSI colour")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    dataset = pathlib.Path(args.dataset)
    rules_path = pathlib.Path(args.rules)

    if not dataset.exists():
        print(f"gisqa: dataset not found: {dataset}", file=sys.stderr)
        return EXIT_UNUSABLE
    if not rules_path.exists():
        print(f"gisqa: rule file not found: {rules_path}", file=sys.stderr)
        return EXIT_UNUSABLE

    try:
        LayerRules.load(rules_path)
    except Exception as exc:  # noqa: BLE001 - the message is the useful part
        print(f"gisqa: could not read rules: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE

    try:
        report = validate_file(dataset, rules_path, layer=args.layer)
    except Exception as exc:  # noqa: BLE001
        print(f"gisqa: could not read {dataset}: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE

    use_colour = sys.stdout.isatty() and not args.no_colour and not args.output
    text = report.to_json() if args.format == "json" else report.to_text(use_colour)

    if args.output:
        pathlib.Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"report written to {args.output}")
    else:
        print(text)

    if report.errors:
        return EXIT_FAILED
    if args.warnings_as_errors and report.warnings:
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
