// Minimal React surface for the desktop lifecycle tests. Hooks record their state and effects so a
// test can execute a component body synchronously and inspect the JSX tree it returns.

export const hookLog = { effects: [], cleanups: [] }
let cursor = 0
let slots = []
let currentEffects = []

export function __beginRender() {
  cursor = 0
  currentEffects = []
}

export function __endRender() {
  hookLog.effects = currentEffects
  return currentEffects
}

export function useState(initial) {
  const index = cursor++
  if (!(index in slots)) {
    slots[index] = typeof initial === 'function' ? initial() : initial
  }
  const set = value => {
    slots[index] = typeof value === 'function' ? value(slots[index]) : value
  }
  return [slots[index], set]
}

export function useEffect(effect) {
  const entry = { effect, cleanup: null }
  currentEffects.push(entry)
  return entry
}

export function __reset() {
  cursor = 0
  slots = []
  currentEffects = []
  hookLog.effects = []
  hookLog.cleanups = []
}

export function __runEffects() {
  for (const entry of hookLog.effects) {
    if (typeof entry === 'function') {
      const cleanup = entry()
      if (typeof cleanup === 'function') hookLog.cleanups.push(cleanup)
      continue
    }
    const cleanup = entry.effect()
    if (typeof cleanup === 'function') {
      entry.cleanup = cleanup
      hookLog.cleanups.push(cleanup)
    }
  }
}

export default { useState, useEffect }
