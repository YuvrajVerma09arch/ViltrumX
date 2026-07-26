# ViltrumX Brand Identity

> The hexagon-shield mark and the "ViltrumX" name are the exclusive property of the project
> owner. See [`../LICENSE`](../LICENSE) — no third-party use without written permission.

## The mark — what it means

The symbol is a **shield inside a hexagon**, and every part of it maps to the product:

| Element | Meaning |
|---|---|
| **Hexagon with node-dots at each vertex** | The Ontology. A hexagon is literally a graph — six nodes joined by six edges. The customer's world as a living digital twin (CLAUDE.md §3) is the actual moat, so it *encloses* everything else in the mark. |
| **Shield** | Governed protection. Defense sits *inside* the ontology — decisions are grounded in the graph, never free-floating scripts. |
| **V chevron** | Viltrum + a "verified" check. Every action is proven (purple-team loop) and every decision is auditable. Carried over from the original favicon for continuity. |
| **Phosphor-green on near-black** | The dark "terminal" theme the whole product ships with. Green is also the "verified / safe / go" signal — fitting for a product whose pitch is *trustworthy* autonomy. |

## Colors (same tokens as `frontend/src/index.css`)

| Token | Hex | Use in the mark |
|---|---|---|
| `--color-bg` | `#0d1117` | Backplate, node fills, shield base |
| `--color-surface-2` | `#1c2432` | Shield gradient top |
| `--color-accent` | `#3fb950` | Shield outline, wordmark "X" |
| `--color-accent-bright` | `#56d364` | Chevron, hexagon gradient top |
| green-dark | `#2ea043` | Hexagon gradient bottom |
| `--color-ink` | `#e6edf3` | Wordmark "VILTRUM" |
| `--color-ink-2` | `#9ba7b4` | Wordmark subline |

## Files

| File | Use |
|---|---|
| `viltrumx-mark.svg` | Primary mark, transparent background — use on dark surfaces (app, slides, README) |
| `viltrumx-app-icon.svg` | Rounded-square backplate — app icon, social avatar, favicon source |
| `viltrumx-mark-mono.svg` | Single color via `currentColor` — print, stamps, light backgrounds |
| `viltrumx-wordmark.svg` | Mark + VILTRUMX + subline — pitch deck headers, doc covers |
| `../frontend/public/favicon.svg` | Simplified mark tuned for 16–32 px |
| `preview.html` | Open in a browser to see all variants at once |

## Usage rules

- **Do** keep the mark on `#0d1117` or a similarly dark surface; use the mono variant on light.
- **Do** keep clear space around the mark of at least the vertex-node diameter.
- **Don't** recolor, rotate, outline, add drop shadows, or remove the vertex nodes.
- **Don't** stretch — the hexagon must stay regular (pointy-top).
- Below 24 px, use the favicon geometry (no vertex nodes) — the nodes clog at small sizes.
