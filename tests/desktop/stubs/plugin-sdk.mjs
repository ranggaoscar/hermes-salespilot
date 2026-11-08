// Minimal stand-in for '@hermes/plugin-sdk' used by the desktop lifecycle tests.
// Only the surface the SalesPilot bundle touches: host, area constants and useValue.

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'

export const calls = { navigate: 0, focus: 0, openRoute: 0, window: 0 }

export const host = {
  state: {
    gateway: { get: () => 'open', listen: () => () => {} }
  },
  navigate: () => { calls.navigate += 1 },
  focus: () => { calls.focus += 1 },
  openRoute: () => { calls.openRoute += 1 },
  openWindow: () => { calls.window += 1 }
}

export function useValue(atom) {
  return atom && typeof atom.get === 'function' ? atom.get() : atom
}
