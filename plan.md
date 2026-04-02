# Plan: Tsunami Development

## Status
- 10/10 test apps render from one-prompt runners
- 9 scaffolds, all compile clean
- 4 UI components (Modal, Tabs, Toast, Badge)
- 5 auto-fix layers (scaffold, swell, CSS, compile, wire)
- Pre-scaffold hidden step + requirement classifier
- Windows .exe + setup.bat + setup.sh — all check VRAM
- GitHub Actions builds .exe automatically
- v0.1.0 release published

## Overnight Priority: shadcn-lite Component Library

Build 10-15 styled React components, add to every scaffold.
The 9B writes `<Dialog>` and it works. This is the highest leverage.

### Components to build (in react-app/src/components/ui/):
- [ ] Dialog — modal with overlay, title, description, actions
- [ ] Dropdown — click to open menu, items with icons
- [ ] Select — styled select with options
- [ ] Skeleton — loading placeholder (pulsing gray boxes)
- [ ] Progress — progress bar with percentage
- [ ] Avatar — circular image or initials
- [ ] Accordion — expandable sections
- [ ] Alert — info/warning/error/success banner
- [ ] Tooltip — hover text
- [ ] Switch — toggle on/off

### For each component:
1. Write as a single .tsx file in scaffolds/react-app/src/components/ui/
2. Use CSS variables from index.css (--bg, --accent, --border, etc.)
3. Typed props interface
4. Under 50 lines each
5. Export from ui/index.ts barrel
6. Add usage example to README
7. Copy to all scaffolds
8. Verify all 9 scaffolds compile

### After components:
- [ ] Update README with all component examples
- [ ] Run calculator test to verify nothing broke
- [ ] Run dashboard test to verify components available
- [ ] Commit + push

## Other Work (if time remains)
- Richer scaffold READMEs for form-app, fullstack, pixijs-game
- More test runners (pomodoro timer, markdown editor, color picker)
- Undertow integrated into auto-build loop
- setup.sh: pin llama.cpp to specific tested release
- Fix duplicate watcher_interval in config.yaml

## Architecture Reference
- 501 token system prompt
- 17 tools in bootstrap
- 9 scaffolds: react-app, dashboard, data-viz, form-app, landing, fullstack, threejs-game, pixijs-game, realtime
- Classifier: VRAM check → requirement analysis → pick scaffold
- Auto layers: pre-scaffold → auto-scaffold → auto-swell → auto-CSS → auto-compile → auto-wire
- Tests: calculator(10), quiz(34), excel-diff(17), snake(12), todo(25), landing(23), rhythm(15), crypto-dash(17), kanban(27), weather(24)
