#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
visualize.py - Generate interactive D3.js HTML visualization.

Usage:
    uv run visualize.py --tree <tree.json> --edges <edges.json> [--path-weights <path_weights.json>] [--output <dir>] [--open]

Features:
- Collapsible tree view
- Agent doc nodes colored by token count (green→yellow→red)
- Reference edges drawn as curved lines
- Agent walk simulator: Click any directory to see cumulative token count
- Path weight view: Toggle to see tree links colored by cumulative token cost
"""

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path


def load_json(path: str) -> dict:
    """Load JSON from file."""
    return json.loads(Path(path).read_text())


def generate_html(tree_data: dict, edges_data: dict, path_weights_data: dict | None = None) -> str:
    """Generate self-contained HTML with embedded D3.js visualization."""
    tree_json = json.dumps(tree_data)
    edges_json = json.dumps(edges_data)
    path_weights_json = json.dumps(path_weights_data) if path_weights_data else "null"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Tree - Instruction File Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --text-muted: #484f58;
            --accent: #58a6ff;
            --border: #30363d;
            --green: #3fb950;
            --yellow: #d29922;
            --red: #f85149;
            --edge-agent-doc: #58a6ff;
            --edge-file: #d4a72c;  /* warm gold, distinct from orange node highlights */
            --edge-directory: #a371f7;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            overflow: hidden;
        }}

        .container {{
            display: grid;
            grid-template-columns: 1fr 320px;
            grid-template-rows: auto 1fr;
            height: 100vh;
        }}

        header {{
            grid-column: 1 / -1;
            background: var(--bg-secondary);
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
        }}

        header h1 {{
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text-primary);
        }}

        .header-stats {{
            display: flex;
            gap: 20px;
            font-size: 13px;
        }}

        .header-stat {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .header-stat-value {{
            font-weight: 600;
            color: var(--accent);
        }}

        .header-stat-label {{
            color: var(--text-secondary);
        }}

        .main-content {{
            background: var(--bg-primary);
            overflow: hidden;
            position: relative;
        }}

        .tree-container {{
            width: 100%;
            height: 100%;
            overflow: hidden;
            cursor: grab;
            position: relative;
        }}

        #tree {{
            width: 100%;
            height: 100%;
            display: block;
        }}

        .tree-container:active {{
            cursor: grabbing;
        }}

        .sidebar {{
            background: var(--bg-secondary);
            border-left: 1px solid var(--border);
            overflow-y: auto;
            padding: 16px;
        }}

        .sidebar h2 {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}

        .sidebar-section {{
            margin-bottom: 24px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            font-size: 12px;
        }}

        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}

        .legend-line {{
            width: 24px;
            height: 2px;
        }}

        .legend-line.dashed {{
            background: repeating-linear-gradient(
                90deg,
                var(--text-secondary) 0px,
                var(--text-secondary) 4px,
                transparent 4px,
                transparent 8px
            );
        }}

        .path-info {{
            background: var(--bg-tertiary);
            border-radius: 6px;
            padding: 12px;
        }}

        .path-info-title {{
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}

        .path-info-path {{
            font-size: 12px;
            font-family: monospace;
            color: var(--accent);
            word-break: break-all;
            margin-bottom: 8px;
            overflow-wrap: break-word;
            overflow: hidden;
        }}

        .path-info-tokens {{
            font-size: 20px;
            font-weight: 600;
        }}

        .path-info-label {{
            font-size: 11px;
            color: var(--text-secondary);
        }}

        .path-chain {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }}

        .path-chain-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            font-size: 11px;
        }}

        .path-chain-item .file {{
            color: var(--text-secondary);
            font-family: monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            min-width: 0;
        }}

        .path-chain-item .tokens {{
            font-weight: 500;
        }}

        /* Tree nodes */
        .node {{
            cursor: pointer;
        }}

        .node circle {{
            stroke: var(--bg-primary);
            stroke-width: 2px;
            transition: all 0.15s ease;
        }}

        .node:hover circle {{
            stroke-width: 3px;
            filter: brightness(1.2);
        }}

        .node text {{
            font-size: 11px;
            fill: var(--text-primary);
            pointer-events: none;
        }}

        .node.directory circle {{
            fill: var(--bg-tertiary);
        }}

        .node.directory text {{
            fill: #7d8fa8;  /* muted blue-gray to pair with blue walk highlighting */
        }}

        .node.file circle {{
            fill: var(--text-muted);
        }}

        .node.agent-doc circle {{
            stroke-width: 2px;
        }}

        .node.collapsed circle {{
            stroke: var(--accent);
            stroke-width: 2px;
        }}

        .node.highlighted circle {{
            stroke: var(--accent);
            stroke-width: 3px;
            filter: drop-shadow(0 0 4px var(--accent));
        }}

        @keyframes pulse {{
            0%, 100% {{ filter: drop-shadow(0 0 4px var(--accent)); }}
            50% {{ filter: drop-shadow(0 0 8px var(--accent)); }}
        }}

        .node.highlighted.selected circle {{
            animation: pulse 2s ease-in-out infinite;
        }}

        .node.highlighted text {{
            fill: var(--accent);
            font-weight: 600;
        }}

        .node.referenced circle {{
            stroke: #f0883e;
            stroke-width: 3px;
            filter: drop-shadow(0 0 4px #f0883e);
        }}

        .node.referenced text {{
            fill: #f0883e;
            font-weight: 600;
        }}

        .edge.highlighted-edge {{
            opacity: 1;
            stroke-width: 2.5px;
        }}

        /* Tree links */
        .link {{
            fill: none;
            stroke: var(--border);
            stroke-width: 1px;
        }}

        .link.highlighted {{
            stroke: var(--accent);
            stroke-width: 2px;
        }}

        /* Reference edges */
        .edge {{
            fill: none;
            stroke-width: 1.5px;
            opacity: 0.6;
        }}

        .edge.agent-doc {{
            stroke: var(--edge-agent-doc);
        }}

        .edge.file {{
            stroke: var(--edge-file);
            stroke-dasharray: 4,3;
        }}

        .edge.directory {{
            stroke: var(--edge-directory);
            stroke-dasharray: 2,2;
        }}

        .edge:hover {{
            opacity: 1;
            stroke-width: 2.5px;
        }}

        /* Tooltip */
        .tooltip {{
            position: fixed;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 10px 12px;
            pointer-events: none;
            z-index: 1000;
            max-width: 280px;
            font-size: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }}

        .tooltip-title {{
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 6px;
            word-break: break-all;
        }}

        .tooltip-row {{
            display: flex;
            justify-content: space-between;
            padding: 2px 0;
            gap: 12px;
        }}

        .tooltip-label {{
            color: var(--text-secondary);
            flex-shrink: 0;
        }}

        .tooltip-value {{
            font-weight: 500;
        }}

        /* Controls */
        .controls {{
            position: absolute;
            top: 12px;
            left: 12px;
            display: flex;
            gap: 8px;
            z-index: 100;
        }}

        .control-btn {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .control-btn:hover {{
            background: var(--bg-tertiary);
            border-color: var(--accent);
        }}

        .depth-status {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .depth-status .current {{
            color: var(--accent);
            font-weight: 600;
        }}

        .selected-status {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .selected-status .selected-name {{
            color: var(--green);
            font-weight: 500;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .selected-status .none {{
            color: var(--text-muted);
        }}

        .instructions {{
            font-size: 11px;
            color: var(--text-muted);
            padding: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            margin-bottom: 16px;
        }}

        .agent-docs-ranking {{
            max-height: 200px;
            overflow-y: auto;
        }}

        .ranking-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 8px;
            font-size: 11px;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.15s ease;
        }}

        .ranking-item:hover {{
            background: var(--bg-tertiary);
        }}

        .ranking-item .path {{
            color: var(--text-secondary);
            font-family: monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 180px;
        }}

        .ranking-item .tokens {{
            font-weight: 600;
            flex-shrink: 0;
            margin-left: 8px;
        }}

        .copy-btn {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            margin-left: 8px;
        }}

        .copy-btn:hover {{
            background: #2563eb;
        }}

        .copy-btn:active {{
            background: #1d4ed8;
        }}

        .copy-btn.copied {{
            background: #10b981;
        }}

        .toast {{
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #1f2937;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s;
        }}

        .toast.show {{
            opacity: 1;
        }}

        /* View mode toggle */
        .view-toggle {{
            display: flex;
            gap: 0;
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
        }}

        .view-toggle-btn {{
            background: var(--bg-secondary);
            border: none;
            padding: 6px 12px;
            font-size: 12px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .view-toggle-btn:not(:last-child) {{
            border-right: 1px solid var(--border);
        }}

        .view-toggle-btn:hover {{
            background: var(--bg-tertiary);
        }}

        .view-toggle-btn.active {{
            background: var(--accent);
            color: var(--bg-primary);
        }}

        /* Doc type toggle */
        .doc-type-toggle {{
            display: flex;
            gap: 0;
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin-left: 8px;
        }}

        .doc-type-btn {{
            background: var(--bg-secondary);
            border: none;
            padding: 6px 10px;
            font-size: 11px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .doc-type-btn:not(:last-child) {{
            border-right: 1px solid var(--border);
        }}

        .doc-type-btn:hover {{
            background: var(--bg-tertiary);
        }}

        .doc-type-btn.active {{
            background: var(--accent);
            color: var(--bg-primary);
        }}

        /* Path weight mode link styles */
        .link.path-weight-green {{
            stroke: var(--green);
        }}

        .link.path-weight-yellow {{
            stroke: var(--yellow);
        }}

        .link.path-weight-red {{
            stroke: var(--red);
        }}

        /* Dimmed edges in path weight mode */
        .edge.dimmed {{
            opacity: 0.1;
            pointer-events: none;
        }}

        /* Heaviest paths list */
        .heaviest-paths-list {{
            max-height: 250px;
            overflow-y: auto;
        }}

        .heaviest-path-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 8px;
            font-size: 11px;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.15s ease;
        }}

        .heaviest-path-item:hover {{
            background: var(--bg-tertiary);
        }}

        .heaviest-path-item .rank {{
            color: var(--text-muted);
            font-weight: 500;
            margin-right: 8px;
            min-width: 18px;
        }}

        .heaviest-path-item .path {{
            color: var(--text-secondary);
            font-family: monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
            min-width: 0;
        }}

        .heaviest-path-item .tokens {{
            font-weight: 600;
            flex-shrink: 0;
            margin-left: 8px;
        }}

        /* Section headers with copy buttons */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .section-header h2 {{
            margin-bottom: 0;
        }}

        .section-copy-btn {{
            background: var(--accent);
            border: none;
            padding: 4px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            color: var(--bg-primary);
            transition: all 0.15s ease;
        }}

        .section-copy-btn:hover {{
            filter: brightness(1.2);
        }}

        .section-copy-btn.copied {{
            background: var(--green);
        }}

        /* Token threshold settings */
        .token-settings {{
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }}

        .token-settings-title {{
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .threshold-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            font-size: 11px;
        }}

        .threshold-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }}

        .threshold-label {{
            color: var(--text-secondary);
            min-width: 50px;
        }}

        .threshold-input {{
            width: 70px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 3px 6px;
            font-size: 11px;
            color: var(--text-primary);
            text-align: right;
        }}

        .threshold-input:focus {{
            outline: none;
            border-color: var(--accent);
        }}

        .threshold-suffix {{
            color: var(--text-muted);
            font-size: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 3v18M12 7l-4-4M12 7l4-4M12 13l-6-4M12 13l6-4M12 19l-8-4M12 19l8-4"/>
                </svg>
                Claude Tree
            </h1>
            <div class="header-stats" id="header-stats"></div>
        </header>

        <div class="main-content">
            <div class="controls">
                <button class="control-btn" onclick="expandLevel()">Expand Level</button>
                <button class="control-btn" onclick="collapseLevel()">Collapse Level</button>
                <button class="control-btn" onclick="resetView()">Reset</button>
                <button class="control-btn" onclick="fitToView()">Fit</button>
                <div class="view-toggle" id="view-toggle" style="display: none;">
                    <button class="view-toggle-btn active" data-mode="reference" onclick="setViewMode('reference')">Reference View</button>
                    <button class="view-toggle-btn" data-mode="path" onclick="setViewMode('path')">Path View</button>
                </div>
                <div class="doc-type-toggle" id="doc-type-toggle">
                    <button class="doc-type-btn active" data-type="all" onclick="setDocTypeFilter('all')">All</button>
                    <button class="doc-type-btn" data-type="claude" onclick="setDocTypeFilter('claude')">CLAUDE.md</button>
                    <button class="doc-type-btn" data-type="agents" onclick="setDocTypeFilter('agents')">AGENTS.md</button>
                </div>
                <span class="depth-status" id="depth-status">Depth: 2 / -</span>
                <span class="selected-status" id="selected-status">Selected: None</span>
            </div>
            <div class="tree-container">
                <svg id="tree">
                    <defs>
                        <marker id="arrow-agent-doc" viewBox="0 0 10 10" refX="10" refY="5"
                                markerWidth="6" markerHeight="6" orient="auto">
                            <path d="M 0 0 L 10 5 L 0 10 z" fill="#58a6ff"/>
                        </marker>
                        <marker id="arrow-file" viewBox="0 0 10 10" refX="10" refY="5"
                                markerWidth="6" markerHeight="6" orient="auto">
                            <path d="M 0 0 L 10 5 L 0 10 z" fill="#d4a72c"/>
                        </marker>
                        <marker id="arrow-directory" viewBox="0 0 10 10" refX="10" refY="5"
                                markerWidth="6" markerHeight="6" orient="auto">
                            <path d="M 0 0 L 10 5 L 0 10 z" fill="#a371f7"/>
                        </marker>
                    </defs>
                </svg>
            </div>
        </div>

        <div class="sidebar">
            <div class="sidebar-section">
                <h2>Legend</h2>
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--green)"></div>
                    <span id="legend-green-label">&lt; 1,000 tokens</span>
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--yellow)"></div>
                    <span id="legend-yellow-label">1,000 - 2,000 tokens</span>
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--red)"></div>
                    <span id="legend-red-label">≥ 2,000 tokens</span>
                </div>
                <div class="legend-item" style="margin-top: 12px;">
                    <div class="legend-dot" style="background: var(--bg-tertiary); border: 1px solid var(--border)"></div>
                    <span>Directory</span>
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background: var(--text-muted)"></div>
                    <span>Regular file</span>
                </div>
                <div class="legend-item" style="margin-top: 12px;">
                    <div class="legend-line" style="background: var(--edge-agent-doc)"></div>
                    <span>Reference to agent doc</span>
                </div>
                <div class="legend-item">
                    <div class="legend-line dashed" style="background: repeating-linear-gradient(
                        90deg, #d4a72c 0px, #d4a72c 4px, transparent 4px, transparent 8px
                    )"></div>
                    <span>Reference to file</span>
                </div>
                <div class="legend-item">
                    <div class="legend-line" style="background: repeating-linear-gradient(
                        90deg, #a371f7 0px, #a371f7 2px, transparent 2px, transparent 4px
                    )"></div>
                    <span>Reference to directory</span>
                </div>
                <div class="legend-item" style="margin-top: 12px;">
                    <div class="legend-dot" style="background: transparent; border: 3px solid #f0883e; box-shadow: 0 0 4px #f0883e;"></div>
                    <span>Referenced file (highlighted)</span>
                </div>

                <div class="token-settings">
                    <div class="token-settings-title">Token Thresholds</div>
                    <div class="threshold-row">
                        <div class="threshold-dot" style="background: var(--green)"></div>
                        <span class="threshold-label">Green</span>
                        <span>&lt;</span>
                        <input type="number" class="threshold-input" id="threshold-green" value="1000" min="1">
                        <span class="threshold-suffix">tokens</span>
                    </div>
                    <div class="threshold-row">
                        <div class="threshold-dot" style="background: var(--yellow)"></div>
                        <span class="threshold-label">Yellow</span>
                        <span>&lt;</span>
                        <input type="number" class="threshold-input" id="threshold-yellow" value="2000" min="1">
                        <span class="threshold-suffix">tokens</span>
                    </div>
                    <div class="threshold-row">
                        <div class="threshold-dot" style="background: var(--red)"></div>
                        <span class="threshold-label">Red</span>
                        <span>≥</span>
                        <span id="threshold-red-display" style="color: var(--text-secondary);">2000 tokens</span>
                    </div>
                </div>
            </div>

            <div class="sidebar-section">
                <div class="section-header">
                    <h2>Agent Docs by Tokens</h2>
                    <button class="section-copy-btn" onclick="copyAgentDocsReport()" title="Copy markdown report for agents">📋</button>
                </div>
                <div class="agent-docs-ranking" id="agent-docs-ranking"></div>
            </div>

            <div class="sidebar-section" id="heaviest-paths-section" style="display: none;">
                <div class="section-header">
                    <h2>Heaviest Paths</h2>
                    <button class="section-copy-btn" onclick="copyHeaviestPathsReport()" title="Copy markdown report for agents">📋</button>
                </div>
                <div class="instructions">Top directories by cumulative token cost when Claude works there.</div>
                <div class="heaviest-paths-list" id="heaviest-paths-list"></div>
            </div>

            <div class="sidebar-section">
                <div class="section-header">
                    <h2>Agent Walk Simulator</h2>
                    <button class="section-copy-btn" id="copy-context-chain-btn" onclick="copyContextChainReport()" style="display: none;" title="Copy markdown report for agents">📋</button>
                </div>
                <div class="instructions">
                    Click any directory to see cumulative tokens Claude loads when working there.
                </div>
                <div class="path-info" id="path-info">
                    <div class="path-info-title">Selected Path</div>
                    <div class="path-info-path" id="selected-path">Click a directory...</div>
                    <div class="path-info-tokens" id="path-tokens">-</div>
                    <div class="path-info-label">cumulative tokens</div>
                    <div class="path-chain" id="path-chain"></div>
                </div>
            </div>

            <div class="sidebar-section" id="referenced-files-section" style="display: none;">
                <h2>Referenced Files</h2>
                <div class="path-info" id="referenced-files-info">
                    <div class="path-info-title">Selected Agent Doc</div>
                    <div class="path-info-path" id="selected-agent-doc-path">-</div>
                    <div class="referenced-count" id="referenced-count"></div>
                    <div class="path-chain" id="referenced-files-list"></div>
                </div>
            </div>
        </div>
    </div>

    <div class="tooltip" id="tooltip" style="display: none;"></div>
    <div id="toast" class="toast"></div>

    <script>
        // Injected data
        const TREE_DATA = {tree_json};
        const EDGES_DATA = {edges_json};
        const PATH_WEIGHTS_DATA = {path_weights_json};

        // Build lookup maps
        const nodeByPath = new Map();
        const agentDocTokens = new Map();

        function indexTree(node, parentPath = '') {{
            const path = node.path || '.';
            nodeByPath.set(path, node);
            if (node.isAgentDoc) {{
                agentDocTokens.set(path, node.tokens || 0);
            }}
            if (node.children) {{
                node.children.forEach(child => indexTree(child, path));
            }}
        }}

        if (TREE_DATA.tree) {{
            indexTree(TREE_DATA.tree);
        }}

        // Doc type filter state
        let activeDocTypeFilter = 'all';  // 'all', 'claude', or 'agents'

        // Helper to check if a path matches current filter
        function matchesDocTypeFilter(path) {{
            if (activeDocTypeFilter === 'all') return true;
            const filename = path.split('/').pop().toLowerCase();
            if (activeDocTypeFilter === 'claude') {{
                return filename === 'claude.md';
            }}
            if (activeDocTypeFilter === 'agents') {{
                return filename === 'agents.md';
            }}
            return true;
        }}

        // Set doc type filter
        function setDocTypeFilter(filterType) {{
            activeDocTypeFilter = filterType;

            // Update toggle buttons
            document.querySelectorAll('.doc-type-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.type === filterType);
            }});

            // Re-render everything that uses agent doc data
            updateLinkColors();
            renderAgentDocsRanking();
            renderHeaviestPaths();
            updateHeaderStats();

            // Update sidebar if path selected
            if (selectedPath) {{
                selectPath(selectedPath);
            }}
        }}

        // Calculate cumulative tokens for a path
        function getCumulativeTokens(path) {{
            const parts = path === '.' ? ['.'] : path.split('/');
            let total = 0;
            const breakdown = [];

            // Check root first (respect filter)
            for (const docName of ['CLAUDE.md', 'AGENTS.md']) {{
                const rootPaths = [`./${{docName}}`, docName];
                for (const rootPath of rootPaths) {{
                    if (agentDocTokens.has(rootPath) && matchesDocTypeFilter(rootPath)) {{
                        const tokens = agentDocTokens.get(rootPath);
                        total += tokens;
                        breakdown.push({{ file: rootPath, tokens }});
                        break;
                    }}
                }}
            }}

            // Walk down the path
            let currentPath = '.';
            for (let i = 0; i < parts.length; i++) {{
                if (parts[i] === '.') continue;
                currentPath = currentPath === '.' ? parts[i] : currentPath + '/' + parts[i];

                // Check for agent docs in this directory (respect filter)
                const claudePath = currentPath + '/CLAUDE.md';
                const agentsPath = currentPath + '/AGENTS.md';

                if (agentDocTokens.has(claudePath) && matchesDocTypeFilter(claudePath)) {{
                    const tokens = agentDocTokens.get(claudePath);
                    total += tokens;
                    breakdown.push({{ file: claudePath, tokens }});
                }}
                if (agentDocTokens.has(agentsPath) && matchesDocTypeFilter(agentsPath)) {{
                    const tokens = agentDocTokens.get(agentsPath);
                    total += tokens;
                    breakdown.push({{ file: agentsPath, tokens }});
                }}
            }}

            return {{ total, breakdown }};
        }}

        // Global threshold state with defaults
        let tokenThresholds = {{
            green: 1000,
            yellow: 2000
        }};

        // Unified color function used by BOTH agent docs and path weights
        function getTokenColor(tokens) {{
            if (tokens < tokenThresholds.green) return 'var(--green)';
            if (tokens < tokenThresholds.yellow) return 'var(--yellow)';
            return 'var(--red)';
        }}

        // Get status text based on token count
        function getTokenStatus(tokens) {{
            if (tokens < tokenThresholds.green) return '✅ OK';
            if (tokens < tokenThresholds.yellow) return '⚠️ Warning';
            return '🔴 High';
        }}

        // Update legend labels based on thresholds
        function updateLegendLabels() {{
            document.getElementById('legend-green-label').textContent = `< ${{tokenThresholds.green.toLocaleString()}} tokens`;
            document.getElementById('legend-yellow-label').textContent = `${{tokenThresholds.green.toLocaleString()}} - ${{tokenThresholds.yellow.toLocaleString()}} tokens`;
            document.getElementById('legend-red-label').textContent = `≥ ${{tokenThresholds.yellow.toLocaleString()}} tokens`;
            document.getElementById('threshold-red-display').textContent = `${{tokenThresholds.yellow.toLocaleString()}} tokens`;
        }}

        // When thresholds change, re-render everything that uses colors
        function updateThresholds() {{
            // Get values from inputs
            const greenInput = document.getElementById('threshold-green');
            const yellowInput = document.getElementById('threshold-yellow');

            const greenVal = parseInt(greenInput.value) || 500;
            const yellowVal = parseInt(yellowInput.value) || 1500;

            // Ensure green < yellow
            if (greenVal >= yellowVal) {{
                // Auto-adjust yellow to be higher than green
                yellowInput.value = greenVal + 100;
            }}

            tokenThresholds.green = parseInt(greenInput.value) || 500;
            tokenThresholds.yellow = parseInt(yellowInput.value) || 1500;

            // Update legend labels
            updateLegendLabels();

            // Re-color agent doc nodes
            if (g) {{
                g.selectAll('g.node.agent-doc circle')
                    .style('fill', d => getTokenColor(d.data.tokens || 0));
            }}

            // Re-color path weight links (if in path view)
            updateLinkColors();

            // Re-color sidebar rankings
            renderAgentDocsRanking();
            renderHeaviestPaths();

            // Re-color the path info if a path is selected
            if (selectedPath) {{
                const {{ total, breakdown }} = getCumulativeTokens(selectedPath);
                const tokensEl = document.getElementById('path-tokens');
                tokensEl.style.color = getTokenColor(total);

                const chainEl = document.getElementById('path-chain');
                if (breakdown.length > 0) {{
                    chainEl.innerHTML = breakdown.map(item => `
                        <div class="path-chain-item">
                            <span class="file">${{item.file}}</span>
                            <span class="tokens" style="color: ${{getTokenColor(item.tokens)}}">${{item.tokens}}</span>
                        </div>
                    `).join('');
                }}
            }}
        }}

        // Toast notification helper
        function showToast(message) {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 2000);
        }}

        // Copy to clipboard helper
        async function copyToClipboard(text) {{
            try {{
                await navigator.clipboard.writeText(text);
                return true;
            }} catch (err) {{
                console.error('Failed to copy:', err);
                return false;
            }}
        }}

        // Copy context chain report for selected directory
        function copyContextChainReport() {{
            if (!selectedPath) return;

            const {{ total, breakdown }} = getCumulativeTokens(selectedPath);

            let md = `## Context Chain: \`${{selectedPath}}\`\\n\\n`;
            md += `When Claude works in this directory, these instruction files load:\\n\\n`;
            md += `| File | Tokens |\\n`;
            md += `|------|--------|\\n`;

            breakdown.forEach(item => {{
                md += `| \`${{item.file}}\` | ${{item.tokens.toLocaleString()}} |\\n`;
            }});

            md += `\\n**Total context cost: ${{total.toLocaleString()}} tokens**\\n`;

            copyToClipboard(md).then(success => {{
                const btn = document.getElementById('copy-context-chain-btn');
                if (success) {{
                    btn.classList.add('copied');
                    btn.textContent = '✓';
                    setTimeout(() => {{
                        btn.classList.remove('copied');
                        btn.textContent = '📋';
                    }}, 2000);
                }}
                showToast(success ? 'Context chain copied!' : 'Failed to copy');
            }});
        }}

        // Copy agent docs report
        function copyAgentDocsReport() {{
            const sortedDocs = Array.from(agentDocTokens.entries())
                .sort((a, b) => b[1] - a[1]);

            let md = `## Agent Docs by Token Count\\n\\n`;
            md += `| File | Tokens | Status |\\n`;
            md += `|------|--------|--------|\\n`;

            sortedDocs.forEach(([path, tokens]) => {{
                const status = getTokenStatus(tokens);
                md += `| \`${{path}}\` | ${{tokens.toLocaleString()}} | ${{status}} |\\n`;
            }});

            md += `\\n**Thresholds:** Green < ${{tokenThresholds.green.toLocaleString()}}, Yellow < ${{tokenThresholds.yellow.toLocaleString()}}, Red ≥ ${{tokenThresholds.yellow.toLocaleString()}}\\n`;

            copyToClipboard(md).then(success => {{
                showToast(success ? 'Agent docs report copied!' : 'Failed to copy');
            }});
        }}

        // Copy heaviest paths report
        function copyHeaviestPathsReport() {{
            if (!PATH_WEIGHTS_DATA || !PATH_WEIGHTS_DATA.ranking) return;

            const topPaths = PATH_WEIGHTS_DATA.ranking.slice(0, 10);

            let md = `## Heaviest Paths (Cumulative Tokens)\\n\\n`;
            md += `| Rank | Path | Cumulative Tokens | Status |\\n`;
            md += `|------|------|-------------------|--------|\\n`;

            topPaths.forEach((item, index) => {{
                const status = getTokenStatus(item.cumulativeTokens);
                md += `| ${{index + 1}} | \`${{item.path}}/\` | ${{item.cumulativeTokens.toLocaleString()}} | ${{status}} |\\n`;
            }});

            md += `\\nThese paths have the highest context cost when Claude works in them.\\n`;

            copyToClipboard(md).then(success => {{
                showToast(success ? 'Heaviest paths report copied!' : 'Failed to copy');
            }});
        }}

        // Copy token budget report
        function copyTokenBudgetReport() {{
            const budget = 1500;
            const sortedDocs = Array.from(agentDocTokens.entries())
                .sort((a, b) => b[1] - a[1]);
            const overBudget = sortedDocs.filter(([path, tokens]) => tokens > budget);
            const totalTokens = sortedDocs.reduce((sum, [path, tokens]) => sum + tokens, 0);

            let md = `## Token Budget Report\\n\\n`;
            md += `Generated: ${{new Date().toISOString().split('T')[0]}}\\n\\n`;
            md += `### Summary\\n`;
            md += `- **Total agent docs:** ${{sortedDocs.length}}\\n`;
            md += `- **Total tokens:** ${{totalTokens.toLocaleString()}}\\n`;
            md += `- **Files over budget (>${{budget}}):** ${{overBudget.length}}\\n\\n`;

            if (overBudget.length > 0) {{
                md += `### Files Exceeding Budget\\n\\n`;
                md += `| File | Tokens | Over By |\\n`;
                md += `|------|--------|---------|\\n`;

                overBudget.forEach(([path, tokens]) => {{
                    const overBy = tokens - budget;
                    const ratio = (tokens / budget).toFixed(1);
                    md += `| \`${{path}}\` | ${{tokens.toLocaleString()}} | +${{overBy.toLocaleString()}} (${{ratio}}x) |\\n`;
                }});

                md += `\\n### Recommended Actions\\n\\n`;
                md += `1. **Split large files** - Break files >3000 tokens into subdirectory-specific docs\\n`;
                md += `2. **Extract shared content** - Move repeated patterns to a shared doc referenced via links\\n`;
                md += `3. **Use links over duplication** - Reference other docs with \`See [topic](./path/CLAUDE.md)\`\\n\\n`;
            }}

            md += `### All Agent Docs by Token Count\\n\\n`;
            md += `| File | Tokens | Status |\\n`;
            md += `|------|--------|--------|\\n`;

            sortedDocs.forEach(([path, tokens]) => {{
                const status = tokens > budget ? 'Over' : tokens > 500 ? 'Warning' : 'OK';
                md += `| \`${{path}}\` | ${{tokens.toLocaleString()}} | ${{status}} |\\n`;
            }});

            copyToClipboard(md).then(success => {{
                showToast(success ? 'Budget report copied!' : 'Failed to copy');
            }});
        }}

        // Render header stats
        function renderHeaderStats() {{
            updateHeaderStats();
        }}

        // Update header stats (respects doc type filter)
        function updateHeaderStats() {{
            const el = document.getElementById('header-stats');

            // Calculate filtered stats
            const filteredDocs = Array.from(agentDocTokens.entries())
                .filter(([path, tokens]) => matchesDocTypeFilter(path));
            const totalDocs = filteredDocs.length;
            const totalTokens = filteredDocs.reduce((sum, [path, tokens]) => sum + tokens, 0);
            const edgeCount = EDGES_DATA.edges?.length || 0;

            // Show filter indicator if not showing all
            const filterLabel = activeDocTypeFilter === 'all' ? '' : ` (${{activeDocTypeFilter === 'claude' ? 'CLAUDE.md' : 'AGENTS.md'}})`;

            el.innerHTML = `
                <div class="header-stat">
                    <span class="header-stat-value">${{totalDocs}}</span>
                    <span class="header-stat-label">agent docs${{filterLabel}}</span>
                </div>
                <div class="header-stat">
                    <span class="header-stat-value">${{totalTokens.toLocaleString()}}</span>
                    <span class="header-stat-label">total tokens</span>
                </div>
                <div class="header-stat">
                    <span class="header-stat-value">${{edgeCount}}</span>
                    <span class="header-stat-label">references</span>
                </div>
            `;
        }}

        // View mode state
        let currentViewMode = 'reference';

        // Path weight helper functions - use unified color system
        function getPathWeightColor(cumulativeTokens) {{
            // Use the same unified getTokenColor function with user-configurable thresholds
            return getTokenColor(cumulativeTokens);
        }}

        function getPathWeightStrokeWidth(cumulativeTokens) {{
            const maxWeight = PATH_WEIGHTS_DATA?.metadata?.maxPathWeight || 1;
            const ratio = cumulativeTokens / maxWeight;
            return 1 + ratio * 2; // 1-3px
        }}

        function setViewMode(mode) {{
            currentViewMode = mode;

            // Update toggle buttons
            document.querySelectorAll('.view-toggle-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.mode === mode);
            }});

            // Update link colors and edge visibility
            updateLinkColors();
            updateEdgeVisibility();
        }}

        function updateLinkColors() {{
            if (!g) return;

            // Reset all link styles first
            g.selectAll('path.link')
                .style('stroke', null)
                .style('stroke-width', null);

            // In path view, color links by cumulative tokens (respecting filter)
            if (currentViewMode === 'path' && PATH_WEIGHTS_DATA) {{
                // Recalculate max weight for current filter
                let maxFilteredWeight = 0;
                Object.keys(PATH_WEIGHTS_DATA.pathWeights).forEach(path => {{
                    const {{ total }} = getCumulativeTokens(path);
                    if (total > maxFilteredWeight) maxFilteredWeight = total;
                }});

                g.selectAll('path.link').each(function(d) {{
                    const targetPath = d.target.data.path;
                    // Recalculate tokens with current filter
                    const {{ total: cumulativeTokens }} = getCumulativeTokens(targetPath);

                    if (cumulativeTokens > 0) {{
                        const color = getPathWeightColor(cumulativeTokens);
                        // Calculate width based on filtered max
                        const ratio = maxFilteredWeight > 0 ? cumulativeTokens / maxFilteredWeight : 0;
                        const width = 1 + ratio * 2; // 1-3px
                        d3.select(this)
                            .style('stroke', color)
                            .style('stroke-width', width + 'px');
                    }}
                }});
            }}
        }}

        function updateEdgeVisibility() {{
            if (!g) return;

            // In path view, dim reference edges significantly
            // In reference view, show them normally
            g.selectAll('.edge')
                .classed('dimmed', currentViewMode === 'path');
        }}

        function renderHeaviestPaths() {{
            const section = document.getElementById('heaviest-paths-section');
            const container = document.getElementById('heaviest-paths-list');

            if (!PATH_WEIGHTS_DATA || !PATH_WEIGHTS_DATA.ranking || PATH_WEIGHTS_DATA.ranking.length === 0) {{
                section.style.display = 'none';
                return;
            }}

            section.style.display = 'block';

            // Recalculate path weights based on current filter
            const recalculatedPaths = PATH_WEIGHTS_DATA.ranking.map(item => {{
                const {{ total }} = getCumulativeTokens(item.path);
                return {{ path: item.path, cumulativeTokens: total }};
            }}).filter(item => item.cumulativeTokens > 0)
              .sort((a, b) => b.cumulativeTokens - a.cumulativeTokens);

            if (recalculatedPaths.length === 0) {{
                const filterMsg = activeDocTypeFilter === 'all'
                    ? 'No paths with agent docs'
                    : `No paths with ${{activeDocTypeFilter === 'claude' ? 'CLAUDE.md' : 'AGENTS.md'}} files`;
                container.innerHTML = `<div style="color: var(--text-muted); font-size: 11px; padding: 8px;">${{filterMsg}}</div>`;
                return;
            }}

            // Show top 10 paths
            const topPaths = recalculatedPaths.slice(0, 10);

            container.innerHTML = topPaths.map((item, index) => `
                <div class="heaviest-path-item" data-path="${{item.path}}">
                    <span class="rank">${{index + 1}}.</span>
                    <span class="path" title="${{item.path}}">${{item.path}}/</span>
                    <span class="tokens" style="color: ${{getPathWeightColor(item.cumulativeTokens)}}">${{item.cumulativeTokens.toLocaleString()}}</span>
                </div>
            `).join('');

            // Add click handlers
            container.querySelectorAll('.heaviest-path-item').forEach(item => {{
                item.addEventListener('click', () => {{
                    const path = item.dataset.path;
                    expandToPath(path + '/dummy'); // Add dummy to expand the target dir
                    selectPath(path);
                }});
            }});
        }}

        // D3 Tree Visualization
        let root, svg, g, treeLayout;
        let selectedPath = null;
        let selectedAgentDoc = null;
        let initialRenderComplete = false;

        // Depth tracking for level-by-level expand/collapse
        let maxTreeDepth = 0;
        let currentVisibleDepth = 2;

        // Calculate max depth from tree data
        function calculateMaxDepth(node, depth = 0) {{
            maxTreeDepth = Math.max(maxTreeDepth, depth);
            if (node.children) {{
                node.children.forEach(child => calculateMaxDepth(child, depth + 1));
            }}
        }}

        // Update depth display in controls
        function updateDepthDisplay() {{
            // Update depth
            const depthEl = document.getElementById('depth-status');
            depthEl.innerHTML = `Depth: <span class="current">${{currentVisibleDepth}}</span> / ${{maxTreeDepth}}`;

            // Update selected agent doc
            const selectedEl = document.getElementById('selected-status');
            if (selectedAgentDoc) {{
                const name = selectedAgentDoc.split('/').pop();
                selectedEl.innerHTML = `Selected: <span class="selected-name" title="${{selectedAgentDoc}}">${{name}}</span>`;
            }} else {{
                selectedEl.innerHTML = `Selected: <span class="none">None</span>`;
            }}
        }}

        // Expand one more level
        function expandLevel() {{
            if (currentVisibleDepth >= maxTreeDepth) return;
            currentVisibleDepth++;

            root.descendants().forEach(d => {{
                // Expand nodes at the new visible depth - 1 (their children become visible)
                if (d.depth === currentVisibleDepth - 1 && d._children) {{
                    d.children = d._children;
                    d._children = null;
                }}
            }});

            update(root);
            renderEdges();
            updateEdgeVisibility();
            updateDepthDisplay();
        }}

        // Collapse one level
        function collapseLevel() {{
            if (currentVisibleDepth <= 1) return;

            root.descendants().forEach(d => {{
                // Collapse nodes at the current visible depth - 1 (hide their children)
                if (d.depth === currentVisibleDepth - 1 && d.children) {{
                    d._children = d.children;
                    d.children = null;
                }}
            }});

            currentVisibleDepth--;
            update(root);
            renderEdges();
            updateEdgeVisibility();
            updateDepthDisplay();
        }}

        function initTree() {{
            const treeData = TREE_DATA.tree;
            if (!treeData) return;

            // Calculate max depth for level controls
            calculateMaxDepth(treeData);

            const container = document.querySelector('.tree-container');
            const margin = {{ top: 20, right: 120, bottom: 20, left: 80 }};
            const width = Math.max(800, container.clientWidth);

            svg = d3.select('#tree')
                .attr('width', '100%')
                .attr('height', '100%');

            g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);

            // Add zoom behavior
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .translateExtent([[-Infinity, -Infinity], [Infinity, Infinity]])
                .on('zoom', (event) => {{
                    g.attr('transform', event.transform);
                }});

            svg.call(zoom);

            // Store zoom reference for fitToView
            window.zoomBehavior = zoom;

            // Create hierarchy
            root = d3.hierarchy(treeData);
            root.x0 = 0;
            root.y0 = 0;

            // Initially collapse some nodes (depth > currentVisibleDepth)
            root.descendants().forEach((d, i) => {{
                if (d.depth >= currentVisibleDepth && d.children) {{
                    d._children = d.children;
                    d.children = null;
                }}
            }});

            treeLayout = d3.tree().nodeSize([24, 180]);

            update(root);
            renderEdges();
            updateEdgeVisibility();
            updateDepthDisplay();
        }}

        function update(source) {{
            const duration = 250;

            // Compute new tree layout
            treeLayout(root);

            // Get all nodes
            const nodes = root.descendants();
            const links = root.links();

            // Normalize for fixed-depth
            nodes.forEach(d => {{
                d.y = d.depth * 180;
            }});

            // Calculate bounds - only set initial position on first render
            if (!initialRenderComplete) {{
                let minX = Infinity;
                nodes.forEach(d => {{
                    if (d.x < minX) minX = d.x;
                }});
                g.attr('transform', `translate(80,${{-minX + 20}})`);
                initialRenderComplete = true;
            }}

            // Update nodes
            const node = g.selectAll('g.node')
                .data(nodes, d => d.data.path);

            // Enter new nodes
            const nodeEnter = node.enter().append('g')
                .attr('class', d => {{
                    let classes = 'node';
                    if (d.data.type === 'directory') classes += ' directory';
                    else classes += ' file';
                    if (d.data.isAgentDoc) classes += ' agent-doc';
                    if (d._children) classes += ' collapsed';
                    return classes;
                }})
                .attr('transform', d => `translate(${{source.y0}},${{source.x0}})`)
                .on('click', (event, d) => {{
                    event.stopPropagation();
                    // Single click = select for random walk
                    if (d.data.type === 'directory') {{
                        selectPath(d.data.path);
                    }} else if (d.data.isAgentDoc) {{
                        if (selectedAgentDoc === d.data.path) {{
                            clearAllHighlighting();  // Deselect if already selected
                        }} else {{
                            selectAgentDoc(d.data.path);
                        }}
                    }}
                }})
                .on('dblclick', (event, d) => {{
                    event.stopPropagation();
                    // Double click = toggle expand/collapse (directories only)
                    if (d.data.type === 'directory') {{
                        if (d.children) {{
                            d._children = d.children;
                            d.children = null;
                        }} else if (d._children) {{
                            d.children = d._children;
                            d._children = null;
                        }}
                        update(d);
                        renderEdges();
                        updateEdgeVisibility();
                    }}
                }})
                .on('mouseover', showTooltip)
                .on('mouseout', hideTooltip);

            nodeEnter.append('circle')
                .attr('r', d => d.data.isAgentDoc ? 7 : (d.data.type === 'directory' ? 5 : 4))
                .style('fill', d => {{
                    if (d.data.isAgentDoc) {{
                        return getTokenColor(d.data.tokens || 0);
                    }}
                    return d.data.type === 'directory' ? 'var(--bg-tertiary)' : 'var(--text-muted)';
                }});

            nodeEnter.append('text')
                .attr('dy', 3)
                .attr('x', d => d.children || d._children ? -12 : 12)
                .attr('text-anchor', d => d.children || d._children ? 'end' : 'start')
                .text(d => d.data.type === 'directory' ? d.data.name + '/' : d.data.name);

            // Update existing nodes
            const nodeUpdate = nodeEnter.merge(node);

            nodeUpdate.transition()
                .duration(duration)
                .attr('transform', d => `translate(${{d.y}},${{d.x}})`);

            nodeUpdate.attr('class', d => {{
                let classes = 'node';
                if (d.data.type === 'directory') classes += ' directory';
                else classes += ' file';
                if (d.data.isAgentDoc) classes += ' agent-doc';
                if (d._children) classes += ' collapsed';
                return classes;
            }});

            // Update circle fill colors for all nodes (not just new ones)
            // Use .style() instead of .attr() for higher CSS specificity
            nodeUpdate.select('circle')
                .style('fill', d => {{
                    if (d.data.isAgentDoc) {{
                        return getTokenColor(d.data.tokens || 0);
                    }}
                    return d.data.type === 'directory' ? 'var(--bg-tertiary)' : 'var(--text-muted)';
                }});

            // Remove old nodes
            node.exit().transition()
                .duration(duration)
                .attr('transform', d => `translate(${{source.y}},${{source.x}})`)
                .remove();

            // Update links
            const link = g.selectAll('path.link')
                .data(links, d => d.target.data.path);

            const linkEnter = link.enter().insert('path', 'g')
                .attr('class', 'link')
                .attr('d', d => {{
                    const o = {{ x: source.x0, y: source.y0 }};
                    return diagonal(o, o);
                }});

            linkEnter.merge(link).transition()
                .duration(duration)
                .attr('d', d => diagonal(d.source, d.target));

            link.exit().transition()
                .duration(duration)
                .attr('d', d => {{
                    const o = {{ x: source.x, y: source.y }};
                    return diagonal(o, o);
                }})
                .remove();

            // Store positions for next update
            nodes.forEach(d => {{
                d.x0 = d.x;
                d.y0 = d.y;
            }});
        }}

        function diagonal(s, d) {{
            return `M ${{s.y}} ${{s.x}}
                    C ${{(s.y + d.y) / 2}} ${{s.x}},
                      ${{(s.y + d.y) / 2}} ${{d.x}},
                      ${{d.y}} ${{d.x}}`;
        }}

        // Render reference edges
        function renderEdges() {{
            // Remove existing edges
            g.selectAll('.edge').remove();

            const edges = EDGES_DATA.edges || [];
            if (edges.length === 0) return;

            // Get visible nodes and their positions
            const visibleNodes = new Map();
            root.descendants().forEach(d => {{
                visibleNodes.set(d.data.path, {{ x: d.x, y: d.y }});
            }});

            // Draw edges
            edges.forEach(edge => {{
                const sourcePos = visibleNodes.get(edge.source);
                const targetPos = visibleNodes.get(edge.target);

                if (sourcePos && targetPos) {{
                    const path = g.append('path')
                        .attr('class', `edge ${{edge.type}}`)
                        .attr('d', `M ${{sourcePos.y + 8}} ${{sourcePos.x}}
                                   Q ${{(sourcePos.y + targetPos.y) / 2 + 50}} ${{(sourcePos.x + targetPos.x) / 2}},
                                     ${{targetPos.y - 12}} ${{targetPos.x}}`)
                        .attr('marker-end', `url(#arrow-${{edge.type}})`)
                        .attr('data-source', edge.source)
                        .attr('data-target', edge.target);

                    // Add tooltip on hover
                    path.on('mouseover', (event) => {{
                        const tooltip = document.getElementById('tooltip');
                        tooltip.innerHTML = `
                            <div class="tooltip-title">Reference</div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">From</span>
                                <span class="tooltip-value" style="word-break: break-all">${{edge.source}}</span>
                            </div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">To</span>
                                <span class="tooltip-value" style="word-break: break-all">${{edge.target}}</span>
                            </div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">Type</span>
                                <span class="tooltip-value">${{edge.type === 'agent-doc' ? 'Agent doc' : edge.type === 'directory' ? 'Directory' : 'File'}}</span>
                            </div>
                        `;
                        tooltip.style.display = 'block';
                        tooltip.style.left = (event.pageX + 12) + 'px';
                        tooltip.style.top = (event.pageY - 10) + 'px';
                    }})
                    .on('mouseout', hideTooltip);
                }}
            }});
        }}

        // Path selection
        function selectPath(path) {{
            selectedPath = path;

            // Highlight path in tree
            root.descendants().forEach(d => {{
                d.highlighted = false;
            }});

            // Highlight ancestors
            let current = root.descendants().find(d => d.data.path === path);
            while (current) {{
                current.highlighted = true;
                current = current.parent;
            }}

            // Update node classes
            g.selectAll('g.node')
                .classed('highlighted', d => d.highlighted)
                .classed('selected', d => d.data.path === path);

            g.selectAll('path.link')
                .classed('highlighted', d => d.target.highlighted);

            // Update sidebar
            const pathEl = document.getElementById('selected-path');
            const tokensEl = document.getElementById('path-tokens');
            const chainEl = document.getElementById('path-chain');

            pathEl.textContent = path === '.' ? (TREE_DATA.tree?.name || '(root)') : path;

            const {{ total, breakdown }} = getCumulativeTokens(path);
            tokensEl.textContent = total.toLocaleString();
            tokensEl.style.color = getTokenColor(total);

            if (breakdown.length > 0) {{
                chainEl.innerHTML = breakdown.map(item => `
                    <div class="path-chain-item">
                        <span class="file">${{item.file}}</span>
                        <span class="tokens" style="color: ${{getTokenColor(item.tokens)}}">${{item.tokens}}</span>
                    </div>
                `).join('');
            }} else {{
                chainEl.innerHTML = '<div style="color: var(--text-muted); font-size: 11px;">No agent docs in path</div>';
            }}

            // Show/hide copy context chain button (in section header)
            const copyBtn = document.getElementById('copy-context-chain-btn');
            copyBtn.style.display = breakdown.length > 0 ? 'inline-block' : 'none';
            copyBtn.textContent = '📋';  // Reset button text
            copyBtn.classList.remove('copied');
        }}

        // Clear all highlighting
        function clearAllHighlighting() {{
            selectedAgentDoc = null;
            g.selectAll('g.node').classed('referenced', false);
            g.selectAll('.edge').classed('highlighted-edge', false);
            document.getElementById('referenced-files-section').style.display = 'none';
            updateDepthDisplay();
        }}

        // Select agent doc and highlight referenced files
        function selectAgentDoc(path) {{
            // Clear previous highlighting
            clearAllHighlighting();

            selectedAgentDoc = path;
            updateDepthDisplay();
            const edges = EDGES_DATA.edges || [];

            // Find all edges from this agent doc
            const referencedPaths = edges
                .filter(e => e.source === path)
                .map(e => e.target);

            if (referencedPaths.length === 0) {{
                // No references, just select the parent directory for random walk
                const node = root.descendants().find(d => d.data.path === path);
                if (node && node.parent) {{
                    selectPath(node.parent.data.path);
                }}
                return;
            }}

            // Highlight referenced nodes
            g.selectAll('g.node')
                .classed('referenced', d => referencedPaths.includes(d.data.path));

            // Highlight edges from this agent doc
            g.selectAll('.edge')
                .classed('highlighted-edge', function() {{
                    return d3.select(this).attr('data-source') === path;
                }});

            // Update sidebar
            const section = document.getElementById('referenced-files-section');
            const pathEl = document.getElementById('selected-agent-doc-path');
            const countEl = document.getElementById('referenced-count');
            const listEl = document.getElementById('referenced-files-list');

            section.style.display = 'block';
            pathEl.textContent = path;
            countEl.innerHTML = `<span style="color: var(--accent); font-weight: 600;">${{referencedPaths.length}}</span> <span style="color: var(--text-secondary);">referenced files</span>`;

            listEl.innerHTML = referencedPaths.map(refPath => `
                <div class="path-chain-item">
                    <span class="file">${{refPath}}</span>
                </div>
            `).join('');
        }}

        // Expand tree to a specific path
        function expandToPath(path) {{
            const parts = path.split('/');
            let currentPath = '';

            for (let i = 0; i < parts.length - 1; i++) {{
                currentPath = currentPath ? currentPath + '/' + parts[i] : parts[i];
                const node = root.descendants().find(d => d.data.path === currentPath);
                if (node && node._children) {{
                    node.children = node._children;
                    node._children = null;
                }}
            }}

            update(root);
            renderEdges();
            updateEdgeVisibility();
        }}

        // Render agent docs ranking
        function renderAgentDocsRanking() {{
            const container = document.getElementById('agent-docs-ranking');

            // Get all agent docs and sort by token count descending, filtered by doc type
            const sortedDocs = Array.from(agentDocTokens.entries())
                .filter(([path, tokens]) => matchesDocTypeFilter(path))
                .sort((a, b) => b[1] - a[1]);

            if (sortedDocs.length === 0) {{
                const filterMsg = activeDocTypeFilter === 'all'
                    ? 'No agent docs found'
                    : `No ${{activeDocTypeFilter === 'claude' ? 'CLAUDE.md' : 'AGENTS.md'}} files found`;
                container.innerHTML = `<div style="color: var(--text-muted); font-size: 11px; padding: 8px;">${{filterMsg}}</div>`;
                return;
            }}

            container.innerHTML = sortedDocs.map(([path, tokens]) => `
                <div class="ranking-item" data-path="${{path}}">
                    <span class="path" title="${{path}}">${{path}}</span>
                    <span class="tokens" style="color: ${{getTokenColor(tokens)}}">${{tokens.toLocaleString()}}</span>
                </div>
            `).join('');

            // Add click handlers
            container.querySelectorAll('.ranking-item').forEach(item => {{
                item.addEventListener('click', () => {{
                    const path = item.dataset.path;
                    expandToPath(path);
                    selectAgentDoc(path);
                }});
            }});
        }}

        // Tooltip
        function showTooltip(event, d) {{
            const tooltip = document.getElementById('tooltip');

            let content = `<div class="tooltip-title">${{d.data.path}}</div>`;

            if (d.data.isAgentDoc) {{
                content += `
                    <div class="tooltip-row">
                        <span class="tooltip-label">Tokens</span>
                        <span class="tooltip-value" style="color: ${{getTokenColor(d.data.tokens || 0)}}">${{(d.data.tokens || 0).toLocaleString()}}</span>
                    </div>
                `;
            }} else if (d.data.type === 'directory') {{
                const childCount = (d.children || d._children || []).length;
                content += `
                    <div class="tooltip-row">
                        <span class="tooltip-label">Children</span>
                        <span class="tooltip-value">${{childCount}}</span>
                    </div>
                `;
                if (d._children) {{
                    content += `<div style="color: var(--text-muted); font-size: 11px; margin-top: 4px;">Double-click to expand</div>`;
                }}
            }}

            tooltip.innerHTML = content;
            tooltip.style.display = 'block';
            tooltip.style.left = (event.pageX + 12) + 'px';
            tooltip.style.top = (event.pageY - 10) + 'px';
        }}

        function hideTooltip() {{
            document.getElementById('tooltip').style.display = 'none';
        }}

        // Control functions
        function resetView() {{
            // Reset to initial depth
            currentVisibleDepth = 2;

            root.descendants().forEach(d => {{
                if (d._children) {{
                    d.children = d._children;
                    d._children = null;
                }}
                if (d.depth >= currentVisibleDepth && d.children) {{
                    d._children = d.children;
                    d.children = null;
                }}
            }});
            selectedPath = null;
            document.getElementById('selected-path').textContent = 'Click a directory...';
            document.getElementById('path-tokens').textContent = '-';
            document.getElementById('path-tokens').style.color = '';
            document.getElementById('path-chain').innerHTML = '';
            const copyBtn = document.getElementById('copy-context-chain-btn');
            copyBtn.style.display = 'none';
            copyBtn.textContent = '📋';
            copyBtn.classList.remove('copied');
            g.selectAll('g.node').classed('highlighted', false).classed('selected', false);
            g.selectAll('path.link').classed('highlighted', false);
            // Clear agent doc highlighting
            clearAllHighlighting();
            // Reset zoom and allow initial positioning
            svg.transition().duration(500).call(window.zoomBehavior.transform, d3.zoomIdentity);
            initialRenderComplete = false;
            update(root);
            renderEdges();
            updateEdgeVisibility();
            updateDepthDisplay();
        }}

        function fitToView(zoomFactor = 0.9) {{
            const bounds = g.node().getBBox();
            const container = document.querySelector('.tree-container');
            const fullWidth = container.clientWidth;
            const fullHeight = container.clientHeight;
            const scale = Math.min(
                fullWidth / (bounds.width + 40),
                fullHeight / (bounds.height + 40)
            ) * zoomFactor;
            const transform = d3.zoomIdentity
                .translate(fullWidth / 2, fullHeight / 2)
                .scale(scale)
                .translate(-bounds.x - bounds.width / 2, -bounds.y - bounds.height / 2);
            svg.transition().duration(500).call(window.zoomBehavior.transform, transform);
        }}

        // Initialize
        renderHeaderStats();
        initTree();
        // Center tree in viewport on load (more zoomed out)
        setTimeout(() => fitToView(0.175), 100);
        renderAgentDocsRanking();

        // Initialize path weights features if data is available
        if (PATH_WEIGHTS_DATA) {{
            document.getElementById('view-toggle').style.display = 'flex';
            renderHeaviestPaths();
        }}

        // Initialize threshold input listeners
        document.getElementById('threshold-green').addEventListener('input', updateThresholds);
        document.getElementById('threshold-yellow').addEventListener('input', updateThresholds);

        // Initialize legend labels
        updateLegendLabels();

        // Handle window resize
        window.addEventListener('resize', () => {{
            // CSS percentage sizing handles resize automatically
        }});
    </script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive D3.js HTML visualization"
    )
    parser.add_argument(
        "--tree", "-t",
        type=str,
        required=True,
        help="Input tree JSON file from tree.py",
    )
    parser.add_argument(
        "--edges", "-e",
        type=str,
        required=True,
        help="Input edges JSON file from sub-agent analysis",
    )
    parser.add_argument(
        "--path-weights", "-p",
        type=str,
        help="Input path weights JSON file from tree.py (optional)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./claude-tree",
        help="Output directory (default: ./claude-tree)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open visualization in browser",
    )

    args = parser.parse_args()

    # Load input files
    tree_data = load_json(args.tree)
    edges_data = load_json(args.edges)
    path_weights_data = load_json(args.path_weights) if args.path_weights else None

    # Generate HTML
    html = generate_html(tree_data, edges_data, path_weights_data)

    # Create output directory and write file
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "index.html"
    output_file.write_text(html)

    print(f"Visualization written to {output_file}", file=sys.stderr)

    # Open in browser if requested
    if args.open:
        try:
            webbrowser.open(f"file://{output_file.resolve()}")
        except Exception as e:
            print(f"Could not open browser: {e}", file=sys.stderr)
            print(f"Please open manually: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
