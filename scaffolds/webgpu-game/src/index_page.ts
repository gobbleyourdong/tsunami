/**
 * Index page — hub linking all games and tools.
 * Shows at / when no game is directly loaded.
 */

export function renderIndexPage(): void {
  const root = document.getElementById('hud')
  if (!root) return

  Object.assign(root.style, {
    pointerEvents: 'auto',
    padding: '40px',
    maxWidth: '800px',
    margin: '0 auto',
  })

  const canvas = document.getElementById('game') as HTMLCanvasElement
  if (canvas) canvas.style.display = 'none'

  const h = (tag: string, text: string, style?: Partial<CSSStyleDeclaration>): HTMLElement => {
    const el = document.createElement(tag)
    el.textContent = text
    if (style) Object.assign(el.style, style)
    return el
  }

  const link = (href: string, text: string, desc: string): HTMLElement => {
    const row = document.createElement('a')
    row.href = href
    row.style.cssText = 'display:block;padding:16px 20px;margin:8px 0;background:#16213e;border:1px solid #333;border-radius:8px;text-decoration:none;transition:border-color 0.2s'
    row.onmouseover = () => row.style.borderColor = '#4a9eff'
    row.onmouseout = () => row.style.borderColor = '#333'

    const title = document.createElement('div')
    title.textContent = text
    title.style.cssText = 'color:#4a9eff;font-size:18px;font-weight:bold;margin-bottom:4px'
    row.appendChild(title)

    const sub = document.createElement('div')
    sub.textContent = desc
    sub.style.cssText = 'color:#888;font-size:13px'
    row.appendChild(sub)

    return row
  }

  // Clear
  while (root.firstChild) root.removeChild(root.firstChild)

  // Header
  root.appendChild(h('div', 'TSUNAMI ENGINE', {
    fontSize: '36px', fontWeight: 'bold', color: '#00ff88',
    textShadow: '0 0 20px #00ff8844', marginBottom: '8px',
  }))
  root.appendChild(h('div', 'WebGPU Game Scaffold — Zero Dependencies', {
    color: '#888', fontSize: '14px', marginBottom: '30px',
  }))

  // Games section
  root.appendChild(h('div', 'Games', {
    fontSize: '14px', color: '#4a9eff', textTransform: 'uppercase',
    letterSpacing: '2px', marginBottom: '12px',
  }))
  root.appendChild(link('/index.html', 'Sigma Arena', 'Top-down wave shooter — 10 waves + boss, generated sprites, procedural audio'))
  root.appendChild(link('/rpg.html', 'Oakvale RPG', '2.5D tile RPG — village + forest, NPC quests, combat, generated sprites'))

  // Tools section
  root.appendChild(h('div', 'Tools', {
    fontSize: '14px', color: '#4a9eff', textTransform: 'uppercase',
    letterSpacing: '2px', marginTop: '24px', marginBottom: '12px',
  }))
  root.appendChild(link('/editor.html', 'Level Editor', 'Paint tiles, place props + NPCs, export JSON, play in RPG'))

  // Stats
  const stats = document.createElement('div')
  stats.style.cssText = 'margin-top:30px;padding:16px;background:#0f3460;border-radius:8px;font-size:12px;color:#666;line-height:1.8'
  const lines = [
    'Engine: 11 modules, 256 tests, 45 source files, zero dependencies',
    'Sprite Pipeline: SD Turbo → sigmatrade extraction → auto-scoring',
    'Audio: 13 SFX + 6 music tracks, all procedural (Web Audio API)',
    'Tools: sprite_pipeline.py, tilemap_gen.py, game_from_text.py',
    'Build: 35KB gzipped (arena) | TypeScript + WGSL',
  ]
  for (const line of lines) {
    const p = document.createElement('div')
    p.textContent = line
    stats.appendChild(p)
  }
  root.appendChild(stats)
}
