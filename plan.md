# Plan: Tsunami Development

## Status: COMPLETE
- 10/10 test apps render from one-prompt runners
- 9 scaffolds, all compile clean
- 28 UI components per web scaffold (24 ui/ + 4 root)
- 9 threejs components (shaders, procedural, sprites, textures)
- 3 pixijs components (canvas, physics, sprite animator)
- 5 auto-fix layers (scaffold, swell, CSS, compile, wire)
- Pre-scaffold hidden step + requirement classifier
- IDE-style desktop UI with split panes + live preview
- Windows .exe + setup.bat + setup.sh — all check VRAM
- GitHub Actions builds .exe automatically
- v0.1.0 release published
- Stall detection + block repeated scaffold
- 501 token system prompt, 17 tools
- 27/27 tests pass

## Component Library (28 UI components)
Base: Modal, Tabs, Toast, Badge
shadcn-lite: Dialog, Select, Skeleton, Progress, Avatar, Accordion, Alert, Tooltip, Switch, Dropdown
Fancy: StarRating, GlowCard, Parallax, AnimatedCounter
Niche: BeforeAfter, ColorPicker, Timeline, Kanban
CSS Effects: AnnouncementBar, Marquee, TypeWriter, GradientText
Interactive: ScrollReveal, Slideshow

## Domain Components
threejs: Scene, Ground, Box, Sphere, HUD, ShaderMaterial (3 GLSL), ProceduralTerrain, ProceduralPlanet, SpriteSheet, TextureGen (4 generators)
pixijs: GameCanvas, Physics2D, SpriteAnimator, Puppet rig
landing: Navbar, Hero, Section, FeatureGrid, Footer, ParallaxHero, PortfolioGrid
dashboard: Layout, StatCard, DataTable, Card
form-app: FileDropzone, DataTable, parseFile
realtime: useWebSocket
fullstack: useApi + Express/SQLite CRUD

## What's Next
- Windows installer testing with real users
- Mac installer testing (Aaron's friend)
- Richer README examples for all 28 UI components
- More test runners for edge cases
- CLI improvements (tab autocomplete, trace view)
- Undertow integrated into auto-build loop with live Vite
