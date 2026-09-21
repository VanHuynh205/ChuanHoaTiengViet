# Adapt the system to the project

## Select intensity by user task

| Intensity | Suitable use | Motion boundaries |
| --- | --- | --- |
| Expressive | Creative portfolio, campaign, entertainment showcase | One signature scene and coordinated transitions; persistent skip/direct navigation |
| Balanced | SaaS marketing, product introduction, hospitality, education landing page | Animated hero/demo and selective reveals; conventional reading and conversion sections |
| Restrained | Dashboard, internal tool, checkout, account management, documentation | Quiet transitions and polished static composition; stable controls and content |

Intensity may change within one site. A store homepage can be expressive while its checkout is restrained. Do not force a user to choose a named intensity when the task makes the decision clear.

## Choose architecture from the content

| Project | Appropriate structure | How the style carries over | What to avoid |
| --- | --- | --- | --- |
| Creative portfolio | Work index, case studies, studio/profile, contact | Spatial project stage, oversized case titles, editorial credits | Hiding all work behind a gesture-only carousel |
| Online shop | Categories, filters/search, product detail, cart, checkout | Art-directed campaign imagery, refined product stage, bold category type | Moving prices, animated checkout fields, obscured purchase controls |
| SaaS marketing | Problem, product demonstration, relevant features, pricing when supplied, signup | Layered interface demo, strong headline, alternating light/dark chapters | Fake product UI, unsupported customer claims, long animation before signup |
| Analytics application | Workspace navigation, filters, KPIs, charts, table/detail views | Controlled contrast, fine separators, typography and selective accent | 3D chart distortion, perspective tables, decorative animations on every refresh |
| Education platform | Course discovery, course detail, lesson, progress | Thematic lesson imagery and strong course hierarchy | Autoplay effects that interrupt reading or video lessons |
| News or documentation | Search, categories, article hierarchy, related content | Editorial type, quiet grid, occasional feature image | Scroll takeover, obscured text, animation on every paragraph |
| Corporate/service site | Services, evidence, organization, enquiry | Restrained dimensional visuals and structured service narratives | Assuming a game-like scene is appropriate to every brand |

Do not add every listed page. Implement only the agreed scope. For existing sites, adapt current information architecture unless a requested redesign justifies changes.

## Responsive decisions

Desktop spatial galleries may become a vertical list or accessible horizontal snap list on small screens. Choose based on item count and comparison needs. Keep titles, prices, and links in ordinary document flow even if images use transforms.

Replace pointer parallax with a stable composition on touch devices. Never require hover to expose critical content. Reduce the number of visible media layers before shrinking the text. Preserve the focal subject when cropping; change the crop or image for mobile if needed.

Check a compact phone, a tablet, and a wide desktop (for example 360, 768, and 1440 CSS px). These are testing examples, not fixed required breakpoints. Let content determine breakpoints. Make controls comfortably touchable, typically about 44 CSS px where practical, and verify zoom and long localized strings.

## Generalization check

Before delivering, answer:

1. Would replacing the site's subject leave almost the same page? If so, revisit content structure and product-specific components.
2. Does the selected direction remain coherent through hierarchy, framing, typography, and pacing when the palette changes, without imposing cinematic effects on functional screens?
3. Does the interface still solve its primary task with animation disabled?
4. Have marketing pages and task pages received different treatment when needed?
5. Have existing brand rules and functional constraints overridden optional stylistic defaults?

## Additional categories and unfamiliar projects

| Project | Necessary architecture to consider | Direction and task constraint |
| --- | --- | --- |
| Property/hospitality | Discovery, property/room details, amenities, location, enquiry or reservation | Luxury editorial or travel narrative; distinguish renderings from photographs and confirmed availability from demo data |
| Travel/transport | Destination/service information, search, results, itinerary/detail, booking when requested | Journey-based storytelling on marketing pages; stable forms, dates, totals, and errors in booking |
| Technical product/platform | Product explanation, architecture/use cases, evidence, docs, contact/signup | Technical world for an explainer, restrained docs and settings; do not invent benchmarks or technical claims |
| Public information, health, civic service | Search, clear guidance, eligibility/instructions, contact or service flow | Readability and trust first; no spectacle obstructing urgent information |
| Community/member product | Discovery/feed, profile, detail/discussion, creation/moderation where in scope | Identity through type, palette, and framing; stable reading and composing surfaces |

These are examples, not promises of prebuilt domain functionality. For unfamiliar domains, enumerate the primary tasks, objects, state transitions, and content depth before choosing components. Define acceptance checks around those tasks.
