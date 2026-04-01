# Building — Research First

When building something complex (games, 3D, physics, APIs you're not sure about):

1. **Search GitHub** — `search_web(query, search_type="code")` finds real implementations
2. **Read the source** — don't guess at APIs, find a repo that does what you need
3. **Study patterns** — how did they set up physics? what library? what's the render loop?
4. **Then build** — use the patterns you found, not guesses

## Web Development

### For React projects
Use webdev_scaffold (Vite + React + TypeScript + Tailwind CSS).

### For single HTML files
Write the complete file with all dependencies from CDN.

### Build from researched patterns
Use the API patterns you found in research. Don't improvise.

## Quality Rules
- Never use href="#" — always real anchors or URLs
- Never import packages that aren't installed
- Always test after building — use undertow
- If test shows an error, read the error, fix, test again
