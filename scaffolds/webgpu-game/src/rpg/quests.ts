/**
 * Quest system — track objectives, check completion, grant rewards.
 */

import type { RPGPlayer } from './rpg_player'

export type QuestStatus = 'inactive' | 'active' | 'complete' | 'turned_in'

export interface QuestObjective {
  type: 'collect' | 'kill' | 'talk' | 'reach'
  target: string       // item ID, NPC sprite, NPC ID, or map name
  required: number
  current: number
  description: string
}

export interface Quest {
  id: string
  name: string
  description: string
  giver: string        // NPC ID who gives/completes the quest
  status: QuestStatus
  objectives: QuestObjective[]
  rewards: { itemId: string; name: string; count: number }[]
  xpReward: number
  dialog: {
    offer: string[]     // dialog when offering quest
    progress: string[]  // dialog when in progress
    complete: string[]  // dialog when objectives met
    done: string[]      // dialog after turn-in
  }
}

export class QuestSystem {
  quests: Quest[] = []
  onQuestStart?: (quest: Quest) => void
  onQuestComplete?: (quest: Quest) => void
  onObjectiveProgress?: (quest: Quest, obj: QuestObjective) => void

  constructor() {
    this.quests = createDefaultQuests()
  }

  /** Get active quests. */
  getActive(): Quest[] {
    return this.quests.filter(q => q.status === 'active')
  }

  /** Get quest dialog for an NPC — returns the right dialog based on quest state. */
  getQuestDialog(npcId: string): string[] | null {
    for (const q of this.quests) {
      if (q.giver !== npcId) continue
      switch (q.status) {
        case 'inactive': return q.dialog.offer
        case 'active':
          // Check if objectives are met
          if (q.objectives.every(o => o.current >= o.required)) {
            return q.dialog.complete
          }
          return q.dialog.progress
        case 'complete': return q.dialog.complete
        case 'turned_in': return q.dialog.done
      }
    }
    return null
  }

  /** Accept a quest from an NPC. */
  acceptQuest(npcId: string): Quest | null {
    const quest = this.quests.find(q => q.giver === npcId && q.status === 'inactive')
    if (!quest) return null
    quest.status = 'active'
    this.onQuestStart?.(quest)
    return quest
  }

  /** Try to turn in a quest to an NPC. */
  turnInQuest(npcId: string, player: RPGPlayer): Quest | null {
    const quest = this.quests.find(q =>
      q.giver === npcId &&
      (q.status === 'active' || q.status === 'complete') &&
      q.objectives.every(o => o.current >= o.required)
    )
    if (!quest) return null

    // Remove collected items from inventory
    for (const obj of quest.objectives) {
      if (obj.type === 'collect') {
        player.inventory.remove(obj.target, obj.required)
      }
    }

    // Grant rewards
    for (const reward of quest.rewards) {
      player.inventory.add(
        { id: reward.itemId, name: reward.name, maxStack: 10, category: 'reward' },
        reward.count
      )
    }

    quest.status = 'turned_in'
    this.onQuestComplete?.(quest)
    return quest
  }

  /** Notify kill event — updates kill objectives. */
  notifyKill(enemySprite: string): void {
    for (const q of this.quests) {
      if (q.status !== 'active') continue
      for (const obj of q.objectives) {
        if (obj.type === 'kill' && obj.target === enemySprite && obj.current < obj.required) {
          obj.current++
          this.onObjectiveProgress?.(q, obj)
        }
      }
    }
  }

  /** Notify item collected — updates collect objectives. */
  notifyCollect(itemId: string): void {
    for (const q of this.quests) {
      if (q.status !== 'active') continue
      for (const obj of q.objectives) {
        if (obj.type === 'collect' && obj.target === itemId && obj.current < obj.required) {
          obj.current++
          this.onObjectiveProgress?.(q, obj)
        }
      }
    }
  }

  /** Notify map reached. */
  notifyReach(mapName: string): void {
    for (const q of this.quests) {
      if (q.status !== 'active') continue
      for (const obj of q.objectives) {
        if (obj.type === 'reach' && obj.target === mapName && obj.current < obj.required) {
          obj.current = obj.required
          this.onObjectiveProgress?.(q, obj)
        }
      }
    }
  }

  serialize(): { id: string; status: QuestStatus; objectives: { current: number }[] }[] {
    return this.quests.map(q => ({
      id: q.id,
      status: q.status,
      objectives: q.objectives.map(o => ({ current: o.current })),
    }))
  }

  deserialize(data: { id: string; status: QuestStatus; objectives: { current: number }[] }[]): void {
    for (const saved of data) {
      const quest = this.quests.find(q => q.id === saved.id)
      if (!quest) continue
      quest.status = saved.status
      for (let i = 0; i < saved.objectives.length && i < quest.objectives.length; i++) {
        quest.objectives[i].current = saved.objectives[i].current
      }
    }
  }
}

function createDefaultQuests(): Quest[] {
  return [
    {
      id: 'wolf_hunt',
      name: 'Wolf Hunt',
      description: 'Clear the wolves from the Dark Forest.',
      giver: 'elder',
      status: 'inactive',
      objectives: [
        { type: 'kill', target: 'rpg_wolf', required: 3, current: 0, description: 'Kill wolves (0/3)' },
      ],
      rewards: [
        { itemId: 'gold', name: 'Gold', count: 50 },
      ],
      xpReward: 100,
      dialog: {
        offer: [
          'Our village is threatened by wolves in the Dark Forest.',
          'Will you hunt them for us? Slay 3 wolves and return.',
          '[Quest: Wolf Hunt — Kill 3 wolves]',
        ],
        progress: [
          'The wolves still roam the forest. Keep fighting!',
        ],
        complete: [
          'You\'ve done it! The forest is safe again.',
          'Here is your reward, brave adventurer.',
          '[Quest Complete: Wolf Hunt — 50 Gold]',
        ],
        done: [
          'Thank you again for saving our village.',
        ],
      },
    },
    {
      id: 'merchant_pelts',
      name: 'Merchant\'s Request',
      description: 'Bring 2 wolf pelts to Merchant Greta.',
      giver: 'merchant',
      status: 'inactive',
      objectives: [
        { type: 'collect', target: 'wolf_pelt', required: 2, current: 0, description: 'Collect wolf pelts (0/2)' },
      ],
      rewards: [
        { itemId: 'iron_shield', name: 'Iron Shield', count: 1 },
      ],
      xpReward: 75,
      dialog: {
        offer: [
          'Business has been terrible with the wolves about.',
          'Bring me 2 wolf pelts and I\'ll craft you a fine shield!',
          '[Quest: Merchant\'s Request — Collect 2 Wolf Pelts]',
        ],
        progress: [
          'Still need those pelts! Try the Dark Forest.',
        ],
        complete: [
          'Perfect pelts! As promised, here\'s your shield.',
          '[Quest Complete: Merchant\'s Request — Iron Shield]',
        ],
        done: [
          'That shield should serve you well!',
        ],
      },
    },
  ]
}
