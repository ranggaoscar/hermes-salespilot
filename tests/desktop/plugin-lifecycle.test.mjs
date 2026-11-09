/**
 * Desktop lifecycle regression tests for the SalesPilot bundle.
 *
 * These run the REAL desktop/plugin.js (not a copy of its logic) against tiny stubs for the plugin
 * SDK, React and the JSX runtime, so the checks cover the failure modes this bundle actually hit:
 *   - "Cannot access 'icp' before initialization" (temporal dead zone in the Settings component)
 *   - duplicate page/nav registration that produced a second Customers view
 *   - background polling that keeps rendering (and re-fronting) a hidden pane
 *   - any navigation/focus call made by the plugin itself
 *
 * Run with: node --test tests/desktop/
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SOURCE = path.join(HERE, '..', '..', 'desktop', 'plugin.js')
const STUBS = path.join(HERE, 'stubs')

const stubUrl = name => pathToFileURL(path.join(STUBS, name)).href

async function loadFresh() {
  const dir = await mkdtemp(path.join(tmpdir(), 'salespilot-desktop-'))
  const body = readFileSync(SOURCE, 'utf8')
    .replace("from '@hermes/plugin-sdk'", `from '${stubUrl('plugin-sdk.mjs')}'`)
    .replace("from 'react'", `from '${stubUrl('react.mjs')}'`)
    .replace("from 'react/jsx-runtime'", `from '${stubUrl('jsx-runtime.mjs')}'`)
  const file = path.join(dir, 'plugin.mjs')
  await writeFile(file, body, 'utf8')
  return import(`${pathToFileURL(file).href}?v=${Math.random().toString(36).slice(2)}`)
}

function textOf(node) {
  if (node === null || node === undefined) return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join(' ')
  if (typeof node === 'object') {
    const own = node.children ? textOf(node.children) : ''
    const props = node.props ? textOf(Object.values(node.props)) : ''
    return `${own} ${props}`.trim()
  }
  return ''
}

// Models the host registry: register() replaces same area+id in place and hands back a disposer that
// removes it, so a test can reproduce the host's dispose -> register reload cycle.
function makeCtx() {
  const registered = []
  return {
    registered,
    register: contribution => {
      const existing = registered.findIndex(row => row.id === contribution.id && row.area === contribution.area)
      if (existing >= 0) registered[existing] = contribution
      else registered.push(contribution)
      return () => {
        const index = registered.findIndex(row => row.id === contribution.id && row.area === contribution.area)
        if (index >= 0) registered.splice(index, 1)
      }
    },
    rest: async route => ({ ok: true, route }),
    navigate: () => { throw new Error('the plugin must never navigate on its own') }
  }
}

function installBrowserStubs({ hidden = false } = {}) {
  const intervals = { armed: [], cleared: 0 }
  const realSetInterval = globalThis.setInterval
  const realClearInterval = globalThis.clearInterval

  globalThis.document = { visibilityState: hidden ? 'hidden' : 'visible' }
  globalThis.window = { setTimeout: (fn, ms) => setTimeout(fn, ms) }
  globalThis.setInterval = (fn, ms) => {
    intervals.armed.push({ fn, ms })
    return { stub: true }
  }
  globalThis.clearInterval = () => { intervals.cleared += 1 }

  return {
    intervals,
    restore() {
      globalThis.setInterval = realSetInterval
      globalThis.clearInterval = realClearInterval
      delete globalThis.document
      delete globalThis.window
    }
  }
}

test('Settings renders without the icp temporal-dead-zone crash', async () => {
  const react = await import(stubUrl('react.mjs'))
  react.__reset()
  const plugin = await loadFresh()
  const { Setup } = plugin.__components

  react.__beginRender()
  const tree = Setup({
    data: {
      business: { name: 'Kinetra Mobility' },
      mail: {},
      icp: { status: 'configured', industries: ['logistics'], locations: ['Jakarta'], buyer_roles: ['Fleet Manager'], issues: [] }
    },
    setSection: () => {}
  })
  react.__endRender()

  const text = textOf(tree)
  assert.match(text, /Ideal customer profile/)
  assert.match(text, /logistics/)
})

test('Save sender requires explicit confirmation naming SMTP destination and sender', async () => {
  const react = await import(stubUrl('react.mjs'))
  const plugin = await loadFresh()
  const requests = []
  const ctx = makeCtx()
  ctx.rest = async (...args) => { requests.push(args); return { ok: true } }
  plugin.default.register(ctx)
  const data = { ok: true, business_id: 'synthetic', business: { name: 'Fictional Co' },
    mail: { host: 'smtp.operator.example', port: 465, security: 'tls', from_address: 'sales@example.com', from_name: 'Operator' } }
  react.__reset()
  react.__beginRender()
  const tree = plugin.__components.Setup({ data })
  react.__endRender()
  function findSave(node) {
    if (!node || typeof node !== 'object') return null
    if (node.props && node.props.onClick && textOf(node.children).trim() === 'Save sender') return node
    for (const child of (Array.isArray(node) ? node : [node.children, ...Object.values(node.props || {})])) {
      const found = findSave(child)
      if (found) return found
    }
    return null
  }
  const button = findSave(tree)
  assert.ok(button, 'real Settings component exposes Save sender')
  try {
    globalThis.window = { confirm: prompt => {
      for (const text of ['smtp.operator.example:465', 'tls', 'sales@example.com', 'Operator']) assert.ok(prompt.includes(text))
      return false
    } }
    button.props.onClick()
    assert.equal(requests.length, 0, 'cancel must not persist transport')
    window.confirm = () => true
    button.props.onClick()
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(requests.length, 1)
    assert.equal(requests[0][1].body.confirm_transport, true)
    assert.equal(requests[0][1].body.host, 'smtp.operator.example')
    delete window.confirm
    button.props.onClick()
    assert.equal(requests.length, 1, 'missing confirmation API must fail closed')
  } finally { delete globalThis.window }
})

test('Settings survives a missing or malformed ICP payload', async () => {
  const react = await import(stubUrl('react.mjs'))
  const plugin = await loadFresh()
  const { Setup } = plugin.__components

  for (const data of [null, {}, { icp: 'not-an-object' }, { icp: { industries: 'logistics', buyer_roles: null } }]) {
    react.__reset()
    react.__beginRender()
    assert.doesNotThrow(() => Setup({ data, setSection: () => {} }), `Setup threw for ${JSON.stringify(data)}`)
    react.__endRender()
  }

  const normalized = plugin.__components.safeIcp({ icp: { industries: 'logistics', status: 'configured' } })
  assert.deepEqual(normalized.industries, [], 'a string must not be treated as a list')
  assert.deepEqual(normalized.locations, [])
})

test('register() is idempotent: a rescan cannot add a second page or nav row', async () => {
  const plugin = await loadFresh()
  const ctx = makeCtx()

  plugin.default.register(ctx)
  plugin.default.register(ctx)
  plugin.default.register(ctx)

  const pages = ctx.registered.filter(row => row.area === 'routes')
  const navs = ctx.registered.filter(row => row.area === 'sidebar.nav')
  assert.equal(pages.length, 1, 'exactly one page contribution')
  assert.equal(navs.length, 1, 'exactly one sidebar row')
  assert.equal(pages[0].data.path, '/salespilot')
  assert.equal(pages[0].title, 'SalesPilot', 'a stable title stops the pane re-registering after reload')
  assert.equal(navs[0].data.path, '/salespilot')
  assert.equal(plugin.__state().cycleActive, true)
  assert.equal(plugin.__state().disposers, 2, 'both contributions keep their disposer')
})

test('dispose then register again restores the page and nav: a reload cannot leave the plugin missing', async () => {
  const plugin = await loadFresh()
  const first = makeCtx()
  const dispose = plugin.default.register(first)
  assert.equal(first.registered.length, 2)

  assert.equal(typeof dispose, 'function', 'register() must hand the host a disposer')
  dispose()
  assert.equal(first.registered.length, 0, 'dispose removes both contributions')
  assert.equal(plugin.__state().cycleActive, false, 'the cycle is closed after dispose')

  const second = makeCtx()
  plugin.default.register(second)
  const areas = second.registered.map(row => row.area).sort()
  assert.deepEqual(areas, ['routes', 'sidebar.nav'], 'the plugin comes back after a rescan')
  assert.equal(plugin.__state().disposers, 2)
})

test('a stale cycle that was never disposed cannot stack on a new one', async () => {
  const plugin = await loadFresh()
  const first = makeCtx()
  const second = makeCtx()

  plugin.default.register(first)
  plugin.default.register(second)

  assert.equal(first.registered.length, 0, 'the stale cycle is disposed, not left stacked')
  assert.equal(second.registered.length, 2, 'the new cycle registers both contributions')
  const live = second.registered.map(row => row.area).sort()
  assert.deepEqual(live, ['routes', 'sidebar.nav'], 'the sidebar row comes back after a reload')
})

test('the bundle never navigates, focuses or opens a window on its own', async () => {
  const sdk = await import(stubUrl('plugin-sdk.mjs'))
  const plugin = await loadFresh()
  const ctx = makeCtx()

  for (const key of Object.keys(sdk.calls)) sdk.calls[key] = 0
  plugin.default.register(ctx)
  assert.deepEqual(sdk.calls, { navigate: 0, focus: 0, openRoute: 0, window: 0 })
})

test('background polling is skipped while the window is hidden and stops on unmount', async () => {
  const browser = installBrowserStubs({ hidden: true })
  const react = await import(stubUrl('react.mjs'))
  const sdk = await import(stubUrl('plugin-sdk.mjs'))
  try {
    const plugin = await loadFresh()
    const ctx = makeCtx()
    plugin.default.register(ctx)
    const routeCalls = []
    ctx.rest = async route => { routeCalls.push(route); return { ok: true } }

    react.__reset()
    react.__beginRender()
    plugin.__components.Page()
    react.__endRender()
    react.__runEffects()

    const before = routeCalls.length
    assert.ok(browser.intervals.armed.length >= 1, 'a refresh timer is armed while the pane is mounted')

    for (const timer of browser.intervals.armed) timer.fn()
    assert.equal(routeCalls.length, before, 'a hidden window must not poll')

    for (const cleanup of react.hookLog.cleanups) cleanup()
    assert.ok(browser.intervals.cleared >= 1, 'unmount clears the timer')
    assert.deepEqual(sdk.calls, { navigate: 0, focus: 0, openRoute: 0, window: 0 })
  } finally {
    browser.restore()
  }
})

test('repeated mount/unmount keeps state isolated and never throws', async () => {
  const browser = installBrowserStubs({ hidden: false })
  const react = await import(stubUrl('react.mjs'))
  try {
    for (let round = 0; round < 3; round += 1) {
      const plugin = await loadFresh()
      const ctx = makeCtx()
      plugin.default.register(ctx)
      react.__reset()
      react.__beginRender()
      assert.doesNotThrow(() => plugin.__components.Page())
      react.__endRender()
      react.__runEffects()
      for (const cleanup of react.hookLog.cleanups) cleanup()
    }
  } finally {
    browser.restore()
  }
})

test('journey: cold or stopped prospects leave the work list, replies and follow-ups are surfaced', async () => {
  const plugin = await loadFresh()
  const { stageOf, Today } = plugin.__components
  assert.equal(stageOf({ status: 'contacted', followup: { state: 'cold' } }), 'closed')
  assert.equal(stageOf({ status: 'contacted', followup: { state: 'followup_due' } }), 'followup')
  assert.equal(stageOf({ status: 'replied', followup: { state: 'replied' } }), 'replied')
  assert.equal(stageOf({ status: 'discovered' }), 'collect')
  assert.equal(Today({ prospects: [{ id: 'a', status: 'discovered' }], drafts: [], onOpen: () => {} }), null, 'nothing due means no Today card')
  const tree = Today({ prospects: [
    { id: 'r', company: 'Replier', status: 'replied', followup: { state: 'replied' }, last_reply_excerpt: 'Kami tertarik' },
    { id: 'f', company: 'Due Co', status: 'contacted', followup: { state: 'followup_due' } },
    { id: 'd', company: 'Draft Co', status: 'draft_ready' }
  ], drafts: [{ id: 'dft', lead_id: 'd' }], onOpen: () => {} })
  const text = textOf(tree)
  for (const word of ['Replier', 'Kami tertarik', 'Due Co', 'Draft Co', 'Follow up today']) assert.match(text, new RegExp(word))
})

test('CSV header parsing keeps raw names and guesses Indonesian columns', async () => {
  const plugin = await loadFresh()
  const { csvHeader, guessMapping } = plugin.__components
  const headers = csvHeader('﻿Nama Perusahaan,"PIC, Sales",E-mail,No HP,Catatan\nx,y,z,1,n')
  assert.deepEqual(headers, ['Nama Perusahaan', 'PIC, Sales', 'E-mail', 'No HP', 'Catatan'])
  assert.deepEqual(guessMapping(headers), { 'Nama Perusahaan': 'company', 'E-mail': 'email', 'No HP': 'phone', 'PIC, Sales': 'contact_name', Catatan: 'notes' })
})

test('getting-started checklist disappears once every step is done', async () => {
  const plugin = await loadFresh()
  const { Checklist } = plugin.__components
  const done = { business_id: 'b', business: { products: 'x', target_market: 'y' }, mail: { connection: 'connected' }, icp: { status: 'configured', industries: ['a'] } }
  assert.equal(Checklist({ setup: done, hasCustomers: true }), null)
  assert.match(textOf(Checklist({ setup: { ...done, mail: { connection: 'not_configured' } }, hasCustomers: false })), /2 of 4 done/)
})

test('approval is its own journey step: a drafted customer waits on the user, not in Prepare', async () => {
  const plugin = await loadFresh()
  const { stageOf, Today } = plugin.__components
  assert.equal(stageOf({ status: 'draft_ready' }), 'approve')
  assert.equal(stageOf({ status: 'qualified' }), 'prepare')
  const text = textOf(Today({ prospects: [{ id: 'd', company: 'Draft Co', status: 'draft_ready' }], drafts: [], onOpen: () => {} }))
  assert.match(text, /Waiting for your approval/)
  assert.match(text, /send with approval/)
})

test('errors read as sentences: known backend codes never reach the user raw', async () => {
  const plugin = await loadFresh()
  const { errText } = plugin.__components
  assert.match(errText({ ok: false, code: 'imap_not_configured', error: 'Save IMAP settings before syncing.' }, 'x'), /Reply tracking is off/)
  assert.equal(errText({ ok: false, code: 'some_new_code' }, 'x'), 'some new code')
  assert.equal(errText({ ok: false, error: 'Specific failure.' }, 'x'), 'Specific failure.')
  assert.equal(errText(null, 'fallback'), 'fallback')
})

test('what works today never claims an unsupported feature works', async () => {
  const plugin = await loadFresh()
  const { capabilities } = plugin.__components
  const rows = Object.fromEntries(capabilities({ connection: 'not_configured' }, {}).map(([label, state]) => [label, state]))
  assert.equal(rows['Separate mailbox per brand'], 'Not yet')
  assert.equal(rows['Automatic sending'], 'Never')
  assert.equal(rows['Send after approval'], 'Set up', 'an unconnected mailbox is not shown as ready')
  assert.equal(rows['Reply tracking'], 'Set up', 'reply sync without IMAP is not shown as on')
  const live = Object.fromEntries(capabilities({ connection: 'connected' }, { configured: true }).map(([label, state]) => [label, state]))
  assert.equal(live['Send after approval'], 'Ready')
  assert.equal(live['Reply tracking'], 'On')
  const untested = Object.fromEntries(capabilities({ connection: 'unverified', configured: true }, {}).map(([l, s]) => [l, s]))
  assert.equal(untested['Send after approval'], 'Untested', 'saved credentials that never passed a test are not "Ready"')
  const off = Object.fromEntries(capabilities({ connection: 'connected', research_only: false, configured: true }, {}).map(([l, s]) => [l, s]))
  assert.equal(off['Reply tracking'], 'Set up')
})
