# Visual language and source observations

## Evidence from the supplied video

The reference is a roughly 15-second portrait recording of a desktop screen, with promotional overlays and a TikTok outro. Website content occupies only part of the frame. Colors, timing, and geometry are approximate because of perspective, recording exposure, compression, and possible editing.

| Approximate position | Visible website behavior | Transferable principle |
| --- | --- | --- |
| 0–1 s | Fine construction lines, a large A form, bright white brand lettering, blue/violet lighting | Stage a memorable typographic introduction using geometry and contrast |
| 1–4 s | Oversized WORKS lettering behind an angular form; colorful rectangular project panels move through a depth-like arrangement | Use layered media with one dominant item and spatial continuity |
| 4–6 s | Violet geometric scene gives way to a white section with compact Japanese text and a colored sculptural form | Alternate visual density and light/dark surfaces to create pacing |
| 6–10 s | Large cropped lettering, monochrome project imagery, then a vivid cloud-like project visual | Let content change the scene palette while retaining navigation and hierarchy |
| Around 10 s | A large A-like mark and fine intersecting lines on a dark surface | Use a consistent geometric motif to resolve the visual narrative |

The screen shows an ALCHE wordmark. This is an observed label, not proof of authorship, technology, or the promotional AI claims. The video does not establish exact input events, mobile behavior, load speed, source code, font family, or whether apparent 3D is rendered live. Do not turn these unknowns into requirements.

Describe the style as **cinematic spatial web design with experimental typography and a technical-grid aesthetic**. This is a useful descriptive name, not an official named methodology. Avoid calling it simply glassmorphism: translucent cards are not its defining feature.

## Composition rules

- Use a dominant stage: a headline, media scene, project, or meaningful data view should command attention. Supporting metadata forms a quieter aligned layer.
- Create depth through a small number of purposeful planes: background structure, subject/media, and foreground text or controls. Keep their boundaries readable.
- Use large letterforms as architecture in expressive areas. Cropping is acceptable for decorative duplicate text, but preserve readable semantic headings and avoid losing meaningful words on mobile.
- Balance dramatic negative space with compact editorial metadata. Do not reproduce illegibly small captions from a filmed desktop screen.
- Keep navigation visually calm and structurally stable across transitions. A scene change must not move the next action unexpectedly.
- Use thin grids, registration-like marks, or linework to support the composition. Avoid covering every component with an equally strong grid.

## Configurable token directions

The following are starting values designed for implementation, not measurements extracted from the video. Change them to fit brand, content, and accessibility.

| Token family | Starting direction | Adaptation |
| --- | --- | --- |
| Canvas | Near-black #0B0B12, light #F4F3EF | Use either as primary; create occasional contrast chapters |
| Foreground | #F5F5F7 on dark, #17171D on light | Check final text contrast with actual compositing |
| Accent | One electric hue, e.g. violet #7657FF or cyan #38CFE0 | Derive from brand; reserve for focal light, links, or action |
| Technical lines | Low-opacity foreground | Decorative only; use stronger borders for inputs and state |
| Display type | Bold sans, optionally condensed | Choose a font with all required Vietnamese glyphs |
| Body type | Readable sans, around 16–18 px | Keep forms/tables practical; allow zoom and wrapping |
| Display scale | clamp(2.75rem, 8vw, 9rem) | Tune line breaks; do not impose on all pages |
| Spacing | 4/8-based steps, generous scene margins | Tighten workspaces while preserving grouping |
| Corners | Square or slightly rounded media framing | Use brand rules; do not apply giant rounded pills everywhere |
| Layers | Background, media, content, controls, overlays | Manage stacking contexts so effects never cover focus or dialogs |

Keep decorative neon away from paragraph text. A glow does not replace contrast. Use readable scrims over complex imagery. Avoid mixing several unrelated display fonts, gradients, distorted headings, and particle systems in one view.

## Media direction

Match the subject to the product: authentic work for a portfolio, product imagery for commerce, software demonstrations for SaaS, and actual chart structures for analytics. Hero imagery should communicate the product rather than merely advertise visual effects.

Choose one principal scene technique: layered stills, a short rendered loop with a poster, CSS perspective panels, or a real 3D scene. Combine techniques only where their visual and loading costs are justified. The reference's dimensional media is inspiration, not a mandatory carousel.
