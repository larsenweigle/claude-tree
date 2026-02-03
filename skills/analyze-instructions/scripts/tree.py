#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "tiktoken",
# ]
# ///
"""
tree.py - Generate file tree JSON with token counts for agent docs.

Usage:
    uv run tree.py <root_path> [--output <tree.json>]

Outputs a JSON tree structure where agent docs (CLAUDE.md, AGENTS.md) include
token counts, enabling visualization of instruction file distribution.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import tiktoken

# Patterns for instruction files (agent docs)
AGENT_DOC_PATTERNS = {
    "CLAUDE.md",
    "AGENTS.md",
    "claude.md",
    "agents.md",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".nyc_output",
    "target",
    ".idea",
    ".vscode",
    ".claude",
    "claude-tree",  # Skip output directory
}

# File extensions to skip (binary/non-text files)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".rar",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class",
    ".db", ".sqlite", ".sqlite3",
    ".lock", ".sum",
}


def get_tokenizer():
    """Get tiktoken tokenizer for cl100k_base encoding (used by Claude)."""
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(content: str, tokenizer) -> int:
    """Count tokens in content using tiktoken."""
    return len(tokenizer.encode(content))


def is_agent_doc(filename: str) -> bool:
    """Check if a file is an agent documentation file."""
    return filename in AGENT_DOC_PATTERNS


def should_skip_file(filename: str) -> bool:
    """Check if a file should be skipped based on extension."""
    _, ext = os.path.splitext(filename.lower())
    return ext in SKIP_EXTENSIONS


def build_tree(root_path: Path, tokenizer) -> dict:
    """
    Build a tree structure representing the file system.

    Returns a nested dict with:
    - name: filename or directory name
    - path: relative path from root
    - type: "directory" or "file"
    - children: list of child nodes (for directories)
    - isAgentDoc: True if this is a CLAUDE.md/AGENTS.md file
    - tokens: token count (only for agent docs)
    """
    root_name = root_path.name or "root"

    def process_directory(dir_path: Path, rel_path: str) -> dict:
        """Recursively process a directory and its contents."""
        name = dir_path.name or root_name
        node = {
            "name": name,
            "path": rel_path,
            "type": "directory",
            "children": [],
        }

        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return node

        for entry in entries:
            entry_path = dir_path / entry
            entry_rel_path = str(Path(rel_path) / entry) if rel_path else entry

            if entry_path.is_dir():
                # Skip excluded directories
                if entry in SKIP_DIRS:
                    continue
                # Skip hidden directories (except .claude)
                if entry.startswith(".") and entry != ".claude":
                    continue

                child_node = process_directory(entry_path, entry_rel_path)
                # Only include directories that have children or contain agent docs
                if child_node["children"]:
                    node["children"].append(child_node)

            elif entry_path.is_file():
                # Skip files we don't want to include
                if should_skip_file(entry):
                    continue

                file_node = {
                    "name": entry,
                    "path": entry_rel_path,
                    "type": "file",
                }

                # Add token count for agent docs
                if is_agent_doc(entry):
                    file_node["isAgentDoc"] = True
                    try:
                        content = entry_path.read_text(encoding="utf-8")
                        file_node["tokens"] = count_tokens(content, tokenizer)
                    except Exception as e:
                        print(f"Warning: Could not read {entry_path}: {e}", file=sys.stderr)
                        file_node["tokens"] = 0

                node["children"].append(file_node)

        return node

    return process_directory(root_path, ".")


def filter_tree_to_agent_docs(tree: dict) -> dict:
    """
    Create a filtered tree that only includes:
    - Directories that contain agent docs (directly or in descendants)
    - Agent doc files
    - Regular files (for reference edges)
    """
    def has_agent_doc(node: dict) -> bool:
        """Check if a node or its descendants contain an agent doc."""
        if node.get("isAgentDoc"):
            return True
        if node["type"] == "directory":
            return any(has_agent_doc(child) for child in node.get("children", []))
        return False

    def filter_node(node: dict, include_all_files: bool = False) -> dict | None:
        """Filter a node and its children."""
        if node["type"] == "file":
            # Always include agent docs
            if node.get("isAgentDoc"):
                return node
            # Include regular files only if requested
            if include_all_files:
                return node
            return None

        # Directory node
        filtered_children = []
        for child in node.get("children", []):
            # Include all files in directories that have agent docs
            should_include_all = has_agent_doc(node)
            filtered_child = filter_node(child, include_all_files=should_include_all)
            if filtered_child is not None:
                filtered_children.append(filtered_child)

        if filtered_children or has_agent_doc(node):
            return {
                **node,
                "children": filtered_children,
            }
        return None

    return filter_node(tree) or tree


def collect_agent_docs(tree: dict) -> list[dict]:
    """Extract a flat list of all agent docs from the tree."""
    agent_docs = []

    def walk(node: dict):
        if node.get("isAgentDoc"):
            agent_docs.append({
                "path": node["path"],
                "tokens": node.get("tokens", 0),
            })
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return agent_docs


def main():
    parser = argparse.ArgumentParser(
        description="Generate file tree JSON with token counts for agent docs"
    )
    parser.add_argument(
        "root_path",
        type=str,
        help="Root directory to scan",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file (default: stdout)",
    )
    parser.add_argument(
        "--full-tree",
        action="store_true",
        help="Include all files, not just agent docs and their directories",
    )

    args = parser.parse_args()
    root_path = Path(args.root_path).resolve()

    if not root_path.exists():
        print(f"Error: Path does not exist: {root_path}", file=sys.stderr)
        sys.exit(1)

    if not root_path.is_dir():
        print(f"Error: Path is not a directory: {root_path}", file=sys.stderr)
        sys.exit(1)

    # Initialize tokenizer
    tokenizer = get_tokenizer()

    # Build full tree
    tree = build_tree(root_path, tokenizer)

    # Optionally filter to just agent docs and their context
    if not args.full_tree:
        tree = filter_tree_to_agent_docs(tree)

    # Collect agent docs for summary
    agent_docs = collect_agent_docs(tree)

    # Build output with metadata
    output = {
        "root": str(root_path),
        "tree": tree,
        "agentDocs": agent_docs,
        "totalAgentDocs": len(agent_docs),
        "totalTokens": sum(doc["tokens"] for doc in agent_docs),
    }

    # Print agent doc summary to stderr
    print("\nAgent docs found:", file=sys.stderr)
    if agent_docs:
        for doc in agent_docs:
            print(f"  {doc['path']} ({doc['tokens']} tokens)", file=sys.stderr)
    else:
        print("  (none)", file=sys.stderr)

    # Token warnings
    high_token = [d for d in agent_docs if d["tokens"] > 1500]
    if high_token:
        print(f"\nWarning: {len(high_token)} file(s) exceed 1500 token budget:", file=sys.stderr)
        for f in high_token:
            print(f"  {f['path']}: {f['tokens']} tokens", file=sys.stderr)

    # Output
    json_output = json.dumps(output, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output)
        print(f"\nTree written to {args.output}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == "__main__":
    main()
