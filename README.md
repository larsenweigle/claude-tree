# claude-tree

Visualize CLAUDE.md/AGENTS.md instruction files as an interactive tree with token-weighted nodes and reference edges.

## Installation

```bash
# Test locally during development
claude --plugin-dir /path/to/claude-tree

# Then invoke the skill
/claude-tree:analyze-instructions
```

## Requirements

- [uv](https://docs.astral.sh/uv/) - Python package runner
  - macOS: `brew install uv`
  - Other: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## How It Works

```
/claude-tree:analyze-instructions
        │
        ▼
┌───────────────────────────────────┐
│  1. tree.py                       │
│  - Generate file tree JSON        │
│  - Token count agent docs         │
│  - Uses tiktoken                  │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│  2. Sub-agents (parallel)         │
│  - Analyze each agent doc         │
│  - Extract ALL file references    │
│  - Output edges JSON              │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│  3. visualize.py                  │
│  - Merge tree + edges             │
│  - Generate D3.js HTML            │
│  - Output to ./claude-tree/       │
└───────────────────────────────────┘
```

## Visualization Features

- **Collapsible tree view** of your codebase
- **Token-weighted nodes**: Agent docs colored by size
  - Green: < 500 tokens (optimal)
  - Yellow: 500-1500 tokens (acceptable)
  - Red: > 1500 tokens (consider splitting)
- **Reference edges**: Curved lines showing file references
  - Solid: agent-doc → agent-doc
  - Dashed: agent-doc → regular file
- **Agent walk simulator**: Click any directory to see cumulative tokens Claude loads when working there
- **Copy to clipboard**: Export markdown reports for use with coding agents
  - **Copy Budget Report** (header): Full token budget report with all files, over-budget warnings, and optimization recommendations
  - **Copy Context Chain** (sidebar): Context chain for selected directory showing which CLAUDE.md files load and their token costs

## Output

All artifacts saved to `./claude-tree/` in your repo:

```
./claude-tree/
├── tree.json              # File tree with token counts
├── edges/                 # Individual edge files from sub-agents
├── edges.json             # Merged edges
└── visualization/
    └── index.html         # Interactive visualization
```

Add `claude-tree/` to `.gitignore` if you don't want to commit artifacts.

## Token Budget Guidelines

| File Type | Recommended Max |
|-----------|-----------------|
| Root CLAUDE.md | 2,000 tokens |
| Subtree AGENTS.md | 1,500 tokens |
| Total chain at any path | 5,000 tokens |
