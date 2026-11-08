/**
 * Dropdown regression tests.
 *
 * The bug these cover: the brand picker used a native <select>, whose popup is painted by the OS and
 * ignored the Hermes theme. On Windows dark mode it opened as a white sheet with light option text,
 * so the brand list was unreadable. The plugin now renders its own listbox, and these tests pin the
 * behaviour that keeps it usable: no native select anywhere, an accessible combobox/listbox pair,
 * keyboard operation, a visible selected state, and surfaces derived from theme tokens.
 *
 * The stubs build plain trees, so function components are expanded here before assertions run.
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
const sourceText = readFileSync(SOURCE, 'utf8')

async function loadFresh() {
  const dir = await mkdtemp(path.join(tmpdir(), 'salespilot-dropdown-'))
  const body = sourceText
    .replace("from '@hermes/plugin-sdk'", `from '${stubUrl('plugin-sdk.mjs')}'`)
    .replace("from 'react'", `from '${stubUrl('react.mjs')}'`)
    .replace("from 'react/jsx-runtime'", `from '${stubUrl('jsx-runtime.mjs')}'`)
  const file = path.join(dir, 'plugin.mjs')
  await writeFile(file, body, 'utf8')
  return import(`${pathToFileURL(file).href}?v=${Math.random().toString(36).slice(2)}`)
}

// The stub runtime returns {type, props, children}; function components are still unresolved nodes.
function expand(node) {
  if (Array.isArray(node)) return node.map(expand)
  if (!node || typeof node !== 'object') return node
  if (typeof node.type === 'function') {
    const props = { ...node.props }
    if (node.children && node.children.length) props.children = node.children.length === 1 ? node.children[0] : node.children
    return expand(node.type(props))
  }
  return { ...node, children: (node.children || []).map(expand) }
}

function walk(node, visit) {
  if (!node || typeof node !== 'object') return
  visit(node)
  ;(node.children || []).forEach(child => walk(child, visit))
}

function findAll(tree, predicate) {
  const found = []
  walk(tree, node => { if (predicate(node)) found.push(node) })
  return found
}

const byRole = (tree, role) => findAll(tree, node => node.props && node.props.role === role)
const optionRows = tree => findAll(tree, node => node.props && node.props.role === 'option')
const comboOf = tree => findAll(tree, node => node.props && node.props.role === 'combobox')[0]

const BRANDS = {
  active: { id: 'biz_a', display_name: 'Kinetra Mobility' },
  brands: [
    { id: 'biz_a', display_name: 'Kinetra Mobility' },
    { id: 'biz_b', display_name: 'PT Marmer Nusantara Abadi Internasional' }
  ]
}

async function mountBrandSwitch(onSwitch = () => {}) {
  const react = await import(stubUrl('react.mjs'))
  const plugin = await loadFresh()
  react.__reset()
  const render = () => {
    react.__beginRender()
    const tree = expand(plugin.__components.BrandSwitch({ brands: BRANDS, onSwitch }))
    react.__endRender()
    return tree
  }
  return { render }
}

test('the bundle renders no native select at all', () => {
  assert.equal(/h\('select'|jsx\('select'/.test(sourceText), false,
    'a native <select> popup cannot follow the Hermes theme on Windows')
  assert.equal(/sp-native-select/.test(sourceText), false, 'the native select styling is gone too')
})

test('brand picker is a combobox whose closed state shows the active brand', async () => {
  const { render } = await mountBrandSwitch()
  const tree = render()
  const button = comboOf(tree)
  assert.ok(button, 'the brand picker exposes a combobox button')
  assert.equal(button.props['aria-haspopup'], 'listbox')
  assert.equal(button.props['aria-expanded'], 'false')
  assert.equal(button.props['aria-label'], 'Active brand')
  assert.match(JSON.stringify(button), /Kinetra Mobility/, 'the control shows the active brand, not a placeholder')
  assert.equal(byRole(tree, 'listbox').length, 0, 'the list is closed until asked for')
})

test('opening the list marks the active row, with a tick and the brand initials', async () => {
  const { render } = await mountBrandSwitch()
  comboOf(render()).props.onClick()
  const open = render()
  const list = byRole(open, 'listbox')[0]
  assert.ok(list, 'clicking the combobox opens a listbox')
  assert.equal(list.props['aria-label'], 'Active brand')
  const rows = optionRows(open)
  assert.equal(rows.length, 2)
  assert.equal(rows[0].props['aria-selected'], 'true', 'the active brand is the selected row')
  assert.equal(rows[1].props['aria-selected'], 'false')
  assert.match(JSON.stringify(rows[0]), /sp-dd-check/, 'the selected row carries a visible tick')
  assert.equal(comboOf(open).props['aria-expanded'], 'true')
  assert.match(JSON.stringify(open), /sp-avatar/, 'the brand initial still sits beside the picker')
})

test('a long brand name stays readable: full text in the title, ellipsis in the row', async () => {
  const { render } = await mountBrandSwitch()
  comboOf(render()).props.onClick()
  const rows = optionRows(render())
  assert.equal(rows[1].props.title, 'PT Marmer Nusantara Abadi Internasional')
  assert.match(JSON.stringify(rows[1]), /sp-dd-opt-label/)
  assert.match(sourceText, /\.sp-dd-opt-label\{[^}]*text-overflow:ellipsis/)
  assert.match(sourceText, /\.sp-dd-menu\{[^}]*max-height:264px[^}]*overflow-y:auto/,
    'a long list scrolls instead of growing past the window')
  assert.match(sourceText, /\.sp-brand-pick \.sp-dd\{flex:0 0 auto;width:auto/, 'the header picker sizes to its label instead of collapsing in a flex row')
  assert.match(sourceText, /\.sp-brand-pick \.sp-dd-label\{max-width:190px\}/, 'a long name is capped, not wide enough to push the tabs away')
})

test('keyboard: arrows open and move, Enter picks, Escape closes without choosing', async () => {
  const picked = []
  const { render } = await mountBrandSwitch(id => picked.push(id))
  const noop = () => {}

  comboOf(render()).props.onKeyDown({ key: 'ArrowDown', preventDefault: noop })
  let open = render()
  assert.equal(byRole(open, 'listbox').length, 1, 'ArrowDown opens the list')
  assert.equal(optionRows(open)[0].props['data-active'], 'true', 'the active brand is highlighted first')

  byRole(open, 'listbox')[0].props.onKeyDown({ key: 'ArrowDown', preventDefault: noop })
  open = render()
  assert.equal(optionRows(open)[1].props['data-active'], 'true', 'ArrowDown moves the highlight')

  byRole(open, 'listbox')[0].props.onKeyDown({ key: 'Enter', preventDefault: noop })
  open = render()
  assert.deepEqual(picked, ['biz_b'], 'Enter selects the highlighted brand')
  assert.equal(byRole(open, 'listbox').length, 0, 'the list closes after choosing')

  comboOf(open).props.onKeyDown({ key: 'ArrowDown', preventDefault: noop })
  open = render()
  byRole(open, 'listbox')[0].props.onKeyDown({ key: 'Escape', preventDefault: noop })
  open = render()
  assert.equal(byRole(open, 'listbox').length, 0, 'Escape closes the list')
  assert.deepEqual(picked, ['biz_b'], 'Escape changed nothing')
})

test('choosing the brand that is already active does not fire a switch', async () => {
  const picked = []
  const { render } = await mountBrandSwitch(id => picked.push(id))
  comboOf(render()).props.onClick()
  optionRows(render())[0].props.onClick()
  render()
  assert.deepEqual(picked, [], 'the active brand is a no-op, not a redundant backend write')
})

test('menu surfaces come from theme tokens, never a hard-coded white', () => {
  const menuRule = sourceText.match(/\.sp-dd-menu\{[^}]+\}/)[0]
  assert.match(menuRule, /background:var\(--sp-menu\)/, 'the menu uses the themed surface token')
  assert.match(menuRule, /color:var\(--sp-text\)/, 'the menu text follows the theme')
  assert.match(sourceText, /--sp-menu:color-mix\(in srgb,var\(--sp-text\) 7%,var\(--sp-bg\)\)/,
    'the surface is mixed from the theme text colour, so it lifts in dark and settles in light')
  assert.equal(/background:\s*#fff|background:\s*white/i.test(menuRule), false, 'no white sheet')
  assert.match(sourceText, /\.sp-app\{color-scheme:light/, 'native controls follow the light theme')
  assert.match(sourceText, /\.dark \.sp-app\{color-scheme:dark/, 'native controls follow the dark theme')
  assert.match(sourceText, /\.sp-dd-opt\[aria-selected=true\]\{[^}]*var\(--sp-accent\)/,
    'the selected row is tinted with the accent, so it is visible in both themes')
  assert.match(sourceText, /\.sp-dd-opt\[data-active=true\]\{[^}]*var\(--sp-text\)/,
    'hover uses a text-derived wash, which works on either surface')
})

test('the import column pickers share the same dropdown, so they cannot regress', () => {
  assert.match(sourceText, /h\(Select, \{\s*key: `\$\{name\}-c`/, 'the CSV mapping uses the shared dropdown')
  assert.match(sourceText, /options: \[\{ value: '', label: 'Skip column' \}\]\.concat\(FIELDS\.map/, 'Skip column stays the default mapping')
  assert.match(sourceText, /\.sp-dialog\{[^}]*overflow:visible/, 'the dialog lets the menu escape its bounds')
})
