---
name: Chuẩn hóa tiếng Việt
description: Vietnamese paper and letterforms, with a compact text workspace.
colors:
  accent: "#086b64"
  accent-strong: "#073f40"
  accent-soft: "#e0f0e8"
  bg: "#f5f4ee"
  panel: "#fffefa"
  panel-strong: "#fff"
  ink: "#183839"
  muted: "#526969"
  line: "#d8dfd9"
  success: "#246953"
  danger: "#a1323d"
typography:
  display:
    fontFamily: "Source Serif 4, serif"
    fontSize: "clamp(48px, 4.4vw, 66px)"
    fontWeight: 400
    lineHeight: 1.12
    letterSpacing: "-.035em"
  headline:
    fontFamily: "Be Vietnam Pro, Segoe UI, sans-serif"
    fontSize: "28px"
    lineHeight: 1.35
    letterSpacing: "-.03em"
  body:
    fontFamily: "Be Vietnam Pro, Segoe UI, sans-serif"
    fontSize: "14px"
    lineHeight: 1.6
  editor:
    fontFamily: "Be Vietnam Pro, Segoe UI, sans-serif"
    fontSize: "16px"
    lineHeight: 1.9
  label:
    fontFamily: "Be Vietnam Pro, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 600
rounded:
  badge: "4px"
  control: "7px"
  panel: "10px"
  auth-frame: "16px"
spacing:
  compact: "12px"
  panel: "18px"
  mobile-page: "16px"
  page: "32px"
components:
  button-auth:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.panel-strong}"
    rounded: "{rounded.control}"
    height: "49px"
  input-auth:
    backgroundColor: "{colors.panel-strong}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px 14px"
    height: "48px"
  editor-panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
    padding: "18px"
---

# Design System: Chuẩn hóa tiếng Việt

## Overview

**Creative North Star: “Giấy và tiếng Việt” (Paper and Vietnamese).** This descriptive name captures the user's supplied concept: deep teal, ivory paper, mint, and Vietnamese diacritics. The auth surface has an expressive paper ribbon; the working surface gives space to text and immediate comparison.

This is a scan of the implemented frontend, not a user interview. The final “Paper & language” overrides in `frontend/src/styles.css` define the current identity. Review captures under `.impeccable/review` use fixtures and do not establish backend correctness.

**Key Characteristics:**

- Vietnamese typography with complete diacritics.
- Paper-like surfaces, restrained borders, and a serif letterform signature.
- Compact controls around generous, legible editors.

The current refresh uses a two-column auth frame with a live HTML form beside the
`vietnamese-ribbon.png` illustration, and a compact 208px workbench rail. Source
and result editors remain the primary content; both copy actions expose real
success/error feedback, while automatic normalization and optional AI consent
remain unchanged.

## Colors

Deep teal anchors navigation and auth; ivory and mint keep the reading surfaces calm.

- **Primary:** `accent-strong` is the auth story, sidebar, and auth primary action; `accent` is links, active controls, and focus.
- **Secondary:** `accent-soft` is the pale mint interaction surface; success uses the semantic `success` color.
- **Neutral:** `bg` surrounds ivory `panel` surfaces; `panel-strong` is the white editing/field surface. `ink` and `muted` distinguish primary text from support text; `line` separates sections.
- **Feedback:** `danger` marks errors. Change highlighting has category-specific colors and must represent actual changes.

**The Meaningful Highlight Rule.** Decorative mint must never imply that unchanged text was normalized.

## Typography

Be Vietnam Pro carries interface text and editable content. Source Serif 4 carries the auth story heading, the decorative “ă” signature, and the empty-result heading. Fonts are self-hosted in `frontend/public/fonts`: Be Vietnam Pro weights 400, 500, 600, 700; Source Serif 4 weight 400, with license files alongside.

The display role applies to wide auth layouts. It reduces to 46px at the tablet breakpoint and 27px on mobile. Auth form titles are 32px, reducing to 27px on mobile. Workspace headings reduce from the headline token to 24px on mobile. Editor text stays 16px, with mobile line height 1.8. Secondary labels and status metadata use a compact 10–13px range.

## Layout

Auth uses a centered frame capped at 1320px, with a deep-teal story/form split and a 760px minimum desktop height. The story now carries a chapter marker, paper example, and the ribbon asset as a restrained focal point; at 700px it stacks into a 220px story band above the form. Functional text remains HTML.

The workspace has a compact 198px teal sidebar, reducing to 174px at 900px. Two equal editor columns use a 16px gap. At 700px navigation becomes a horizontal scrollable row and editors stack. Content padding reduces with viewport width; long names and status text must wrap or truncate without widening the page.

Desktop editors use `clamp(300px, calc(100svh - 450px), 560px)` above 1100px; tablet editors use 420px, and mobile editors use 290px. Their contents scroll. These are density targets, not a guarantee that every conditional notice fits in every viewport.

## Elevation & Depth

Depth is primarily tonal. Workspace panels are flat with thin borders; the auth frame has a diffuse shadow (`0 24px 70px #163c3520`). Small paper examples use a modest shadow (`0 8px 18px #002b2a22`) and slight static rotation. Focus has a 2px teal outline and `0 0 0 3px #086b6426` ring; sidebar links and buttons instead use a light mint outline (`#b9ead4`) without a shadow against the dark surface. Legacy utility surfaces retain their local shadows.

## Shapes

Controls have gently rounded corners; panels use the panel radius and the auth frame uses the larger frame radius. Status badges use the compact badge radius. The paper ribbon and “ă” are signature elements, not a replacement for readable labels or icons. Existing utility forms retain some pill-shaped actions.

## Components

- **Auth controls:** white bordered inputs with visible labels and a separate password visibility button. The deep teal submit action retains loading and error states; the registration/login switch is an outlined link.
- **Navigation:** icon plus text, pale text on teal, with a translucent active surface. Administrative entries remain role-dependent. A keyboard skip link reaches the main content.
- **Editor pair:** matching white text surfaces in ivory panels, with headers, status, and copy action. The source overlay and textarea must use identical text metrics. Preserve empty, loading, error, and populated states.
- **AI consent:** compact mint notice with an explicit checkbox and expandable data explanation. Keep the explanation accessible and consent optional.
- **Signature artwork:** `frontend/public/images/vietnamese-ribbon.png` is a custom generated decorative asset, not a whole-page mockup. Keep labels, examples, forms, and navigation as live HTML. The decorative image uses an empty alt attribute. The product lockup uses the two-leaf `BrandMark` SVG; the Vietnamese letterform is reserved for editorial decoration and is not used as the project logo.
- **Composition notes:** Auth lets the ribbon, botanical marks, cloud motifs, and fine loops occupy the story field behind the live copy. Workspace uses the same asset as a low-opacity right-edge ornament with a live quote, while editor surfaces remain opaque and quiet for reading.

Auth enters once over 400ms with `cubic-bezier(.16,1,.3,1)`. Control state transitions use 150ms ease; active buttons move down 1px. There is no perpetual decorative motion; the existing loading shimmer remains a functional progress state. Reduced-motion preference disables animations and transitions globally.

## Do's and Don'ts

- **Do** preserve Vietnamese diacritics, keyboard focus, semantic labels, and responsive reading order.
- **Do** keep workspace ornament subordinate to the editor pair.
- **Do** reuse the actual final stylesheet values when extending the interface.
- **Don't** add unsupported auth flows or turn a visual redesign into backend behavior changes.
- **Don't** replace functional content with an image or animate the ribbon continuously.
- **Don't** present fixture screenshots as evidence of real authentication, normalization, or persistence.
