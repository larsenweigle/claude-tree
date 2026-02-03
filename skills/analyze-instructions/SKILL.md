---
name: analyze-instructions
description: Visualize CLAUDE.md/AGENTS.md instruction files as an interactive tree with token-weighted nodes and reference edges
allowed-tools: Bash, Read, Glob, Grep, Task, Write
---

# Analyze Instructions Skill

Visualize a codebase's instruction files (CLAUDE.md, AGENTS.md) as an interactive tree with token-weighted nodes and reference edges.

## Workflow

Execute these steps in order:

### Step 1: Create Output Directory

Create the `claude-tree/` directory in the scan root for all artifacts:

```bash
mkdir -p ./claude-tree/edges ./claude-tree/visualization
```

The directory structure will be:
```
{repo_root}/
├── claude-tree/           # All artifacts here (add to .gitignore if desired)
│   ├── tree.json          # File tree with token counts
│   ├── edges/             # Sub-agent output files
│   │   ├── CLAUDE_md.json
│   │   ├── src_api_AGENTS_md.json
│   │   └── ...
│   ├── edges.json         # Merged edges
│   └── visualization/
│       └── index.html     # Interactive visualization
└── ... (rest of repo)
```

### Step 2: Generate File Tree

Run the tree generator to discover all files and compute token counts for agent docs:

```bash
uv run skills/analyze-instructions/scripts/tree.py . --output ./claude-tree/tree.json
```

This outputs JSON with:
- Full file tree structure
- Token counts for each CLAUDE.md/AGENTS.md file
- Summary of total agent docs and tokens

**stderr output** shows agent doc paths and token warnings:
```
Agent docs found:
  CLAUDE.md (847 tokens)
  src/api/AGENTS.md (1203 tokens)
  tests/AGENTS.md (412 tokens)

Warning: 1 file(s) exceed 1500 token budget:
  docs/CLAUDE.md: 2104 tokens

Tree written to ./claude-tree/tree.json
```

Use the paths from stderr output to spawn sub-agents in Step 3.

### Step 3: Analyze Agent Docs for References (Parallel Sub-agents)

For each agent doc found in the tree, spawn a sub-agent to extract ALL file references. The sub-agents should run in parallel for speed.

**Important:** Each sub-agent writes its output to a file instead of returning it inline. This prevents lossy manual aggregation.

If you need to re-access agent doc paths programmatically:
```python
import json
docs = json.load(open("./claude-tree/tree.json"))["agentDocs"]
for d in docs: print(d["path"])
```

For each agent doc at path `{agent_doc_path}`, use Task tool with `subagent_type: "instruction-reader"` and this prompt:

```
Analyze the agent doc at {agent_doc_path} and extract ALL file references.

Read the file and identify:
1. Explicit markdown links: [text](path/to/file)
2. Code block file paths mentioned
3. Directory references like "see src/api/"
4. Any other file/directory mentions

For each reference found, determine:
- source: the agent doc path (e.g., "src/api/AGENTS.md")
- target: the referenced file path (e.g., "src/api/routes.ts")
- type: "agent-doc" if target is another CLAUDE.md/AGENTS.md, otherwise "file"

CRITICAL: Write your output using the Write tool to: ./claude-tree/edges/{filename}

Compute {filename} from the source path by replacing "/" with "_" and "." with "_", then append ".json".
Example: "src/api/AGENTS.md" → "src_api_AGENTS_md.json"

The file MUST contain ONLY valid JSON (no markdown, no explanation).
Start with '{' and end with '}'.

{
  "source": "{agent_doc_path}",
  "edges": [
    {"source": "{agent_doc_path}", "target": "path/to/target", "type": "agent-doc|file"},
    ...
  ]
}
```

### Step 4: Merge & Validate Edges

After all sub-agents complete, merge and validate their outputs:

```bash
uv run skills/analyze-instructions/scripts/merge_edges.py \
  --input-dir ./claude-tree/edges \
  --output ./claude-tree/edges.json \
  --validate
```

This will:
- Validate each file has valid JSON with `source` and `edges` fields
- Merge all edges into a single output file
- Print summary (files processed, edges found, validation errors)

Use `--verbose` flag to see each file being processed (helpful for debugging large runs).

If no agent docs were found, create an empty edges file:
```bash
echo '{"edges": []}' > ./claude-tree/edges.json
```

### Step 5: Generate Visualization

Create the interactive HTML visualization:

```bash
uv run skills/analyze-instructions/scripts/visualize.py \
  --tree ./claude-tree/tree.json \
  --edges ./claude-tree/edges.json \
  --output ./claude-tree/visualization \
  --open
```

This generates `./claude-tree/visualization/index.html` with:
- Collapsible tree view of the codebase
- Agent doc nodes colored by token count (green < 500, yellow 500-1500, red > 1500)
- Directory nodes display with "/" suffix for visual distinction
- Reference edges as curved lines (solid for agent-doc links, dashed for file links)
- Agent walk simulator to see cumulative tokens at any directory
- **Copy buttons** for exporting markdown reports:
  - **Copy Budget Report**: Exports a full token budget report with all agent docs, over-budget files, and recommendations
  - **Copy Context Chain**: Exports the context chain for a selected directory (appears after clicking a directory)

### Step 6: Report All Artifacts

Summarize for the user:

1. **Output Directory**: `./claude-tree/` in the scan root
2. **Files Found**: Number of agent docs and total tokens
3. **References**: Number of cross-file references discovered
4. **Validation**: Any errors from edge validation
5. **Visualization**: Confirm visualization is ready

Example output:
```
Output directory: ./claude-tree/

Found 5 agent docs with 2,847 total tokens.
Discovered 12 file references.
All edge files validated successfully.

Artifacts:
- Tree data: ./claude-tree/tree.json
- Edge files: ./claude-tree/edges/ (5 files)
- Merged edges: ./claude-tree/edges.json
- Visualization: ./claude-tree/visualization/index.html
```

## Token Budget Guidelines

From the research on instruction file best practices:

- **Green (< 500 tokens)**: Optimal - minimal context overhead
- **Yellow (500-1500 tokens)**: Acceptable - monitor for growth
- **Red (> 1500 tokens)**: Consider splitting or extracting shared content

The agent walk simulator shows cumulative tokens Claude loads when working in a directory - this helps identify "expensive" paths in the codebase.

**Note on token counts:** Token counts are approximations using OpenAI's `cl100k_base` tokenizer (via tiktoken). Claude doesn't have a public tokenizer, so actual token usage may differ slightly. The counts are directionally accurate for identifying large files and comparing relative sizes.

## Troubleshooting

**Agent doc paths not visible to sub-agents?**
The tree.py stderr output shows all agent doc paths. If you need to access them programmatically:
```python
import json
docs = json.load(open("./claude-tree/tree.json"))["agentDocs"]
for d in docs: print(d["path"])
```

**Sub-agent output validation failing?**
Run merge_edges.py with `--validate --verbose` to see which files have issues and what the errors are.

**Want to keep artifacts out of git?**
Add `claude-tree/` to your `.gitignore` file.

**Visualization not opening?**
The `--open` flag uses the system's default browser. You can also manually open `./claude-tree/visualization/index.html`.

## Dependencies

This skill uses [uv](https://docs.astral.sh/uv/) with [PEP 723](https://peps.python.org/pep-0723/) inline script metadata.

**If uv is not installed:**
- macOS: `brew install uv`
- Other: `curl -LsSf https://astral.sh/uv/install.sh | sh`
