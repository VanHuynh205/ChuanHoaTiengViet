# Motion implementation and delivery

## Write a motion specification

For each significant animation, identify its purpose, trigger, affected properties, duration or scroll interval, exit/cleanup behavior, and static fallback. Treat timing below as proposed starting ranges, not extracted measurements.

| Effect | Practical starting specification | Fallback |
| --- | --- | --- |
| Control feedback | 120–220 ms color/opacity or small transform | Immediate state change |
| Content reveal | 350–650 ms, opacity and 12–28 px translation | Content visible without animation |
| Scene transition | 600–1100 ms, limited to major storytelling moments | Immediate chapter change |
| Pointer depth | Small bounded transform on decorative media; requestAnimationFrame updates | Stable media on coarse pointer/reduced motion |
| Spatial gallery | One active item, explicit previous/next and item links, bounded perspective | Semantic list/grid with the same content |
| Intro | Brief and skippable; show navigation and content immediately | Static opening frame |

Avoid repeated cinematic delays on frequently used actions. Restrict continuous movement to a justified area; provide pause behavior for persistent moving media. Avoid rapid flashing and aggressive glitch effects.

## Choose technology by required effect

1. Static composition or modest layering: HTML/CSS with images and transforms.
2. A few on-enter reveals: CSS plus IntersectionObserver if needed.
3. Coordinated multi-element scenes: the project's existing timeline/animation system, or one justified library.
4. Truly spatial geometry, lighting, or shader effects: WebGL with a poster fallback and accessible DOM counterpart.

Do not infer that 3D-looking panels require WebGL. Do not add Three.js, GSAP, a smooth-scroll library, and a second animation framework as a default bundle. Avoid per-frame framework state updates when direct animation values can drive visual changes.

## Scroll and scene ownership

Use native scroll and normal document order as the baseline. If a section is pinned, bound its duration, preserve escape through ordinary navigation, and verify wheel, keyboard, touch, resize, and route transitions. Do not intercept scrolling for the entire site.

Keep nested transformations separate: an outer wrapper may own scroll movement, an inner wrapper hover feedback. Prevent multiple systems from writing the same transform. Clean up event listeners, observers, timelines, and GPU resources on unmount. Pause rendering in hidden tabs and offscreen scenes.

## Accessible motion and fallback

Respect prefers-reduced-motion in both CSS and JavaScript. Turn off parallax, long travel, auto-rotation, scrubbed movement, and intro delays; keep the final composition visible. Ensure reduced-motion CSS does not leave elements at opacity zero. Do not assume a CSS rule stops a JavaScript render loop.

Use semantic headings and links outside canvas. Give meaningful media appropriate alternative text and decorative layers empty alternatives or aria-hidden. Keep a visible focus state above effects. Dialogs, galleries, and menus must work by keyboard; moving scenes must not steal focus. Validate contrast against rendered backgrounds, especially glow and video.

## Loading and performance

Start with visible text, navigation, dimensions reserved for media, and a poster. Load scene code and large assets only where used. Size images for their displayed role, defer below-fold media, and avoid eagerly loading every gallery video. Use compressed assets and cap rendering resolution according to device capability.

If a scene causes visible jank or poor loading, first simplify layers, blur, texture resolution, and continuous rendering. On weak devices or failed graphics initialization, retain the static experience. Never gate navigation on loading a large 3D file. Do not promise a performance score without measurement.

## Acceptance checklist

- The initial viewport communicates identity and purpose with an obvious next action.
- Page structure is specific to this product; requested routes and actions work.
- The chosen visual identity survives static mode through appropriate typography, hierarchy, framing, color, or imagery; no specific cinematic effect is mandatory.
- Desktop and phone layouts avoid clipped meaningful text, overlap, and accidental horizontal scrolling.
- Keyboard focus, menus, dialogs, form feedback, and touch controls remain usable.
- Reduced motion and failed/missing media leave readable, navigable content.
- The primary task does not wait for decorative animation.
- Repeated navigation does not duplicate listeners, loops, or effects.
- Report build/runtime checks actually performed and any untested conditions.

Use functional checks and rendered inspection proportionate to the implementation. Do not claim this checklist is formal accessibility certification.

## Scene continuity patterns from additional references

- Expanding media: grow a framed image toward a section-width composition with a stable focal point. Reserve layout space; avoid scaling text inside the image. On mobile use a simple image-to-section transition.
- Portal transition: a window or frame gives way to the scene it contains. Use a mask/layer or rendered sequence only if assets support it; keep equivalent content in DOM. Reduced motion shows the destination composition directly.
- Guided environment: present chapters along an apparent path through a spatial world. Choose direct chapter navigation and one active text panel; do not require navigation through 3D to access information. The source video does not prove how this was implemented.
- Product as anchor: carry an aircraft, building, or product visual across adjacent sections to explain a story. Keep coordinates/layout ownership explicit and prevent overlap with actionable content.
- Organic edge accents: use foliage or similar framing only for a relevant brand; clip decoration to its region, hide it from accessibility APIs, and prevent pointer interception.
- Globe or map stage: provide equivalent searchable destination/service lists and conventional controls. Decorative routes must not imply real service coverage or geographic precision.

Specify the start composition, transition, destination composition, and user action for each chosen scene. Do not stack portal zoom, particle effects, horizontal takeover, and parallax on the same interaction. Durations in edited promotional video are not reliable production timing targets.
