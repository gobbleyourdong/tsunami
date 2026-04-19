---
name: Shadcn Startup
applies_to: [landing, react-build, dashboard, fullstack, auth-app, ai-app]
phase: deliver
weight: strict
---

## Questions
1. Is the top navigation a sticky bar with `backdrop-blur-sm bg-white/80` or similar, containing a wordmark + horizontal link list + right-side CTA pair?
2. Is the hero content (claim headline + subtitle + CTA) horizontally centered in a `max-w-4xl` container, NOT full-bleed or left-aligned asymmetric?
3. Is the primary button solid with a saturated accent (blue `hsl(217 91% 60%)`, purple `hsl(234 55% 58%)`, or similar) and `rounded-lg` or `rounded-xl`?
4. Is there a visible "Trusted by" or social-proof strip with 5–6 company names / logos below the hero, rendered at ~60% opacity?
5. Are feature cards (if present) rendered as an equal 3-up grid with `rounded-xl border bg-white p-6` cards, each containing icon + heading + 2-line description + "Learn more" link?
6. Does the background stay pure white or `hsl(0 0% 99%)`, NOT dark, NOT warm cream, NOT gradient mesh?
7. Is typography the system-sans stack (`ui-sans-serif, system-ui`) or a close neutral sans (Inter), NOT a serif display face?
8. Are shadows subtle — `shadow-sm` max — rather than heavy glow or layered drop shadows?
9. Is the page free of oversized display type (headlines stay ≤ 56px), rotational layouts, mesh gradients, and expressive bento grids?
10. Does the page feel like a utility SaaS / dev-tool landing — information-dense rather than expressive?

## PASS criteria
≥ 8/10 questions answer yes unambiguously. Questions 1, 2, 3 are load-bearing — sticky blurred nav, centered hero, saturated primary CTA button are the doctrine tells.

## FAIL criteria
Any "no" on questions 1, 6, or 7. A shadcn_startup delivery without a sticky-blurred nav, with a dark background, or using a serif display face is not shadcn_startup — it drifted into photo_studio / editorial_dark / magazine_editorial territory.
