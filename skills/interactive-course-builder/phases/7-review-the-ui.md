# Phase 7: Review the UI

**Goal:** a clean, purposeful interface that works on phones, tablets and
desktops, free of AI-slop patterns.

**Read:** [UI rules](../references/ui-rules.md). Have the app running with
real data: some progress, a lesson that has been run, a finished experiment.

**Produce:** `course/ui-review.md` from [`templates/ui-review.md`](../templates/ui-review.md) (findings, fixes, final pass) and
screenshots in `course/screenshots/`.

## Checklist

1. [ ] **Screenshot every screen** at **390, 768, 1024, 1280 and 1440 px** wide, in
   dark and light themes: course map, each lesson kind's page (after a run),
   the stack/plugins page, any drawer or palette, sign-in, admin pages. Use a
   headless browser script, and commit it.
2. [ ] **Measure overflow.** For each screenshot, record
   `document.documentElement.scrollWidth - innerWidth`. Anything above 0 is a defect.
3. [ ] **Run the deslop checklist** in [UI rules](../references/ui-rules.md)
   against every screen. Write each finding as: screen, pattern, fix.
4. [ ] **Fix and re-shoot.** Repeat steps 1–3 until a full pass finds nothing.
   Usually this takes two or three rounds.
5. [ ] **Check text.** Every label is sentence case, every empty state is one
   line, there is no repeated explanatory subtitle, and no marketing copy.
6. [ ] **Check interaction.** Keyboard: run with ⌘/Ctrl+Enter, palette with
   ⌘/Ctrl+K, visible focus rings, Escape closes overlays. Touch: no hover-only
   information.
7. [ ] **Record the final pass** in `ui-review.md`: the widths and themes
   covered, zero overflow, and the checklist with every item ticked.

## Exit criteria

- The final round finds no deslop violations and no overflow at any width.
- Screenshots of the final state are committed.
- `python tools/lint_artifacts.py course/ui-review.md` passes.
