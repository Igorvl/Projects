---
title: GitHub Profile Metrics SVG Font Scaling
status: Deferred
priority: Low
---

# Issue: GitHub Profile `lowlighter/metrics` SVG Font Scaling

## State Summary
Currently, the `Igorvl/Igorvl` repository successfully generates a dynamic SVG using the `lowlighter/metrics` GitHub Action. We successfully achieved:
1. **Dark Theme Integration**: Background matches `#0d1117`.
2. **Custom Language Colors**: Python, Shell, PHP, PLpgSQL natively configured to neon colors (`#58a6ff`, `#39d353`, etc).
3. **Grid Context**: 3D contribution grid maps empty cells to `#2d333b` for contrast.
4. **Cache Busting**: Integrated `?v=X` cache buster in `README.md` to bypass GitHub Camo proxy.

**The Remaining Issue (Why deferred):**
The font size of the text within the generated SVG remains unexpectedly large compared to GitHub's native page text.
Despite injecting CSS overrides like `font-size: 12px !important` onto `svg`, `.items-wrapper`, `h2`, and `h3`, the browser scaling or `<foreignObject>` isolation inside an `<img>` tag in markdown prevents the text from visually matching the proportion we desire.

## Detailed History of Changes
1. **Initial implementation**: Swapped out `profile-3d-contrib` for `lowlighter/metrics` to get a 6-month view and language stats.
2. **Color adjustments**: Discovered `[fill="..."]` properties in SVG and overrode them via `extras_css` in `metrics.yml` because standard thematic variables didn't cleanly apply to the `isocalendar` plugin without it.
3. **Font scaling attempts**: 
    - Attempt 1: `svg { font-size: 16px; }` -> Resulted in huge headers because `h2` / `h3` cascaded relatively.
    - Attempt 2: `svg { font-size: 13px !important; }` -> Ignored by HTML `div.items-wrapper` inside the `<foreignObject>`.
    - Attempt 3: `.items-wrapper { font-size: 12px !important; }` and `h2 { font-size: 13px !important; }` -> While the SVG text changed in isolation, the scaling in the GitHub profile UI still appeared visually identical/large. 
4. **Encoding/Cache Bug**: Pushing changes required dealing with GitHub CDN (Camo) aggressively caching `github-metrics.svg`. Bypassing this via `README.md` replacement (`?v=N`) via PowerShell corrupted multibyte emojis, which were subsequently fixed by restoring the file strictly as UTF-8.

## Task Overview for the Future
To ultimately resolve the SVG font size discrepancy:
* **Option A (Investigation):** Determine if `width: 100%` on the `<foreignObject>` or `<svg>` is scaling the text proportionally to fit an 800px width limit in `README.md`, overriding the fixed `px` values. Try setting fixed viewbox constraints or relative `rem` limits.
* **Option B (Template Override):** Explore if `lowlighter/metrics` exposes templates to remove HTML `<div class="items-wrapper">` completely and render raw SVG `<text>` elements which respect explicit CSS dimensions better.
* **Option C (Alternatives):** Accept the layout as-is since the colors and features are correct, or consider writing a custom SVG builder via Python script.
