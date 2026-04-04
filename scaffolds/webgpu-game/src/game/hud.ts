/**
 * HUD — HTML overlay for health, score, combo, wave, and screen states.
 * Pure DOM methods only — no innerHTML.
 */

import type { GameState } from './state'
import type { TutorialSystem } from '@engine/flow/tutorial'

function el(tag: string, style?: Partial<CSSStyleDeclaration>, text?: string): HTMLElement {
  const e = document.createElement(tag)
  if (style) Object.assign(e.style, style)
  if (text) e.textContent = text
  return e
}

export class HUD {
  private root: HTMLElement

  constructor(root: HTMLElement) {
    this.root = root
  }

  private clear(): void {
    while (this.root.firstChild) this.root.removeChild(this.root.firstChild)
  }

  showTitle(highScore: number): void {
    this.clear()
    Object.assign(this.root.style, { textAlign: 'center', paddingTop: '30vh' })

    this.root.appendChild(el('div', {
      fontSize: '48px', fontWeight: 'bold', color: '#00ff88',
      textShadow: '0 0 30px #00ff8844',
    }, 'SIGMA ARENA'))
    this.root.appendChild(el('div', {
      marginTop: '20px', color: '#aaa', fontSize: '16px',
    }, 'Top-Down Arena Shooter'))
    const prompt = el('div', {
      marginTop: '40px', color: '#4a9eff', fontSize: '18px',
    }, 'Press ENTER to Start')
    prompt.style.animation = 'pulse 1.5s infinite'
    this.root.appendChild(prompt)

    if (highScore > 0) {
      this.root.appendChild(el('div', {
        marginTop: '20px', color: '#888', fontSize: '14px',
      }, `High Score: ${highScore}`))
    }
  }

  showTutorial(tutorial: TutorialSystem): void {
    this.clear()
    Object.assign(this.root.style, { textAlign: 'center', paddingTop: '40vh' })

    const msg = el('div', { fontSize: '28px', color: '#fff' }, tutorial.currentStep?.message ?? '')
    const step = el('div', { marginTop: '10px', color: '#666', fontSize: '14px' },
      `Step ${tutorial.stepIndex + 1} / ${tutorial.totalSteps}`)

    this.root.appendChild(msg)
    this.root.appendChild(step)

    tutorial.onStepChange = (s) => {
      msg.textContent = s.message
      step.textContent = `Step ${tutorial.stepIndex + 1} / ${tutorial.totalSteps}`
    }
  }

  showArena(): void {
    this.clear()
    Object.assign(this.root.style, { textAlign: '', paddingTop: '', pointerEvents: 'none' })

    const row = el('div', {
      display: 'flex', justifyContent: 'space-between', padding: '12px 20px',
    })

    // Health
    const healthBox = el('div', { display: 'flex', alignItems: 'center', gap: '8px' })
    healthBox.appendChild(el('span', { color: '#ff4444' }, 'HP'))
    const barOuter = el('div', {
      width: '120px', height: '8px', background: '#333',
      borderRadius: '4px', overflow: 'hidden',
    })
    const barInner = el('div', { width: '100%', height: '100%', background: '#ff4444', transition: 'width 0.3s' })
    barInner.id = 'hud-hp-bar'
    barOuter.appendChild(barInner)
    healthBox.appendChild(barOuter)
    const hpText = el('span', { color: '#ff4444', fontSize: '12px' }, '100')
    hpText.id = 'hud-hp-text'
    healthBox.appendChild(hpText)
    row.appendChild(healthBox)

    // Wave
    const wave = el('div', { color: '#4a9eff', fontSize: '16px' })
    wave.id = 'hud-wave'
    row.appendChild(wave)

    // Score
    const scoreBox = el('div', { textAlign: 'right' })
    const score = el('div', { color: '#fff', fontSize: '20px', fontWeight: 'bold' }, '0')
    score.id = 'hud-score'
    const combo = el('div', { color: '#ffcc00', fontSize: '14px', opacity: '0', transition: 'opacity 0.3s' })
    combo.id = 'hud-combo'
    scoreBox.appendChild(score)
    scoreBox.appendChild(combo)
    row.appendChild(scoreBox)

    this.root.appendChild(row)
  }

  showPause(paused: boolean): void {
    const existing = document.getElementById('pause-overlay')
    if (paused && !existing) {
      const overlay = el('div', {
        position: 'fixed', top: '0', left: '0', right: '0', bottom: '0',
        background: 'rgba(0,0,0,0.7)', display: 'flex',
        alignItems: 'center', justifyContent: 'center', zIndex: '100',
      })
      overlay.id = 'pause-overlay'
      overlay.appendChild(el('div', {
        color: '#fff', fontFamily: 'monospace', fontSize: '24px',
      }, 'PAUSED — Press ESC to resume'))
      document.body.appendChild(overlay)
    } else if (!paused && existing) {
      existing.remove()
    }
  }

  showVictory(score: number, maxCombo: number): void {
    this.clear()
    Object.assign(this.root.style, { textAlign: 'center', paddingTop: '22vh' })

    this.root.appendChild(el('div', {
      fontSize: '48px', fontWeight: 'bold', color: '#00ff88',
      textShadow: '0 0 30px #00ff8844',
    }, 'VICTORY'))
    this.root.appendChild(el('div', {
      marginTop: '15px', color: '#ffcc00', fontSize: '22px',
    }, 'Arena Cleared!'))
    this.root.appendChild(el('div', {
      marginTop: '30px', color: '#fff', fontSize: '20px',
    }, `Final Score: ${score.toLocaleString()}`))
    this.root.appendChild(el('div', {
      marginTop: '10px', color: '#aaa', fontSize: '16px',
    }, `Max Combo: ${maxCombo}x | All 10 Waves Survived`))
    const prompt = el('div', {
      marginTop: '40px', color: '#4a9eff', fontSize: '18px',
    }, 'Press ENTER to Play Again')
    prompt.style.animation = 'pulse 1.5s infinite'
    this.root.appendChild(prompt)
  }

  showGameOver(score: number, wave: number, maxCombo: number): void {
    this.clear()
    Object.assign(this.root.style, { textAlign: 'center', paddingTop: '25vh' })

    this.root.appendChild(el('div', {
      fontSize: '40px', fontWeight: 'bold', color: '#ff4444',
      textShadow: '0 0 20px #ff444444',
    }, 'GAME OVER'))
    this.root.appendChild(el('div', {
      marginTop: '30px', color: '#fff', fontSize: '20px',
    }, `Score: ${score.toLocaleString()}`))
    this.root.appendChild(el('div', {
      marginTop: '10px', color: '#aaa', fontSize: '16px',
    }, `Wave: ${wave} | Max Combo: ${maxCombo}x`))
    const prompt = el('div', {
      marginTop: '40px', color: '#4a9eff', fontSize: '18px',
    }, 'Press ENTER to Retry')
    prompt.style.animation = 'pulse 1.5s infinite'
    this.root.appendChild(prompt)
  }

  update(dt: number, state: GameState): void {
    if (state.phase !== 'arena') return

    const hpBar = document.getElementById('hud-hp-bar')
    const hpText = document.getElementById('hud-hp-text')
    const scoreEl = document.getElementById('hud-score')
    const comboEl = document.getElementById('hud-combo')
    const waveEl = document.getElementById('hud-wave')

    if (hpBar) {
      const pct = state.playerHealth.healthPercent * 100
      hpBar.style.width = `${pct}%`
      hpBar.style.background = pct < 25 ? '#ff0000' : pct < 50 ? '#ff8800' : '#ff4444'
    }
    if (hpText) hpText.textContent = `${Math.ceil(state.playerHealth.health)}`
    if (scoreEl) scoreEl.textContent = state.score.score.toLocaleString()
    if (comboEl) {
      if (state.score.combo > 1) {
        comboEl.style.opacity = '1'
        comboEl.textContent = `${state.score.combo}x COMBO (${state.score.multiplier.toFixed(1)}x)`
      } else {
        comboEl.style.opacity = '0'
      }
    }
    if (waveEl) waveEl.textContent = `WAVE ${state.wave} / ${state.maxWave}`
  }
}
