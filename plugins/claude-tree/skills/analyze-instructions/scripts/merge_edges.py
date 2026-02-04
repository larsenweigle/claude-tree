#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
merge_edges.py - Merge and validate edge files from sub-agents.

Usage:
    uv run merge_edges.py --input-dir <dir> --output <edges.json> [--validate]

Merges individual edge JSON files into a single edges.json file.
Each input file should have the format:
{
  "source": "path/to/agent.md",
  "edges": [
    {"source": "...", "target": "...", "type": "agent-doc|file"},
    ...
  ]
}
"""

import argparse
import json
import sys
from pathlib import Path


def validate_edge_file(file_path: Path) -> tuple[dict | None, list[str]]:
    """
    Validate a single edge file.

    Returns:
        tuple of (parsed_data or None, list of error messages)
    """
    errors = []

    try:
        content = file_path.read_text()
    except Exception as e:
        errors.append(f"Could not read file: {e}")
        return None, errors

    # Try to parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return None, errors

    # Validate structure
    if not isinstance(data, dict):
        errors.append("Root must be an object")
        return None, errors

    if "source" not in data:
        errors.append("Missing 'source' field")
    elif not isinstance(data["source"], str):
        errors.append("'source' must be a string")

    if "edges" not in data:
        errors.append("Missing 'edges' field")
    elif not isinstance(data["edges"], list):
        errors.append("'edges' must be an array")
    else:
        for i, edge in enumerate(data["edges"]):
            if not isinstance(edge, dict):
                errors.append(f"Edge {i}: must be an object")
                continue
            if "source" not in edge:
                errors.append(f"Edge {i}: missing 'source'")
            if "target" not in edge:
                errors.append(f"Edge {i}: missing 'target'")
            if "type" not in edge:
                errors.append(f"Edge {i}: missing 'type'")
            elif edge.get("type") not in ("agent-doc", "file", "directory"):
                errors.append(f"Edge {i}: 'type' must be 'agent-doc', 'file', or 'directory'")

    if errors:
        return None, errors

    return data, []


def merge_edge_files(input_dir: Path, validate: bool = False, verbose: bool = False) -> tuple[dict, dict]:
    """
    Merge all edge JSON files in a directory.

    Returns:
        tuple of (merged_data, summary)
    """
    merged_edges = []
    summary = {
        "files_processed": 0,
        "files_valid": 0,
        "files_invalid": 0,
        "total_edges": 0,
        "validation_errors": {},
    }

    # Find all JSON files in the input directory
    json_files = sorted(input_dir.glob("*.json"))

    for file_path in json_files:
        summary["files_processed"] += 1

        if verbose:
            print(f"Processing: {file_path.name}", file=sys.stderr)

        data, errors = validate_edge_file(file_path)

        if errors:
            summary["files_invalid"] += 1
            if validate:
                summary["validation_errors"][file_path.name] = errors
            if verbose:
                print(f"  -> INVALID ({len(errors)} errors)", file=sys.stderr)
        else:
            summary["files_valid"] += 1
            edges = data.get("edges", [])
            summary["total_edges"] += len(edges)
            merged_edges.extend(edges)
            if verbose:
                print(f"  -> OK ({len(edges)} edges)", file=sys.stderr)

    return {"edges": merged_edges}, summary


def main():
    parser = argparse.ArgumentParser(
        description="Merge and validate edge files from sub-agents"
    )
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        required=True,
        help="Directory containing individual edge JSON files",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output path for merged edges.json",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Report validation errors in detail",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show files being processed",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    # Validate input directory exists
    if not input_dir.is_dir():
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    # Merge files
    merged_data, summary = merge_edge_files(input_dir, validate=args.validate, verbose=args.verbose)

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write merged output
    output_path.write_text(json.dumps(merged_data, indent=2))

    # Print summary
    print(f"Files processed: {summary['files_processed']}", file=sys.stderr)
    print(f"Files valid: {summary['files_valid']}", file=sys.stderr)
    print(f"Files invalid: {summary['files_invalid']}", file=sys.stderr)
    print(f"Total edges: {summary['total_edges']}", file=sys.stderr)
    print(f"Output written to: {output_path}", file=sys.stderr)

    # Print validation errors if requested
    if args.validate and summary["validation_errors"]:
        print("\nValidation errors:", file=sys.stderr)
        for filename, errors in summary["validation_errors"].items():
            print(f"\n  {filename}:", file=sys.stderr)
            for error in errors:
                print(f"    - {error}", file=sys.stderr)

    # Exit with error code if any files were invalid
    if summary["files_invalid"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
