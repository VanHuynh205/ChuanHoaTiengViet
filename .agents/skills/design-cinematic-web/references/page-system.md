# Page system and completion criteria

## Translate purpose into pages

Map each requested user journey to entry, decision, action, and result. List only pages/states necessary for the scope. A visually polished homepage does not complete a request for a multipage store or usable workspace.

| Page family | Primary concern | Typical visual treatment |
| --- | --- | --- |
| Introduction/campaign | Identity, value, next action | Most expressive area; direct path past spectacle |
| Discovery/search | Find and compare | Consistent cards/rows, visible filters and result state |
| Detail/case/product | Understand evidence and options | Strong subject media plus readable structured information |
| Reading/docs | Comprehend and navigate | Comfortable measure, heading hierarchy, stable anchors/search |
| Transaction/form | Complete accurately | Persistent labels, understandable errors, stable controls |
| Workspace/monitoring | Repeated efficient use | Predictable navigation, practical density, truthful data |

For each included family specify primary content, primary action, responsive behavior, and significant states. Preserve URL/navigation conventions where present. Do not fabricate APIs or data integrations to make a demo appear complete.

## Shared system without uniform layouts

Keep tokens, button/link semantics, focus treatment, navigation behavior, labels, and spacing relationships consistent. Define variants for compact versus spacious components. Use expressive chapter transitions only between appropriate presentation sections, not between every application state.

Treat content as a design input. Use realistic title lengths, Vietnamese text, long names, missing images, and data ranges. Avoid placeholders that hide layout problems. Mark sample data explicitly and never invent customer logos or testimonials as evidence.

For forms, cover validation, submit/loading, success only on actual success, and recoverable failure. For lists/search, cover empty query, no results, loading, and errors. For restricted content, distinguish signed-out, unauthorized, and unavailable states when in scope. For data applications, include units, time ranges, and relevant empty/error states.

## Review in separate passes

1. Scope and function: can users complete the requested journey? Are routes, links, data states, and outcomes honest?
2. Identity and composition: do media, typography, spacing, and color express the selected direction? Are different page families composed for their tasks?
3. Interaction and access: inspect focus, keyboard/touch, zoom, responsive layout, contrast, and reduced motion.
4. Delivery: run appropriate build/runtime checks, inspect loading and failure of heavy media, and verify route changes do not leak effects.

Use available rendered screenshots at representative widths; do not accept code inspection alone as visual proof. If preview tools are unavailable, report what could be checked and leave visual validation explicitly unverified. Do not create extra audit artifacts unless useful to the task.

Resolve broken task flows, unreadable content, and unusable controls before decorative refinements. Then correct hierarchy, image crop, spacing, and motion. Aesthetic polish does not compensate for a missing action or a fabricated integration.

## Definition of done

Requested pages and states are represented; core actions work within the stated backend/demo scope; selected visual direction is coherent; smaller screens and reduced-motion paths remain usable; available checks have been run; remaining asset, integration, or verification gaps are disclosed. Do not call the result universally production-ready solely because it resembles a reference.
