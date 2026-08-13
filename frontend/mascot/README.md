# Portfolio Mascot Assets

Cogni companion assets generated as a clean chroma-key pose sheet, then cropped into transparent PNG/WebP state assets.

Each state folder contains:
- `pose.webp` for the production companion component
- `pose.png` as the transparent PNG source

The generated source sheet is kept as `cogni-source-pose-sheet.png` for future iteration.

Directional head assets live in `head/`:
- `neutral`, `left`, `right`, `up`, `down`, and `blink`
- each has transparent PNG source and production WebP

The generated head source sheet is kept as `head-source-sheet.png`.

Layered body assets live in `body/<state>/`:
- `pose.webp` is the production body-only sprite used under the directional head layer
- `pose.png` is the transparent PNG source

The body/head alignment preview is kept as `body/body-head-preview.png`.
