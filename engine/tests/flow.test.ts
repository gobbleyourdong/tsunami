import { describe, it, expect } from 'vitest'
import { SceneManager } from '../src/flow/scene_manager'
import { MenuSystem } from '../src/flow/menu'
import { DialogSystem } from '../src/flow/dialog'
import { TutorialSystem } from '../src/flow/tutorial'
import { DifficultyManager } from '../src/flow/difficulty'
import { GameFlow } from '../src/flow/game_flow'
import type { GameScene } from '../src/flow/scene_manager'
import type { MenuItem } from '../src/flow/menu'

function makeScene(name: string, log?: string[]): GameScene {
  return {
    name,
    enter: (from) => log?.push(`enter:${name}<-${from ?? 'none'}`),
    exit: (to) => log?.push(`exit:${name}->${to ?? 'none'}`),
    update: () => log?.push(`update:${name}`),
  }
}

describe('SceneManager', () => {
  it('registers and lists scenes', () => {
    const sm = new SceneManager()
    sm.add(makeScene('title')).add(makeScene('game'))
    expect(sm.list()).toEqual(['title', 'game'])
  })

  it('transitions instantly', async () => {
    const log: string[] = []
    const sm = new SceneManager()
    sm.add(makeScene('a', log)).add(makeScene('b', log))

    await sm.goto('a')
    expect(sm.current).toBe('a')
    expect(log).toContain('enter:a<-')

    await sm.goto('b')
    expect(sm.current).toBe('b')
    expect(log).toContain('exit:a->b')
    expect(log).toContain('enter:b<-a')
  })

  it('fade transition drives progress over update calls', async () => {
    const sm = new SceneManager()
    sm.add(makeScene('a')).add(makeScene('b'))
    await sm.goto('a')

    // Start fade transition
    await sm.goto('b', { type: 'fade', duration: 200 })
    expect(sm.isTransitioning).toBe(true)

    // Drive transition with updates
    sm.update(0.05)  // 50ms
    expect(sm.progress).toBeGreaterThan(0)

    sm.update(0.06)  // now at 110ms > 100ms half-duration → switch
    // Scene should have switched at midpoint
    expect(sm.current).toBe('b')

    sm.update(0.1)  // finish transition
    expect(sm.isTransitioning).toBe(false)
  })

  it('calls update on current scene', async () => {
    const log: string[] = []
    const sm = new SceneManager()
    sm.add(makeScene('a', log))
    await sm.goto('a')

    sm.update(0.016)
    expect(log).toContain('update:a')
  })

  it('fires onSceneChange callback', async () => {
    const changes: string[] = []
    const sm = new SceneManager()
    sm.add(makeScene('a')).add(makeScene('b'))
    sm.onSceneChange = (from, to) => changes.push(`${from}->${to}`)

    await sm.goto('a')
    await sm.goto('b')
    expect(changes).toContain('a->b')
  })
})

describe('MenuSystem', () => {
  it('pushes and navigates', () => {
    const menu = new MenuSystem()
    menu.push({
      title: 'Main',
      items: [
        { id: 'play', label: 'Play', type: 'button' },
        { id: 'options', label: 'Options', type: 'button' },
        { id: 'quit', label: 'Quit', type: 'button' },
      ],
    })

    expect(menu.selectedIdx).toBe(0)
    expect(menu.selectedItem?.id).toBe('play')

    menu.down()
    expect(menu.selectedItem?.id).toBe('options')

    menu.down()
    expect(menu.selectedItem?.id).toBe('quit')

    menu.down() // wraps
    expect(menu.selectedItem?.id).toBe('play')
  })

  it('up wraps to last', () => {
    const menu = new MenuSystem()
    menu.push({
      title: 'Test',
      items: [
        { id: 'a', label: 'A', type: 'button' },
        { id: 'b', label: 'B', type: 'button' },
      ],
    })
    menu.up() // wrap from 0 to 1
    expect(menu.selectedItem?.id).toBe('b')
  })

  it('confirm triggers button callback', () => {
    let clicked = false
    const menu = new MenuSystem()
    menu.push({
      title: 'Test',
      items: [
        { id: 'play', label: 'Play', type: 'button', onSelect: () => { clicked = true } },
      ],
    })
    menu.confirm()
    expect(clicked).toBe(true)
  })

  it('toggle flips value', () => {
    const menu = new MenuSystem()
    const toggle: MenuItem = { id: 'sound', label: 'Sound', type: 'toggle', value: true }
    menu.push({ title: 'Test', items: [toggle] })

    menu.confirm()
    expect(toggle.value).toBe(false)
    menu.confirm()
    expect(toggle.value).toBe(true)
  })

  it('slider adjusts with left/right', () => {
    const menu = new MenuSystem()
    const slider: MenuItem = {
      id: 'vol', label: 'Volume', type: 'slider',
      value: 50, min: 0, max: 100, step: 10,
    }
    menu.push({ title: 'Test', items: [slider] })

    menu.right()
    expect(slider.value).toBe(60)
    menu.left(); menu.left()
    expect(slider.value).toBe(40)
  })

  it('push/pop stacks sub-menus', () => {
    const menu = new MenuSystem()
    menu.push({ title: 'Main', items: [{ id: 'a', label: 'A', type: 'button' }] })
    menu.push({ title: 'Sub', items: [{ id: 'b', label: 'B', type: 'button' }] })

    expect(menu.depth).toBe(2)
    expect(menu.currentPage?.title).toBe('Sub')

    menu.pop()
    expect(menu.depth).toBe(1)
    expect(menu.currentPage?.title).toBe('Main')
  })

  it('skips separators in navigation', () => {
    const menu = new MenuSystem()
    menu.push({
      title: 'Test',
      items: [
        { id: 'a', label: 'A', type: 'button' },
        { id: 'sep', label: '---', type: 'separator' },
        { id: 'b', label: 'B', type: 'button' },
      ],
    })
    expect(menu.selectableItems.length).toBe(2)
    menu.down()
    expect(menu.selectedItem?.id).toBe('b')
  })
})

describe('DialogSystem', () => {
  it('displays lines with typewriter', () => {
    const dialog = new DialogSystem()
    dialog.start(DialogSystem.createScript([
      { text: 'Hello world', speed: 100 },
    ]))

    expect(dialog.active).toBe(true)
    expect(dialog.currentText).toBe('')

    dialog.update(0.05)  // 5 chars
    expect(dialog.currentText.length).toBe(5)

    dialog.update(0.1)   // complete
    expect(dialog.isComplete).toBe(true)
    expect(dialog.currentText).toBe('Hello world')
  })

  it('advance skips typewriter then goes to next', () => {
    const dialog = new DialogSystem()
    dialog.start(DialogSystem.createScript([
      { text: 'Line one', speed: 10 },
      { text: 'Line two', speed: 10 },
    ]))

    dialog.advance()  // skip typewriter
    expect(dialog.currentText).toBe('Line one')

    dialog.advance()  // next line
    expect(dialog.fullText).toBe('Line two')
  })

  it('shows choices and waits for selection', () => {
    let chosen = ''
    const dialog = new DialogSystem()
    dialog.start(DialogSystem.createScript([
      {
        text: 'Pick one',
        speed: 0,
        choices: [
          { text: 'Option A', onSelect: () => { chosen = 'A' } },
          { text: 'Option B', onSelect: () => { chosen = 'B' } },
        ],
      },
      { text: 'After choice', speed: 0 },
    ]))

    expect(dialog.isWaitingForChoice).toBe(true)
    dialog.advance()  // should not advance past choices
    expect(dialog.isWaitingForChoice).toBe(true)

    dialog.selectChoice(1)
    expect(chosen).toBe('B')
    expect(dialog.fullText).toBe('After choice')
  })

  it('speaker is tracked', () => {
    const dialog = new DialogSystem()
    dialog.start(DialogSystem.createScript([
      { speaker: 'NPC', text: 'Hello', speed: 0 },
    ]))
    expect(dialog.currentSpeaker).toBe('NPC')
  })

  it('ends when lines exhausted', () => {
    let ended = false
    const dialog = new DialogSystem()
    dialog.onDialogEnd = () => { ended = true }
    dialog.start(DialogSystem.createScript([
      { text: 'Only line', speed: 0 },
    ]))
    dialog.advance()  // complete line
    dialog.advance()  // try next → ends
    expect(ended).toBe(true)
    expect(dialog.active).toBe(false)
  })
})

describe('TutorialSystem', () => {
  it('steps through tutorial', () => {
    const tut = new TutorialSystem()
    const visited: string[] = []

    tut.start([
      { id: 'move', message: 'Use WASD to move', waitForAction: 'move' },
      { id: 'jump', message: 'Press Space to jump', waitForAction: 'jump' },
    ])

    expect(tut.active).toBe(true)
    expect(tut.currentStep?.id).toBe('move')

    tut.notifyAction('move')
    expect(tut.currentStep?.id).toBe('jump')

    tut.notifyAction('jump')
    expect(tut.active).toBe(false)
  })

  it('auto-advances timed steps', () => {
    const tut = new TutorialSystem()
    tut.start([
      { id: 'intro', message: 'Welcome!', duration: 0.5 },
      { id: 'next', message: 'Next step', duration: 0.5 },
    ])

    tut.update(0.6)
    expect(tut.currentStep?.id).toBe('next')
  })

  it('skip ends tutorial', () => {
    let completed = false
    const tut = new TutorialSystem()
    tut.onComplete = () => { completed = true }
    tut.start([
      { id: 'a', message: 'Step A', waitForAction: 'test' },
    ])
    tut.skip()
    expect(tut.active).toBe(false)
    expect(completed).toBe(true)
  })

  it('tracks completed steps', () => {
    const tut = new TutorialSystem()
    tut.start([
      { id: 'a', message: 'A', duration: 0.1 },
      { id: 'b', message: 'B', duration: 0.1 },
    ])
    tut.update(0.2)
    expect(tut.wasCompleted('a')).toBe(true)
  })
})

describe('DifficultyManager', () => {
  it('starts at easy (level 0)', () => {
    const diff = new DifficultyManager()
    diff.setLevel(0)
    expect(diff.get('enemyHealthMul')).toBeCloseTo(0.5)
    expect(diff.get('enemyDamageMul')).toBeCloseTo(0.5)
  })

  it('ramps to hard (level 1)', () => {
    const diff = new DifficultyManager()
    diff.setLevel(1)
    expect(diff.get('enemyHealthMul')).toBeCloseTo(2.0)
    expect(diff.get('enemyDamageMul')).toBeCloseTo(2.0)
  })

  it('S-curve is smooth at midpoint', () => {
    const diff = new DifficultyManager()
    diff.setLevel(0.5)
    // S-curve at 0.5 = 0.5 (midpoint of smoothstep)
    const health = diff.get('enemyHealthMul')
    expect(health).toBeGreaterThan(0.5)
    expect(health).toBeLessThan(2.0)
    expect(health).toBeCloseTo(1.25) // midpoint of 0.5 to 2.0
  })

  it('getAll returns all params', () => {
    const diff = new DifficultyManager()
    diff.setLevel(0)
    const all = diff.getAll()
    expect(all.enemyHealthMul).toBeCloseTo(0.5)
    expect(all.spawnRateMul).toBeCloseTo(0.5)
    expect(all.timeLimitMul).toBeCloseTo(1.5)
  })

  it('advanceByLevel sets correct proportion', () => {
    const diff = new DifficultyManager()
    diff.advanceByLevel(5, 10)
    expect(diff.getLevel()).toBeCloseTo(0.5)
  })

  it('clamps level to 0-1', () => {
    const diff = new DifficultyManager()
    diff.setLevel(-5)
    expect(diff.getLevel()).toBe(0)
    diff.setLevel(99)
    expect(diff.getLevel()).toBe(1)
  })
})

describe('GameFlow', () => {
  it('starts at first step', async () => {
    const sm = new SceneManager()
    sm.add(makeScene('title')).add(makeScene('game')).add(makeScene('gameover'))

    const flow = new GameFlow(sm)
    flow.setFlow([
      { scene: 'title' },
      { scene: 'game' },
      { scene: 'gameover' },
    ])

    await flow.start()
    expect(flow.currentScene).toBe('title')
  })

  it('advances through steps', async () => {
    const sm = new SceneManager()
    sm.add(makeScene('a')).add(makeScene('b')).add(makeScene('c'))

    const flow = new GameFlow(sm)
    flow.setFlow([{ scene: 'a' }, { scene: 'b' }, { scene: 'c' }])
    await flow.start()

    await flow.next()
    expect(flow.currentScene).toBe('b')

    await flow.next()
    expect(flow.currentScene).toBe('c')
  })

  it('loops back to start after last step', async () => {
    const sm = new SceneManager()
    sm.add(makeScene('a')).add(makeScene('b'))

    const flow = new GameFlow(sm)
    flow.setFlow([{ scene: 'a' }, { scene: 'b' }])
    await flow.start()

    await flow.next()
    await flow.next() // loops
    expect(flow.currentScene).toBe('a')
  })

  it('gotoScene jumps to named step', async () => {
    const sm = new SceneManager()
    sm.add(makeScene('title')).add(makeScene('game')).add(makeScene('over'))

    const flow = new GameFlow(sm)
    flow.setFlow([{ scene: 'title' }, { scene: 'game' }, { scene: 'over' }])
    await flow.start()

    await flow.gotoScene('over')
    expect(flow.currentScene).toBe('over')
    expect(flow.currentStep).toBe(2)
  })

  it('pause stops update propagation', async () => {
    const log: string[] = []
    const sm = new SceneManager()
    sm.add(makeScene('a', log))

    const flow = new GameFlow(sm)
    flow.setFlow([{ scene: 'a' }])
    await flow.start()

    log.length = 0
    flow.togglePause()
    expect(flow.isPaused).toBe(true)
    flow.update(0.016)
    expect(log.filter(l => l.startsWith('update'))).toHaveLength(0)

    flow.togglePause()
    flow.update(0.016)
    expect(log.filter(l => l.startsWith('update'))).toHaveLength(1)
  })

  it('condition auto-advances', async () => {
    const sm = new SceneManager()
    sm.add(makeScene('intro')).add(makeScene('game'))

    const flow = new GameFlow(sm)
    flow.setFlow([
      { scene: 'intro', condition: 'introDone' },
      { scene: 'game' },
    ])
    await flow.start()
    expect(flow.currentScene).toBe('intro')

    flow.setCondition('introDone')
    flow.update(0.016)
    expect(flow.currentScene).toBe('game')
  })
})
