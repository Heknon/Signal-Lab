# UI rules

The UI is a tool for learning, not a landing page. Every element must help
someone do the current exercise or find the next one.

## Layout

- **Course map:** one line of plain purpose, progress plus a single "Continue:
  <next lesson>" button, a one-line status strip for the running components,
  then tracks → modules → lessons. A lesson row shows state, title and minutes,
  and the kind only when it isn't the default.
- **Lesson page:** outline sidebar (collapsible); the lesson pane (title, a
  one-line meta row, goals with live status, prose, hints, previous/next); the
  workbench (editor plus result panel). The panes are resizable, and stack
  vertically below 860 px.
- **Workbench:** a toolbar (file tabs, status, Reset, Run with the shortcut) and
  a result panel with tabs (console, observations by type, environment).
  Panel internals adapt to the panel's own width (container queries), not the
  viewport's.
- **Empty states:** one quiet line ("No spans yet."), no icon or paragraph.

## Visual system

- **Typography:** a deliberate pair, such as IBM Plex Sans + Plex Mono, not a
  default single font everywhere. Body 14–15 px; prose 15 px at a line height of
  about 1.7; headings weight 600.
- **Colour:** neutral surfaces, one accent for primary actions and success, and
  fixed colours for each kind of thing in the domain (for example trace /
  metric / log), used consistently. Dark and light themes from tokens.
- **Radii by role:** inputs 3 px, buttons 5 px, panels 8 px. Not one radius everywhere.
- **Depth:** borders, not shadows. Shadows only for floating layers (popover, palette, drawer).
- **Motion:** only on state change, 100–200 ms, ease-out. No decorative animation.
- **Icons:** one SVG icon set, one stroke width. Never emoji.

## Deslop checklist

Run this on every screen in phase 7. Each item is a defect.

**Copy**
- [ ] A subtitle or explanatory line under a heading that restates the heading
- [ ] Eyebrow labels (small uppercase, letter-spaced text above headings)
- [ ] Marketing taglines or slogans ("Learn X by doing Y", "supercharge", "unlock", "seamless", "journey")
- [ ] Badges announcing what the product is ("Interactive course" with a sparkle icon)
- [ ] Title Case on labels and buttons (use sentence case)
- [ ] Throat-clearing intros ("In this lesson we will...", "Welcome to...")
- [ ] Empty states with an icon, a title *and* a paragraph
- [ ] Repeating the same information in two places on one screen
- [ ] Round fake numbers or placeholder names (John Doe, Acme)

**Visual**
- [ ] Gradient text, especially purple-to-blue
- [ ] Rows of identical icon-topped cards
- [ ] Initials in coloured circles or squares standing in for logos or avatars
- [ ] Glow halos, neon shadows, glassmorphism
- [ ] Heavy drop shadows on flat cards
- [ ] Emoji as icons or decoration
- [ ] The same border radius on every element
- [ ] Decorative flow diagrams or chips that carry no information
- [ ] More than one primary button in a view

**Behaviour and responsiveness**
- [ ] Horizontal scroll at any of 390, 768, 1024, 1280 or 1440 px
- [ ] Hover-only information (no focus or tap equivalent)
- [ ] Missing focus rings
- [ ] Spinners where the layout could show the incoming shape
- [ ] Text truncated with no way to see it (missing `title` or expansion)

## What good looks like

- The first thing on the course map is what to do next.
- Every check's failure message is readable in the goals list without opening anything.
- A finished experiment shows its chart with the limits and the fault window,
  and one sentence saying whether the hypothesis held.
