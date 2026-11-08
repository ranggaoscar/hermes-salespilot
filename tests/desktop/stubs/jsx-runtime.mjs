// Minimal jsx/jsxs for the lifecycle tests: build plain trees instead of React elements.

function build(type, props, key) {
  const { children, ...rest } = props || {}
  const flat = []
  const push = value => {
    if (Array.isArray(value)) value.forEach(push)
    else if (value !== null && value !== undefined && value !== false) flat.push(value)
  }
  push(children)
  return { type, key, props: rest, children: flat }
}

export function jsx(type, props, key) {
  return build(type, props, key)
}

export function jsxs(type, props, key) {
  return build(type, props, key)
}

export const Fragment = Symbol('Fragment')
