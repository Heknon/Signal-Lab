# UI review: {{subject}}

Replace every `{{...}}` placeholder.

## Coverage

- **Screens:** {{course map, each lesson kind after a run, stack page, palette, drawer, sign-in, admin}}
- **Widths:** 390, 768, 1024, 1280, 1440
- **Themes:** dark, light
- **Script:** `{{path to the screenshot script}}`

## Rounds

### Round 1

| Screen | Width | Pattern | Fix |
|---|---|---|---|
| {{course map}} | {{390}} | {{eyebrow label above heading}} | {{removed}} |

## Final pass

Overflow (`scrollWidth - innerWidth`) at every width and screen: {{0}}

- [ ] No subtitle restating a heading
- [ ] No eyebrow labels
- [ ] No marketing copy or taglines
- [ ] No self-describing badges
- [ ] Sentence case everywhere
- [ ] One-line empty states
- [ ] No gradient text, glows or glassmorphism
- [ ] No icon-topped card grids or initials avatars
- [ ] No emoji
- [ ] Radii vary by role; borders, not shadows
- [ ] One primary button per view
- [ ] Zero horizontal overflow at all widths
- [ ] Focus rings visible; nothing hover-only
- [ ] Keyboard: run, palette, Escape
