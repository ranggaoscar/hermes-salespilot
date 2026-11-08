import { host, ROUTES_AREA, SIDEBAR_NAV_AREA, useValue } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const VERSION = '1.1.0'
const GITHUB = 'https://github.com/ranggaoscar'

// ---------------------------------------------------------------------------------------------
// Design tokens. Structure (text, lines, surfaces) comes from the host theme so SalesPilot sits
// inside Hermes in light and dark; the identity is the jade signal accent and the ember heat tone.
// ---------------------------------------------------------------------------------------------
const CSS = `
.sp-app{--sp-text:var(--ui-text-primary,var(--foreground));--sp-text-2:var(--ui-text-secondary,var(--muted-foreground));--sp-text-3:var(--ui-text-tertiary,var(--muted-foreground));--sp-text-4:var(--ui-text-quaternary,var(--muted-foreground));--sp-line:var(--ui-stroke-tertiary,var(--border));--sp-line-soft:var(--ui-stroke-quaternary,var(--border));--sp-bg:var(--ui-bg-editor,var(--background));--sp-raised:color-mix(in srgb,var(--sp-text) 2.5%,var(--sp-bg));--sp-sunk:color-mix(in srgb,var(--sp-text) 4.5%,var(--sp-bg));--sp-hover:color-mix(in srgb,var(--sp-text) 5%,transparent);--sp-active:color-mix(in srgb,var(--sp-accent) 9%,transparent);--sp-accent:#23735d;--sp-accent-ink:#fff;--sp-heat:#b8641a;--sp-blue:#3563c9;--sp-violet:#6b55c4;--sp-green:#23735d;--sp-amber:#a8650f;--sp-red:#c2364f;--sp-shadow:0 1px 2px rgba(15,15,20,.06),0 8px 24px -12px rgba(15,15,20,.18);height:100%;display:flex;flex-direction:column;overflow:hidden;color:var(--sp-text);background:var(--sp-bg);font:13px/1.5 var(--font-sans,inherit);-webkit-font-smoothing:antialiased}
.dark .sp-app{--sp-accent:#4fb894;--sp-accent-ink:#06120e;--sp-heat:#e09a52;--sp-blue:#7c9cf0;--sp-violet:#a796f0;--sp-green:#4fb894;--sp-amber:#e0a14a;--sp-red:#ec6f86;--sp-shadow:0 1px 2px rgba(0,0,0,.4),0 12px 32px -14px rgba(0,0,0,.7)}
.sp-app *{box-sizing:border-box}
.sp-app button{font:inherit;color:inherit}
.sp-app a{color:inherit;text-decoration:underline;text-decoration-color:var(--sp-line);text-underline-offset:2px}
.sp-app a:hover{text-decoration-color:currentColor}
.sp-top{display:flex;align-items:center;gap:16px;height:52px;padding:0 20px;border-bottom:1px solid var(--sp-line-soft);flex:none}
.sp-logo{display:flex;align-items:center;gap:8px;font-weight:600;letter-spacing:-.01em;font-size:13.5px;white-space:nowrap}
.sp-mark{width:20px;height:20px;color:var(--sp-accent);flex:none}
.sp-mark-tile{width:24px;height:24px;border-radius:7px;flex:none;display:inline-flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#27805f,#1b5f4a);color:#f6f3ec;box-shadow:inset 0 0 0 1px rgba(255,255,255,.08),0 1px 2px rgba(10,30,24,.25)}
.sp-mark-tile svg{width:18px;height:18px;--sp-heat:#f0a35e}
.sp-logo span{letter-spacing:-.015em}
.sp-sep{width:1px;height:18px;background:var(--sp-line)}
.sp-tabs{display:flex;gap:2px;margin-left:4px}
.sp-tab{position:relative;display:flex;align-items:center;gap:6px;border:0;background:transparent;padding:6px 10px;border-radius:7px;color:var(--sp-text-3);cursor:pointer;font-weight:500}
.sp-tab:hover{color:var(--sp-text);background:var(--sp-hover)}
.sp-tab[aria-selected=true]{color:var(--sp-text);background:var(--sp-sunk)}
.sp-tab .sp-badge{min-width:18px;height:18px;padding:0 5px;border-radius:9px;font-size:11px;display:inline-flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--sp-heat) 16%,transparent);color:var(--sp-heat);font-variant-numeric:tabular-nums}
.sp-spacer{flex:1}
.sp-body{flex:1;min-height:0;overflow:auto}
.sp-page{max-width:1240px;margin:0 auto;padding:24px 28px 56px;display:flex;flex-direction:column;gap:20px}
.sp-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
.sp-h1{margin:0;font-size:20px;line-height:1.2;font-weight:600;letter-spacing:-.02em}
.sp-sub{margin:4px 0 0;color:var(--sp-text-3);font-size:13px}
.sp-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sp-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:30px;padding:0 11px;border-radius:7px;border:1px solid var(--sp-line);background:var(--sp-bg);cursor:pointer;font-weight:500;white-space:nowrap;transition:background .12s,border-color .12s,transform .06s}
.sp-btn:hover{background:var(--sp-hover)}
.sp-btn:active{transform:translateY(.5px)}
.sp-btn:disabled{opacity:.5;cursor:default;transform:none}
.sp-btn svg{width:14px;height:14px;flex:none}
.sp-btn-primary{background:var(--sp-accent);border-color:var(--sp-accent);color:var(--sp-accent-ink)}
.sp-btn-primary:hover{background:color-mix(in srgb,var(--sp-accent) 88%,#000)}
.sp-btn-ghost{border-color:transparent;background:transparent;color:var(--sp-text-2)}
.sp-btn-ghost:hover{color:var(--sp-text)}
.sp-btn-danger{color:var(--sp-red)}
.sp-btn-sm{height:26px;padding:0 8px;font-size:12px}
.sp-icon-btn{width:28px;height:28px;padding:0}
/* Native <select> popups are painted by the OS: on Windows they render as a white sheet that ignores
   the host theme, so white option text lands on white. Every dropdown in this plugin is therefore a
   small listbox we own. Surfaces are derived from the host text colour, which keeps the menu legible
   in both themes: 7% of near-white over a dark page reads as a raised panel, 7% of near-black over a
   light page reads as a subtle grey. */
.sp-app{color-scheme:light;--sp-menu:color-mix(in srgb,var(--sp-text) 7%,var(--sp-bg));--sp-menu-shadow:0 10px 30px -12px rgba(15,15,20,.28),0 2px 6px rgba(15,15,20,.08)}
.dark .sp-app{color-scheme:dark;--sp-menu-shadow:0 16px 40px -16px rgba(0,0,0,.75),0 2px 8px rgba(0,0,0,.45)}
.sp-brand-pick{display:flex;align-items:center;gap:8px;min-width:0}
.sp-dd{position:relative;min-width:0}
/* The picker must size to its label: inside a flex row a bare width:100% collapses to the avatar
   width and the name disappears. */
.sp-brand-pick .sp-dd{flex:0 0 auto;width:auto;min-width:auto;max-width:260px}
.sp-brand-pick .sp-dd-btn{width:auto;max-width:260px}
.sp-brand-pick .sp-dd-label{max-width:190px}
.sp-dd-btn{display:flex;align-items:center;gap:6px;width:100%;height:30px;padding:0 26px 0 9px;border:1px solid var(--sp-line);border-radius:7px;background:var(--sp-bg);color:var(--sp-text);font:inherit;font-weight:500;text-align:left;cursor:pointer;position:relative;transition:background .12s,border-color .12s,box-shadow .12s}
.sp-dd-btn:hover{background:var(--sp-hover)}
.sp-dd-btn[aria-expanded=true]{border-color:color-mix(in srgb,var(--sp-accent) 55%,var(--sp-line));box-shadow:0 0 0 3px color-mix(in srgb,var(--sp-accent) 13%,transparent)}
.sp-dd-btn:focus-visible{outline:2px solid color-mix(in srgb,var(--sp-accent) 55%,transparent);outline-offset:1px}
.sp-dd-btn:disabled{opacity:.55;cursor:default}
.sp-dd-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sp-dd-btn svg.sp-caret{position:absolute;right:8px;width:12px;height:12px;color:var(--sp-text-3);pointer-events:none;transition:transform .12s}
.sp-dd-btn[aria-expanded=true] svg.sp-caret{transform:rotate(180deg)}
.sp-dd-menu{position:absolute;z-index:60;top:calc(100% + 4px);left:0;min-width:100%;width:max-content;max-width:min(340px,82vw);max-height:264px;overflow-y:auto;overscroll-behavior:contain;margin:0;padding:4px;list-style:none;border:1px solid var(--sp-line);border-radius:9px;background:var(--sp-menu);color:var(--sp-text);box-shadow:var(--sp-menu-shadow);outline:none}
.sp-dd-menu[data-side=up]{top:auto;bottom:calc(100% + 4px)}
.sp-dd-opt{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:6px;cursor:pointer;color:var(--sp-text);white-space:nowrap}
.sp-dd-opt-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}
.sp-dd-opt[data-active=true]{background:color-mix(in srgb,var(--sp-text) 9%,transparent)}
.sp-dd-opt[aria-selected=true]{background:color-mix(in srgb,var(--sp-accent) 15%,transparent);font-weight:600}
.sp-dd-opt[aria-selected=true][data-active=true]{background:color-mix(in srgb,var(--sp-accent) 22%,transparent)}
.sp-dd-check{width:12px;height:12px;flex:none;color:var(--sp-accent);opacity:0}
.sp-dd-opt[aria-selected=true] .sp-dd-check{opacity:1}
.sp-dd-empty{padding:8px 9px;color:var(--sp-text-3);white-space:nowrap}
.sp-dd-sm .sp-dd-btn{height:30px;font-weight:400}
.sp-avatar{width:22px;height:22px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;flex:none;background:color-mix(in srgb,var(--sp-accent) 14%,transparent);color:var(--sp-accent)}
.sp-avatar-lg{width:36px;height:36px;border-radius:9px;font-size:14px}
.sp-journey{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--sp-line);border-radius:10px;overflow:hidden;background:var(--sp-raised)}
.sp-step{position:relative;display:flex;flex-direction:column;gap:2px;padding:12px 14px;border:0;border-right:1px solid var(--sp-line-soft);background:transparent;text-align:left;cursor:pointer;min-width:0}
.sp-step:last-child{border-right:0}
.sp-step:hover{background:var(--sp-hover)}
.sp-step[aria-pressed=true]{background:var(--sp-bg)}
.sp-step[aria-pressed=true]::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--sp-accent)}
.sp-step-k{display:flex;align-items:center;gap:6px;color:var(--sp-text-3);font-size:11.5px;font-weight:500}
.sp-step-n{font-size:20px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.3}
.sp-step-d{color:var(--sp-text-3);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sp-num{display:inline-flex;width:16px;height:16px;border-radius:5px;align-items:center;justify-content:center;font-size:10px;font-weight:600;background:var(--sp-sunk);color:var(--sp-text-2)}
.sp-step[aria-pressed=true] .sp-num{background:var(--sp-accent);color:var(--sp-accent-ink)}
.sp-toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sp-search{position:relative;flex:1;min-width:200px;max-width:340px}
.sp-search svg{position:absolute;left:9px;top:8px;width:14px;height:14px;color:var(--sp-text-3)}
.sp-input,.sp-textarea{width:100%;border:1px solid var(--sp-line);background:var(--sp-bg);color:var(--sp-text);border-radius:7px;padding:6px 9px;font:inherit;outline:none;transition:border-color .12s,box-shadow .12s}
.sp-input{height:30px}
.sp-search .sp-input{padding-left:29px}
.sp-input:focus,.sp-textarea:focus{border-color:color-mix(in srgb,var(--sp-accent) 60%,var(--sp-line));box-shadow:0 0 0 3px color-mix(in srgb,var(--sp-accent) 14%,transparent)}
.sp-input[readonly]{background:var(--sp-sunk);color:var(--sp-text-2)}
.sp-textarea{min-height:76px;resize:vertical;line-height:1.5}
.sp-seg{display:inline-flex;padding:2px;border-radius:8px;background:var(--sp-sunk);gap:2px}
.sp-seg button{border:0;background:transparent;padding:4px 10px;border-radius:6px;cursor:pointer;color:var(--sp-text-3);font-weight:500;font-size:12.5px;display:inline-flex;gap:6px;align-items:center}
.sp-seg button[aria-pressed=true]{background:var(--sp-bg);color:var(--sp-text);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.sp-seg .sp-count{color:var(--sp-text-4);font-variant-numeric:tabular-nums}
.sp-split{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;align-items:start}
.sp-split.sp-open{grid-template-columns:minmax(0,1fr) 400px}
.sp-table{border:1px solid var(--sp-line);border-radius:10px;overflow:hidden;background:var(--sp-bg)}
.sp-tr{display:grid;grid-template-columns:minmax(0,2.2fr) 128px 92px 92px minmax(0,1.5fr);gap:12px;align-items:center;padding:0 14px;min-height:50px;border-bottom:1px solid var(--sp-line-soft);cursor:pointer;width:100%;border-left:0;border-right:0;border-top:0;background:transparent;text-align:left}
.sp-tr:last-child{border-bottom:0}
.sp-tr:hover{background:var(--sp-hover)}
.sp-tr[aria-selected=true]{background:var(--sp-active)}
.sp-th{min-height:34px;cursor:default;color:var(--sp-text-3);font-size:11.5px;font-weight:500;background:var(--sp-raised)}
.sp-th:hover{background:var(--sp-raised)}
.sp-tr-imp{grid-template-columns:minmax(0,2fr) minmax(0,1.6fr) minmax(0,1fr) 96px 132px}
.sp-cell{min-width:0;display:flex;align-items:center;gap:10px}
.sp-cell-stack{display:flex;flex-direction:column;min-width:0}
.sp-strong{font-weight:550;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sp-muted{color:var(--sp-text-3)}
.sp-faint{color:var(--sp-text-4)}
.sp-small{font-size:12px}
.sp-trunc{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sp-tabnum{font-variant-numeric:tabular-nums}
.sp-pill{display:inline-flex;align-items:center;gap:6px;height:22px;padding:0 8px;border-radius:6px;font-size:11.5px;font-weight:500;white-space:nowrap;background:color-mix(in srgb,var(--tone) 11%,transparent);color:color-mix(in srgb,var(--tone) 92%,var(--sp-text))}
.sp-pill::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--tone)}
.sp-pill.sp-plain::before{display:none}
.tone-neutral{--tone:var(--sp-text-3)}.tone-blue{--tone:var(--sp-blue)}.tone-violet{--tone:var(--sp-violet)}.tone-green{--tone:var(--sp-green)}.tone-amber{--tone:var(--sp-amber)}.tone-red{--tone:var(--sp-red)}.tone-heat{--tone:var(--sp-heat)}
.sp-panel{border:1px solid var(--sp-line);border-radius:12px;background:var(--sp-bg);box-shadow:var(--sp-shadow);position:sticky;top:0;max-height:calc(100vh - 140px);display:flex;flex-direction:column;overflow:hidden}
.sp-panel-head{display:flex;gap:12px;align-items:flex-start;padding:16px 16px 14px;border-bottom:1px solid var(--sp-line-soft)}
.sp-panel-body{overflow:auto;padding:16px;display:flex;flex-direction:column;gap:18px}
.sp-panel-title{margin:0;font-size:15px;font-weight:600;letter-spacing:-.01em;line-height:1.3}
.sp-next{border-radius:10px;padding:14px;background:color-mix(in srgb,var(--sp-accent) 7%,var(--sp-bg));border:1px solid color-mix(in srgb,var(--sp-accent) 22%,var(--sp-line));display:flex;flex-direction:column;gap:10px}
.sp-next-k{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--sp-accent)}
.sp-next-t{font-weight:600;font-size:14px}
.sp-next p{margin:0;color:var(--sp-text-2)}
.sp-label{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--sp-text-3);margin:0 0 8px}
.sp-facts{display:grid;grid-template-columns:110px minmax(0,1fr);gap:7px 12px;margin:0;font-size:12.5px}
.sp-facts dt{color:var(--sp-text-3)}
.sp-facts dd{margin:0;min-width:0;overflow-wrap:anywhere}
.sp-quote{margin:0;padding:10px 12px;border-left:2px solid var(--sp-line);background:var(--sp-raised);border-radius:0 8px 8px 0;color:var(--sp-text-2);white-space:pre-wrap;overflow-wrap:anywhere}
.sp-quote-hot{border-left-color:var(--sp-heat);font-size:14px;color:var(--sp-text);background:color-mix(in srgb,var(--sp-heat) 6%,var(--sp-bg))}
.sp-draft{border:1px solid var(--sp-line);border-radius:9px;overflow:hidden}
.sp-draft-h{padding:9px 12px;border-bottom:1px solid var(--sp-line-soft);background:var(--sp-raised);font-size:12px;display:flex;flex-direction:column;gap:2px}
.sp-draft-b{padding:10px 12px;white-space:pre-wrap;max-height:200px;overflow:auto;font-size:12.5px;color:var(--sp-text-2)}
.sp-tl{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.sp-tl li{display:grid;grid-template-columns:18px minmax(0,1fr);gap:10px;position:relative;padding-bottom:14px}
.sp-tl li:not(:last-child)::before{content:"";position:absolute;left:8.5px;top:18px;bottom:0;width:1px;background:var(--sp-line-soft)}
.sp-tl-dot{width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--sp-sunk);color:var(--sp-text-3)}
.sp-tl-dot svg{width:11px;height:11px}
.sp-tl-in .sp-tl-dot{background:color-mix(in srgb,var(--sp-green) 16%,transparent);color:var(--sp-green)}
.sp-tl-out .sp-tl-dot{background:color-mix(in srgb,var(--sp-violet) 16%,transparent);color:var(--sp-violet)}
.sp-empty{display:flex;flex-direction:column;align-items:center;text-align:center;gap:10px;padding:48px 24px;border:1px dashed var(--sp-line);border-radius:12px;background:var(--sp-raised)}
.sp-empty h2{margin:0;font-size:15px;font-weight:600}
.sp-empty p{margin:0;color:var(--sp-text-3);max-width:440px}
.sp-empty-icon{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:var(--sp-bg);border:1px solid var(--sp-line);color:var(--sp-text-2)}
.sp-empty-icon svg{width:18px;height:18px}
.sp-start{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;width:100%;max-width:620px;margin-top:8px}
.sp-start button{display:flex;flex-direction:column;align-items:flex-start;gap:6px;text-align:left;padding:14px;border:1px solid var(--sp-line);border-radius:10px;background:var(--sp-bg);cursor:pointer}
.sp-start button:hover{border-color:color-mix(in srgb,var(--sp-accent) 45%,var(--sp-line))}
.sp-start strong{font-weight:600}
.sp-start span{color:var(--sp-text-3);font-size:12.5px}
.sp-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.sp-stat{border:1px solid var(--sp-line);border-radius:10px;padding:12px 14px;background:var(--sp-raised)}
.sp-stat-n{font-size:22px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.sp-stat-k{color:var(--sp-text-3);font-size:12px}
.sp-hot{display:grid;grid-template-columns:minmax(0,1fr) 280px;border:1px solid var(--sp-line);border-radius:12px;overflow:hidden;background:var(--sp-bg)}
.sp-hot-main{padding:18px;display:flex;flex-direction:column;gap:12px;min-width:0}
.sp-hot-side{padding:18px;border-left:1px solid var(--sp-line-soft);background:var(--sp-raised);display:flex;flex-direction:column;gap:10px}
.sp-heat{display:inline-flex;gap:2px;align-items:flex-end;height:14px}
.sp-heat i{width:4px;border-radius:1px;background:var(--sp-line)}
.sp-heat i.on{background:var(--sp-heat)}
.sp-ev{display:flex;flex-direction:column;gap:6px;margin:0;padding:0;list-style:none}
.sp-ev li{display:flex;gap:8px;font-size:12px;color:var(--sp-text-2);min-width:0}
.sp-ev li>span{flex:none;white-space:nowrap}
.sp-ev li>span.sp-ev-x{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}
.sp-settings{display:grid;grid-template-columns:180px minmax(0,1fr);gap:32px;align-items:start}
.sp-snav{position:sticky;top:0;display:flex;flex-direction:column;gap:1px}
.sp-snav button{border:0;background:transparent;text-align:left;padding:6px 10px;border-radius:7px;cursor:pointer;color:var(--sp-text-3);font-weight:500;display:flex;align-items:center;justify-content:space-between;gap:8px}
.sp-snav button:hover{background:var(--sp-hover);color:var(--sp-text)}
.sp-sections{display:flex;flex-direction:column;gap:16px;min-width:0}
.sp-card{border:1px solid var(--sp-line);border-radius:12px;background:var(--sp-bg);overflow:hidden;scroll-margin-top:12px}
.sp-card-h{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px 18px 0}
.sp-card-h h2{margin:0;font-size:14px;font-weight:600}
.sp-card-h p{margin:3px 0 0;color:var(--sp-text-3);font-size:12.5px}
.sp-card-b{padding:16px 18px;display:flex;flex-direction:column;gap:14px}
.sp-card-f{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 18px;border-top:1px solid var(--sp-line-soft);background:var(--sp-raised);flex-wrap:wrap}
.sp-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.sp-grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.sp-field{display:flex;flex-direction:column;gap:5px;min-width:0}
.sp-field>span{font-size:12px;font-weight:500;color:var(--sp-text-2)}
.sp-field small{color:var(--sp-text-3);font-size:11.5px}
.sp-field .sp-seg{align-self:flex-start;height:30px;align-items:center}
.sp-chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;min-height:34px;padding:4px 6px;border:1px solid var(--sp-line);border-radius:7px;background:var(--sp-bg)}
.sp-chips:focus-within{border-color:color-mix(in srgb,var(--sp-accent) 60%,var(--sp-line));box-shadow:0 0 0 3px color-mix(in srgb,var(--sp-accent) 14%,transparent)}
.sp-chip{display:inline-flex;align-items:center;gap:4px;height:24px;padding:0 4px 0 8px;border-radius:6px;background:var(--sp-sunk);font-size:12px}
.sp-chip button{border:0;background:transparent;cursor:pointer;color:var(--sp-text-3);padding:0 2px;display:flex}
.sp-chip svg{width:12px;height:12px}
.sp-chips input{flex:1;min-width:120px;border:0;outline:none;background:transparent;font:inherit;color:var(--sp-text);height:24px}
.sp-brands{display:flex;flex-direction:column;border:1px solid var(--sp-line);border-radius:9px;overflow:hidden}
.sp-brand-row{display:flex;align-items:center;gap:10px;padding:10px 12px;border:0;border-bottom:1px solid var(--sp-line-soft);background:transparent;cursor:pointer;text-align:left}
.sp-brand-row:last-child{border-bottom:0}
.sp-brand-row:hover{background:var(--sp-hover)}
.sp-brand-row[aria-checked=true]{background:var(--sp-active)}
.sp-radio{width:14px;height:14px;border-radius:50%;border:1.5px solid var(--sp-line);flex:none}
.sp-brand-row[aria-checked=true] .sp-radio{border:4px solid var(--sp-accent)}
.sp-check{display:flex;gap:8px;align-items:flex-start;cursor:pointer}
.sp-check input{margin-top:3px;accent-color:var(--sp-accent)}
.sp-callout{display:flex;gap:10px;padding:10px 12px;border-radius:8px;background:var(--sp-raised);border:1px solid var(--sp-line-soft);color:var(--sp-text-2);font-size:12.5px}
.sp-callout svg{width:15px;height:15px;flex:none;margin-top:1px;color:var(--sp-text-3)}
.sp-callout-warn{background:color-mix(in srgb,var(--sp-amber) 8%,var(--sp-bg));border-color:color-mix(in srgb,var(--sp-amber) 25%,var(--sp-line))}
.sp-callout-warn svg{color:var(--sp-amber)}
.sp-overlay{position:fixed;inset:0;z-index:50;background:color-mix(in srgb,#000 32%,transparent);display:flex;align-items:flex-start;justify-content:center;padding:8vh 16px 16px;overflow:auto}
.sp-dialog{width:100%;max-width:620px;border-radius:14px;background:var(--sp-bg);border:1px solid var(--sp-line);box-shadow:0 24px 64px -16px rgba(0,0,0,.45);display:flex;flex-direction:column;overflow:visible}
.sp-dialog-h{border-radius:14px 14px 0 0}
.sp-dialog-f{border-radius:0 0 14px 14px}
.sp-dialog-h{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--sp-line-soft)}
.sp-dialog-h h2{margin:0;font-size:15px;font-weight:600}
.sp-dialog-b{padding:18px;display:flex;flex-direction:column;gap:16px}
.sp-dialog-f{display:flex;justify-content:flex-end;gap:8px;padding:12px 18px;border-top:1px solid var(--sp-line-soft);background:var(--sp-raised)}
.sp-drop{display:flex;flex-direction:column;align-items:center;gap:6px;padding:22px;border:1px dashed var(--sp-line);border-radius:10px;background:var(--sp-raised);text-align:center;cursor:pointer;position:relative}
.sp-drop:hover{border-color:color-mix(in srgb,var(--sp-accent) 50%,var(--sp-line))}
.sp-drop input{position:absolute;inset:0;opacity:0;cursor:pointer}
.sp-map{display:grid;grid-template-columns:minmax(0,1fr) 18px minmax(0,1fr);gap:8px 10px;align-items:center}
.sp-map svg{width:14px;height:14px;color:var(--sp-text-4)}
.sp-toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:60;display:flex;align-items:center;gap:10px;max-width:min(560px,calc(100vw - 32px));padding:10px 14px;border-radius:10px;background:color-mix(in srgb,var(--sp-text) 92%,var(--sp-bg));color:var(--sp-bg);box-shadow:0 12px 32px -10px rgba(0,0,0,.4);font-size:12.5px;animation:sp-in .18s ease-out}
.sp-toast.err{background:var(--sp-red);color:#fff}
.sp-toast svg{width:15px;height:15px;flex:none}
.sp-skel{border-radius:10px;background:linear-gradient(90deg,var(--sp-sunk),var(--sp-raised),var(--sp-sunk));background-size:200% 100%;animation:sp-sh 1.4s linear infinite}
.sp-banner{display:flex;align-items:center;gap:10px;padding:8px 20px;font-size:12.5px;background:color-mix(in srgb,var(--sp-amber) 10%,var(--sp-bg));border-bottom:1px solid var(--sp-line-soft);color:var(--sp-text-2)}
.sp-dot{width:7px;height:7px;border-radius:50%;background:var(--tone);display:inline-block;flex:none}
.sp-kbd{font:11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;padding:2px 5px;border-radius:4px;background:var(--sp-sunk);color:var(--sp-text-2)}
.sp-mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.sp-divider{height:1px;background:var(--sp-line-soft);margin:2px 0}
.sp-caps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;border:1px solid var(--sp-line-soft);border-radius:9px}
.sp-caps li{display:grid;grid-template-columns:minmax(0,200px) 84px minmax(0,1fr);gap:12px;align-items:center;padding:9px 12px;border-bottom:1px solid var(--sp-line-soft)}
.sp-caps li:last-child{border-bottom:0}
.sp-caps .sp-pill{justify-self:start}
@media (max-width:640px){.sp-caps li{grid-template-columns:minmax(0,1fr) auto}.sp-caps li>:last-child{grid-column:1/-1}}
.sp-getting{border:1px solid color-mix(in srgb,var(--sp-accent) 25%,var(--sp-line));border-radius:12px;background:color-mix(in srgb,var(--sp-accent) 4%,var(--sp-bg));padding:14px 16px;display:flex;flex-direction:column;gap:10px}
.sp-getting-h{display:flex;align-items:center;gap:10px}
.sp-progress{flex:1;max-width:160px;height:4px;border-radius:2px;background:var(--sp-sunk);overflow:hidden}.sp-progress i{display:block;height:100%;background:var(--sp-accent)}
.sp-getting-l{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 20px}
.sp-getting-l li{display:flex;align-items:center;gap:10px;min-height:34px}
.sp-getting-n{width:20px;height:20px;border-radius:50%;flex:none;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;border:1px solid var(--sp-line);color:var(--sp-text-3);background:var(--sp-bg)}
.sp-getting-n svg{width:11px;height:11px}
.sp-getting-l li.done .sp-getting-n{background:var(--sp-accent);border-color:var(--sp-accent);color:var(--sp-accent-ink)}
.sp-getting-l li.done .sp-getting-t{color:var(--sp-text-3);text-decoration:line-through;text-decoration-color:var(--sp-line)}
.sp-getting-t{flex:1;min-width:0}
.sp-today{border:1px solid var(--sp-line);border-radius:12px;background:var(--sp-bg);padding:14px 16px;display:flex;flex-direction:column;gap:12px}
.sp-today-h{display:flex;align-items:baseline;gap:10px}
.sp-today-g{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}
.sp-today-col{display:flex;flex-direction:column;gap:4px;align-items:flex-start;min-width:0}
.sp-today-item{display:flex;align-items:center;gap:10px;width:calc(100% + 8px);padding:7px 8px;margin-left:-8px;border:0;border-radius:8px;background:transparent;text-align:left;cursor:pointer;min-width:0}
.sp-today-item:hover{background:var(--sp-hover)}
.sp-today-item .sp-cell-stack{flex:1}
.sp-app svg.sp-today-go{width:14px;height:14px;color:var(--sp-text-4);flex:none}
.sp-senders{display:flex;flex-direction:column;border:1px solid var(--sp-line-soft);border-radius:8px}
.sp-senders>div{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--sp-line-soft);font-size:12.5px}.sp-senders>div:last-child{border-bottom:0}
@media (max-width:640px){.sp-getting-l{grid-template-columns:minmax(0,1fr)}.sp-getting-l li{flex-wrap:wrap}}
.sp-app svg.sp-inline{width:12px;height:12px;vertical-align:-2px}
.sp-start svg{width:18px;height:18px;color:var(--sp-accent)}
.sp-banner svg{width:15px;height:15px;flex:none;color:var(--sp-amber)}
.sp-next .sp-quote{margin:0}
@keyframes sp-in{from{opacity:0;transform:translate(-50%,6px)}to{opacity:1;transform:translate(-50%,0)}}
@keyframes sp-sh{to{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){.sp-app *{animation:none!important;transition:none!important}}
@media (max-width:1080px){.sp-split.sp-open{grid-template-columns:minmax(0,1fr)}.sp-panel{position:fixed;right:12px;top:64px;bottom:12px;width:min(420px,calc(100vw - 24px));max-height:none;z-index:40}}
@media (max-width:860px){.sp-journey{grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:var(--sp-line-soft)}.sp-step{border-right:0;background:var(--sp-raised)}.sp-step[aria-pressed=true]{background:var(--sp-bg)}.sp-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.sp-hot{grid-template-columns:minmax(0,1fr)}.sp-hot-side{border-left:0;border-top:1px solid var(--sp-line-soft)}.sp-settings{grid-template-columns:minmax(0,1fr)}.sp-snav{display:none}.sp-tr{grid-template-columns:minmax(0,1fr) 124px}.sp-tr>:nth-child(n+3){display:none}.sp-tr-imp{grid-template-columns:minmax(0,1fr) 132px}}
@media (max-width:640px){.sp-top{padding:8px 12px 0;gap:8px;height:auto;flex-wrap:wrap}.sp-tabs{order:3;width:100%;margin:0 -4px;overflow-x:auto;padding-bottom:6px}.sp-tab{flex:none}.sp-logo span,.sp-sep,.sp-ask-label{display:none}.sp-page{padding:16px 16px 40px}.sp-grid2,.sp-grid3,.sp-start{grid-template-columns:minmax(0,1fr)}.sp-journey{grid-template-columns:repeat(2,minmax(0,1fr))}}
`

// ---------------------------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------------------------

function h(type, props, ...kids) {
  const { key, ...rest } = props || {}
  const children = kids.length === 0 ? undefined : kids.length === 1 ? kids[0] : kids
  const finalProps = children === undefined ? rest : { ...rest, children }
  return Array.isArray(children) ? jsxs(type, finalProps, key) : jsx(type, finalProps, key)
}

const ICONS = {
  search: 'M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm10 2-4.35-4.35',
  upload: 'M12 15V3m0 0 4 4m-4-4L8 7M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4',
  compass: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm3.5-12.5-2 5-5 2 2-5 5-2Z',
  chat: 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z',
  send: 'M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z',
  mail: 'M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm-1 1 9 7 9-7',
  reply: 'M9 14 4 9l5-5M4 9h10a6 6 0 0 1 6 6v5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v5l3 2',
  check: 'M20 6 9 17l-5-5',
  x: 'M18 6 6 18M6 6l12 12',
  chevron: 'M6 9l6 6 6-6',
  right: 'M5 12h14m-6-6 6 6-6 6',
  copy: 'M9 9h10v12H9zM5 15V3h12',
  flame: 'M12 22c4 0 7-2.7 7-7 0-4-3-6.5-4-10-2 2-3 4-3 6-1-1-2-2-2.5-4C7 10 5 12 5 15c0 4.3 3 7 7 7Z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm13 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
  settings: 'M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-5v-4m0-4h.01',
  alert: 'M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  refresh: 'M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6',
  note: 'M4 4h16v12l-4 4H4zM16 20v-4h4',
  plus: 'M12 5v14M5 12h14',
  link: 'M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1m2 5a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1'
}

function Icon({ name, className }) {
  return h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '1.7', strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true', className },
    h('path', { d: ICONS[name] || ICONS.info }))
}
const icon = (name, className) => h(Icon, { name, className })

// The SalesPilot mark is a heading dial: an open instrument ring, a needle set to north-east and an
// ember tip. It reads as a compass (the pilot) and a gauge (the pipeline), and the ember is the same
// heat tone Hot Prospects use. Drawn on a 24 grid with 2px strokes so it holds at 16px.
function Mark({ tile }) {
  const ring = h('path', { key: 'r', d: 'M7.9 19.1A8.2 8.2 0 1 1 16.1 19.1', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round' })
  const needle = h('path', { key: 'n', d: 'M12 12.6 15.6 9', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round' })
  const hub = h('circle', { key: 'h', cx: '12', cy: '12.6', r: '1.9', fill: 'currentColor' })
  const tip = h('circle', { key: 't', cx: '16.4', cy: '8.2', r: '1.9', fill: 'var(--sp-heat)' })
  if (tile) {
    return h('span', { className: 'sp-mark-tile', 'aria-hidden': 'true' },
      h('svg', { viewBox: '0 0 24 24', fill: 'none' }, ring, needle, hub, tip))
  }
  return h('svg', { className: 'sp-mark', viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': 'true' }, ring, needle, hub, tip)
}

const initials = name => String(name || '?').replace(/^(pt\.?|cv\.?|ud\.?)\s+/i, '').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?'

function parseDate(value) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

function ago(value) {
  const d = parseDate(value)
  if (!d) return ''
  const s = (Date.now() - d.getTime()) / 1000
  if (s < 0) return inDays(value)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`
  return shortDate(value)
}

function inDays(value) {
  const d = parseDate(value)
  if (!d) return ''
  const days = Math.round((d.getTime() - Date.now()) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'tomorrow'
  if (days < 7) return `in ${days} days`
  return shortDate(value)
}

function shortDate(value) {
  const d = parseDate(value)
  if (!d) return ''
  const opts = { month: 'short', day: 'numeric' }
  if (d.getFullYear() !== new Date().getFullYear()) opts.year = 'numeric'
  return d.toLocaleDateString(undefined, opts)
}

// Backend codes are for logs; people get a sentence that says what to do next.
const FRIENDLY = {
  imap_not_configured: 'Reply tracking is off. Add your inbox in Settings → Reply tracking.',
  not_qualified: 'Qualify this customer before preparing an email.',
  missing_email: 'There is no email address for this customer yet.',
  outreach_blocked: 'This customer asked not to be contacted. SalesPilot will not email them.',
  lead_not_found: 'This customer belongs to another brand. Switch brand and try again.',
  search_unavailable: 'Web search is not available here. Use “Find leads with Hermes” in chat instead.',
  missing_credentials: 'Add your mailbox username and password in Hermes plugin settings first.',
  not_authorized: 'Confirm you have permission to contact this list.',
  missing_authorization_note: 'Say where this list comes from.',
  file_too_large: 'That file is over 2 MB. Split it and import the parts.',
  schema_pending: 'SalesPilot is updating its storage. Try again in a moment.'
}
const errText = (body, fallback) => {
  if (!body) return fallback
  if (body.code && FRIENDLY[body.code]) return FRIENDLY[body.code]
  if (body.error) return body.error
  return body.code ? String(body.code).replace(/_/g, ' ') : fallback
}

// ---------------------------------------------------------------------------------------------
// Pipeline vocabulary: one place maps backend statuses to the journey the user sees.
// ---------------------------------------------------------------------------------------------

const STATUS = {
  discovered: ['New', 'neutral'],
  qualified: ['Qualified', 'blue'],
  draft_ready: ['Needs approval', 'blue'],
  contacted: ['Sent', 'violet'],
  replied: ['Replied', 'green'],
  follow_up_due: ['Follow-up due', 'amber'],
  followed_up: ['Followed up', 'violet'],
  not_interested: ['Not interested', 'red'],
  do_not_contact: ['Do not contact', 'red'],
  archived: ['Archived', 'neutral']
}

// The six steps a customer moves through. Approval is its own step on purpose: nothing leaves until a
// person confirms it in Hermes chat.
const JOURNEY = [
  { id: 'collect', label: 'Collect', hint: 'Check the fit' },
  { id: 'prepare', label: 'Prepare', hint: 'Write the first email' },
  { id: 'approve', label: 'Approve', hint: 'Your sign-off' },
  { id: 'sent', label: 'Sent', hint: 'Waiting for a reply' },
  { id: 'replied', label: 'Replied', hint: 'Answer personally' },
  { id: 'followup', label: 'Follow up', hint: 'Due or done' }
]

function stageOf(p) {
  const status = p.status || 'discovered'
  const follow = (p.followup && p.followup.state) || ''
  if (p.archived || ['not_interested', 'do_not_contact', 'archived'].includes(status)) return 'closed'
  // Cold or exhausted prospects stay saved but leave the daily work list.
  if (['cold', 'exhausted', 'stopped'].includes(follow)) return 'closed'
  if (status === 'replied' || follow === 'replied') return 'replied'
  if (status === 'follow_up_due' || status === 'followed_up' || follow === 'followup_due') return 'followup'
  if (status === 'contacted') return 'sent'
  if (status === 'draft_ready') return 'approve'
  if (status === 'qualified') return 'prepare'
  return 'collect'
}

function StatusPill({ status }) {
  const [label, tone] = STATUS[status] || [status || 'Unknown', 'neutral']
  return h('span', { className: `sp-pill tone-${tone}` }, label)
}

function followLine(p) {
  const f = p.followup || {}
  if (f.state === 'followup_due') return { text: 'Follow-up due now', tone: 'amber' }
  if (f.state === 'awaiting_reply') return { text: `Follow up ${inDays(f.next_due)}`, tone: 'neutral' }
  if (f.state === 'replied') return { text: `Replied ${ago(p.last_reply_at)}`.trim(), tone: 'green' }
  if (f.state === 'cold') return { text: 'Gone cold', tone: 'neutral' }
  if (f.state === 'exhausted') return { text: `Stopped after ${f.attempts} attempts`, tone: 'neutral' }
  if (f.state === 'stopped') return { text: 'Outreach stopped', tone: 'red' }
  if (p.status === 'draft_ready') return { text: 'Draft waiting for you', tone: 'blue' }
  if (p.status === 'qualified') return { text: 'Prepare the first email', tone: 'neutral' }
  return { text: 'Check the fit', tone: 'neutral' }
}

// Who will read the email, in words a salesperson uses.
const READINESS = {
  decision_maker: 'Decision-maker',
  business_contact: 'Named business contact',
  role_generic: 'Shared inbox (info@, sales@)',
  person_unknown_role: 'A person, role unknown',
  missing: 'No contact yet'
}

// ---------------------------------------------------------------------------------------------
// Host bridges: REST to the plugin backend, and the chat composer for chat-first actions.
// ---------------------------------------------------------------------------------------------

let rest = null
let osApi = null

function askHermes(text, notify) {
  const say = notify || (() => {})
  const copy = () => {
    const writer = osApi && typeof osApi.writeClipboard === 'function'
      ? osApi.writeClipboard(text)
      : (typeof navigator !== 'undefined' && navigator.clipboard ? navigator.clipboard.writeText(text).then(() => true) : Promise.resolve(false))
    Promise.resolve(writer).then(ok => say(ok ? 'Copied. Paste it into a Hermes chat and press Enter.' : `Paste into a Hermes chat: ${text}`)).catch(() => say(`Paste into a Hermes chat: ${text}`))
  }
  const composer = host && host.composer
  if (composer && typeof composer.insertText === 'function') {
    Promise.resolve(composer.insertText(null, text, { mode: 'replace' }))
      .then(ok => {
        if (!ok) return copy()
        if (typeof composer.focus === 'function') composer.focus(null)
        say('Added to your Hermes chat. Review it, then press Enter.')
      })
      .catch(copy)
    return
  }
  copy()
}

const PROMPTS = {
  findLeads: brand => `Use SalesPilot to find new prospects for ${brand} that match our ideal customer profile. Save only companies with quoted public evidence and a public contact. Do not send anything.`,
  research: (p, brand) => `Use SalesPilot to research ${p.company} (lead ${p.id}) for ${brand}: confirm quoted public evidence and find the right decision-maker contact, then qualify it. Do not send anything.`,
  researchImported: (c, brand) => `Use SalesPilot to research the imported customer ${c.company}${c.email ? ` (${c.email})` : ''} for ${brand}. Find quoted public evidence, add it to the pipeline and qualify it. Do not send anything.`,
  followup: p => `Use SalesPilot to write a short follow-up email draft for ${p.company} (lead ${p.id}) based on our last message. Show me the draft first and do not send it.`,
  reply: p => `Read the latest reply from ${p.company} (lead ${p.id}) in SalesPilot and draft a response for my review. Do not send it.`,
  send: draftId => `/salespilot-send ${draftId}`
}

// ---------------------------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------------------------

const TABS = [
  ['customers', 'Customers'],
  ['hot', 'Hot Prospects'],
  ['settings', 'Settings']
]

const TAB_PATHS = {
  customers: ['/pipeline?limit=500', '/outreach', '/customers', '/setup'],
  hot: ['/hot', '/pipeline?limit=500'],
  settings: ['/setup']
}

const keyOf = path => path.slice(1).split('?')[0]

function Page() {
  const gateway = useValue(host.state.gateway)
  const [tab, setTab] = useState('customers')
  const [data, setData] = useState({})
  const [brands, setBrands] = useState({ ok: true, brands: [], active: null })
  const [version, setVersion] = useState(0)
  const [toast, setToast] = useState(null)
  const [focusLead, setFocusLead] = useState('')
  const [hotCount, setHotCount] = useState(0)
  const [anchor, setAnchor] = useState('')

  const notify = (message, kind) => setToast({ message, kind: kind || 'ok', at: Date.now() })
  const refresh = () => setVersion(v => v + 1)

  useEffect(() => {
    if (!toast || typeof window === 'undefined') return undefined
    const timer = window.setTimeout(() => setToast(null), toast.kind === 'err' ? 6500 : 4200)
    return () => window.clearTimeout && window.clearTimeout(timer)
  }, [toast && toast.at])

  useEffect(() => {
    let stop = false
    const paths = TAB_PATHS[tab] || []
    const load = () => {
      if (!rest) {
        setData(current => ({ ...current, [tab]: { error: 'The SalesPilot backend route is not bound.' } }))
        return Promise.resolve()
      }
      return Promise.all(paths.map(path => rest(path).catch(err => ({ ok: false, error: err && err.message ? err.message : 'The API did not answer.' }))))
        .then(bodies => {
          if (stop) return
          const merged = {}
          paths.forEach((path, index) => { merged[keyOf(path)] = bodies[index] || { ok: false } })
          setData(current => ({ ...current, [tab]: merged }))
          if (merged.hot && Array.isArray(merged.hot.prospects)) setHotCount(merged.hot.prospects.length)
        })
    }
    load()
    if (rest) rest('/brands').then(body => { if (!stop && body) setBrands(body) }).catch(() => undefined)
    if (rest && tab !== 'hot') rest('/hot').then(body => { if (!stop && body && Array.isArray(body.prospects)) setHotCount(body.prospects.length) }).catch(() => undefined)
    // Refresh only while the window is visible and never two at once: a hidden window must not
    // keep re-rendering a pane (that is what kept re-fronting it). Settings never polls, so a
    // half-typed form is not overwritten.
    let inFlight = false
    const poll = () => {
      if (stop || inFlight || tab === 'settings') return
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      inFlight = true
      Promise.resolve(load()).finally(() => { inFlight = false })
    }
    const timer = setInterval(poll, 10000)
    return () => { stop = true; clearInterval(timer) }
  }, [tab, version])

  const switchBrand = (brand) => {
    if (!rest || !brand) return
    rest('/brands', { method: 'POST', body: { brand } })
      .then(body => {
        if (body && body.ok === false) return notify(errText(body, 'The brand did not switch.'), 'err')
        setBrands(body || brands)
        setData({})
        setFocusLead('')
        refresh()
        const name = body && body.active ? body.active.display_name : 'brand'
        notify(`Switched to ${name}.`)
      })
      .catch(err => notify(err && err.message ? err.message : 'The brand did not switch.', 'err'))
  }

  const openCustomer = (leadId) => { setFocusLead(leadId); setTab('customers') }
  const offline = gateway && gateway !== 'open' && gateway !== 'connected'
  const current = data[tab]
  const brandName = (brands.active && brands.active.display_name) || 'your brand'
  // setSection('settings', 'sp-set-email') opens a tab and lands on one card, so "Connect your email"
  // goes to the email form instead of the top of Settings.
  const setSection = (next, target) => { setAnchor(target || ''); setTab(next) }
  const shared = { data: current, notify, refresh, brands, brandName, switchBrand, setSection, openCustomer, focusLead, setFocusLead, version, anchor }

  return h('div', { className: 'sp-app' },
    h('style', { key: 'css' }, CSS),
    h('header', { key: 'top', className: 'sp-top' },
      h('div', { className: 'sp-logo' }, h(Mark, { tile: true }), h('span', null, 'SalesPilot')),
      h('div', { className: 'sp-sep', 'aria-hidden': 'true' }),
      h(BrandSwitch, { brands, onSwitch: switchBrand }),
      h('nav', { className: 'sp-tabs', role: 'tablist', 'aria-label': 'SalesPilot sections' },
        TABS.map(([id, label]) => h('button', {
          key: id, type: 'button', role: 'tab', className: 'sp-tab', 'aria-selected': tab === id, onClick: () => setSection(id)
        }, label, id === 'hot' && hotCount ? h('span', { className: 'sp-badge' }, String(hotCount)) : null))),
      h('div', { className: 'sp-spacer' }),
      h('button', { type: 'button', className: 'sp-btn sp-btn-ghost', title: 'Hand a sales task to Hermes in chat', onClick: () => askHermes(`Use SalesPilot for ${brandName}: `, notify) },
        icon('chat'), h('span', { className: 'sp-ask-label' }, 'Ask Hermes'))),
    offline ? h('div', { key: 'off', className: 'sp-banner', role: 'status' }, icon('alert'), 'Hermes is offline. Your records are safe and reload when the gateway returns.') : null,
    h('div', { key: 'body', className: 'sp-body' },
      !current ? h(Loading, {}) :
        current.error ? h(Problem, { text: current.error }) :
          tab === 'customers' ? h(CustomersView, shared) :
            tab === 'hot' ? h(HotView, shared) :
              h(SettingsView, shared)),
    toast ? h('div', { key: 'toast', className: `sp-toast ${toast.kind === 'err' ? 'err' : ''}`, role: toast.kind === 'err' ? 'alert' : 'status' },
      icon(toast.kind === 'err' ? 'alert' : 'check'), h('span', null, toast.message)) : null)
}

// One listbox for every dropdown in the plugin. A native <select> popup is drawn by the OS and ignores
// the host theme — on Windows dark mode it opens as a white sheet, which is what made the brand picker
// unreadable. This owns its surface instead, and stays accessible: combobox button + listbox, full
// keyboard support, stable ids instead of refs so the outside-click listener can find the node.
let ddSeq = 0

const ddLabel = option => (option && (option.label || option.value)) || ''

function Select({ value, options, onChange, ariaLabel, className, placeholder, disabled }) {
  const list = Array.isArray(options) ? options : []
  const [id] = useState(() => `sp-dd-${++ddSeq}`)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [side, setSide] = useState('down')
  const selectedIndex = list.findIndex(option => option.value === value)
  const current = selectedIndex >= 0 ? list[selectedIndex] : null

  const close = () => { setOpen(false); setActive(-1) }
  const focusButton = () => {
    if (typeof document === 'undefined' || !document.getElementById) return
    const button = document.getElementById(`${id}-btn`)
    if (button && button.focus) button.focus()
  }
  const openAt = index => {
    if (!list.length) return
    const fallback = selectedIndex >= 0 ? selectedIndex : 0
    setActive(index >= 0 && index < list.length ? index : fallback)
    setOpen(true)
    if (typeof document !== 'undefined' && document.getElementById) {
      const button = document.getElementById(`${id}-btn`)
      const rect = button && button.getBoundingClientRect ? button.getBoundingClientRect() : null
      const height = typeof window !== 'undefined' && window.innerHeight ? window.innerHeight : 0
      // Open upwards near the bottom of the window so the list is never cut off.
      setSide(rect && height && rect.bottom + 280 > height ? 'up' : 'down')
    }
  }
  const pick = index => {
    const option = list[index]
    close()
    if (option && option.value !== value) onChange(option.value)
    focusButton()
  }

  useEffect(() => {
    if (!open) return undefined
    if (typeof document === 'undefined' || !document.addEventListener) return undefined
    const onDown = event => {
      const root = document.getElementById(`${id}-root`)
      if (root && event.target && root.contains && root.contains(event.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDown, true)
    const menu = document.getElementById(`${id}-menu`)
    if (menu && menu.focus) menu.focus()
    return () => document.removeEventListener('mousedown', onDown, true)
  }, [open, id])

  const onButtonKey = event => {
    const key = event.key
    if (key === 'ArrowDown' || key === 'ArrowUp') {
      event.preventDefault()
      // Closed: open on the selected row so the reader starts where the form is. Open: step from it.
      const step = key === 'ArrowDown' ? 1 : -1
      openAt(open ? active + step : selectedIndex)
      return
    }
    if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
      event.preventDefault()
      if (open && active >= 0) pick(active)
      else openAt(-1)
      return
    }
    if (key === 'Escape' && open) {
      event.preventDefault()
      close()
    }
  }

  const onMenuKey = event => {
    const key = event.key
    if (key === 'ArrowDown' || key === 'ArrowUp') {
      event.preventDefault()
      const step = key === 'ArrowDown' ? 1 : -1
      setActive(previous => {
        const from = previous < 0 ? (step > 0 ? -1 : list.length) : previous
        return Math.min(list.length - 1, Math.max(0, from + step))
      })
      return
    }
    if (key === 'Home') { event.preventDefault(); setActive(0); return }
    if (key === 'End') { event.preventDefault(); setActive(list.length - 1); return }
    if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
      event.preventDefault()
      if (active >= 0) pick(active)
      return
    }
    if (key === 'Escape') { event.preventDefault(); close(); focusButton(); return }
    if (key === 'Tab') close()
  }

  return h('div', { className: `sp-dd ${className || ''}`.trim(), id: `${id}-root`, 'data-open': open ? 'true' : 'false' },
    h('button', {
      id: `${id}-btn`, type: 'button', className: 'sp-dd-btn', role: 'combobox',
      'aria-haspopup': 'listbox', 'aria-expanded': open ? 'true' : 'false', 'aria-controls': `${id}-menu`,
      'aria-label': ariaLabel, disabled: !!disabled, title: current ? ddLabel(current) : (placeholder || ''),
      onClick: () => (open ? close() : openAt(-1)), onKeyDown: onButtonKey
    },
    h('span', { className: 'sp-dd-label' }, current ? ddLabel(current) : (placeholder || 'Select')),
    icon('chevron', 'sp-caret')),
    open ? h('ul', {
      id: `${id}-menu`, className: 'sp-dd-menu', role: 'listbox', tabIndex: -1,
      'aria-label': ariaLabel, 'data-side': side, onKeyDown: onMenuKey
    },
    list.length ? list.map((option, index) => h('li', {
      key: `${option.value}`, id: `${id}-opt-${index}`, role: 'option', className: 'sp-dd-opt',
      'aria-selected': option.value === value ? 'true' : 'false', 'data-active': index === active ? 'true' : 'false',
      title: ddLabel(option),
      onMouseEnter: () => setActive(index),
      onMouseDown: event => { if (event && event.preventDefault) event.preventDefault() },
      onClick: () => pick(index)
    },
    h('span', { className: 'sp-dd-opt-label' }, ddLabel(option)),
    icon('check', 'sp-dd-check')))
      : h('li', { className: 'sp-dd-empty' }, 'Nothing to choose from')) : null)
}

function BrandSwitch({ brands, onSwitch }) {
  const list = (brands && brands.brands) || []
  const active = (brands && brands.active) || list[0]
  if (!list.length) return h('span', { className: 'sp-muted sp-small' }, 'No brand yet')
  return h('div', { className: 'sp-brand-pick' },
    h('span', { className: 'sp-avatar' }, initials(active ? active.display_name : list[0].display_name)),
    h(Select, {
      value: active ? active.id : '',
      ariaLabel: 'Active brand',
      placeholder: 'Choose a brand',
      className: 'sp-brand-dd',
      options: list.map(item => ({ value: item.id, label: item.display_name || item.name || item.id })),
      onChange: onSwitch
    }))
}

function Loading() {
  return h('div', { className: 'sp-page', 'aria-busy': 'true' },
    h('div', { key: 'a', className: 'sp-skel', style: { height: 28, width: 220 } }),
    h('div', { key: 'b', className: 'sp-skel', style: { height: 74 } }),
    h('div', { key: 'c', className: 'sp-skel', style: { height: 320 } }))
}

function Problem({ text }) {
  return h('div', { className: 'sp-page' }, h(Empty, { iconName: 'alert', title: 'SalesPilot could not load', body: text }))
}

function Empty({ iconName, title, body, children }) {
  return h('section', { className: 'sp-empty' },
    h('div', { className: 'sp-empty-icon' }, icon(iconName || 'info')),
    h('h2', null, title),
    body ? h('p', null, body) : null,
    children || null)
}

// ---------------------------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------------------------

function CustomersView({ data, notify, refresh, brandName, setSection, focusLead, setFocusLead, version }) {
  const pipe = (data && data.pipeline) || {}
  const outreach = (data && data.outreach) || {}
  const imported = (data && data.customers) || {}
  const [view, setView] = useState('pipeline')
  const [stage, setStage] = useState('')
  const [query, setQuery] = useState('')
  const [importing, setImporting] = useState(false)
  const [busy, setBusy] = useState('')

  const prospects = Array.isArray(pipe.prospects) ? pipe.prospects : []
  const drafts = Array.isArray(outreach.drafts) ? outreach.drafts : []
  const importedRows = Array.isArray(imported.customers) ? imported.customers : []
  const counts = {}
  prospects.forEach(p => { const s = stageOf(p); counts[s] = (counts[s] || 0) + 1 })
  const due = prospects.filter(p => p.followup && p.followup.state === 'followup_due').length
  const q = query.trim().toLowerCase()
  const rows = prospects.filter(p => {
    if (stage && stageOf(p) !== stage) return false
    if (!stage && stageOf(p) === 'closed') return false
    if (!q) return true
    return `${p.company} ${p.email} ${p.contact_name} ${p.evidence} ${p.note}`.toLowerCase().includes(q)
  })
  const selected = prospects.find(p => p.id === focusLead) || null

  const discover = () => {
    if (!rest) return
    setBusy('discover')
    notify('Searching permitted public pages… this can take a minute.')
    rest('/setup', { method: 'POST', body: { action: 'discover', business_id: pipe.business_id } })
      .then(body => {
        if (!body || body.ok === false) return notify(errText(body, 'Discovery did not run.'), 'err')
        const run = (body.discovery && typeof body.discovery === 'object') ? body.discovery : {}
        // The envelope is ok when the setup state could be read; a search that never ran is a failure
        // and must not read like a completed, empty search.
        if (run.ok === false) return notify(errText(run, 'Discovery did not run.'), 'err')
        const found = (run.prospects || []).length
        notify(found ? `Discovery saved ${found} quoted prospect${found === 1 ? '' : 's'}.` : 'Discovery finished. No company was quoted with a contact, so nothing was added.')
        refresh()
      })
      .catch(err => notify(err && err.message ? err.message : 'Discovery did not run.', 'err'))
      .finally(() => setBusy(''))
  }

  if (pipe.ok === false && pipe.code === 'schema_pending') return h('div', { className: 'sp-page' }, h(Empty, { title: 'Updating storage', body: 'SalesPilot is migrating its records. This view returns in a moment.' }))
  if (!pipe.business_id) {
    return h('div', { className: 'sp-page' }, h(Empty, { iconName: 'users', title: 'Set up your first brand', body: 'Tell SalesPilot what you sell and who you sell to. Then import customers or let Hermes find them.' },
      h('button', { type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => setSection('settings') }, 'Open Settings', icon('right'))))
  }

  const header = h('div', { key: 'head', className: 'sp-head' },
    h('div', null,
      h('h1', { className: 'sp-h1' }, 'Customers'),
      h('p', { className: 'sp-sub' }, `${pipe.total || prospects.length} in pipeline · ${importedRows.length} imported${due ? ` · ${due} follow-up${due === 1 ? '' : 's'} due` : ''}`)),
    h('div', { className: 'sp-row' },
      h('button', { type: 'button', className: 'sp-btn', onClick: () => setImporting(true) }, icon('upload'), 'Import CSV'),
      h('button', { type: 'button', className: 'sp-btn', disabled: busy === 'discover', onClick: discover, title: 'Search permitted public pages for your target market' }, icon('search'), busy === 'discover' ? 'Searching…' : 'Discover'),
      h('button', { type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => askHermes(PROMPTS.findLeads(brandName), notify) }, icon('chat'), 'Find leads with Hermes')))

  const journey = h('div', { key: 'journey', className: 'sp-journey', role: 'group', 'aria-label': 'Outreach journey' },
    JOURNEY.map((step, index) => h('button', {
      key: step.id, type: 'button', className: 'sp-step', 'aria-pressed': stage === step.id,
      onClick: () => { setView('pipeline'); setStage(stage === step.id ? '' : step.id) }
    },
    h('span', { className: 'sp-step-k' }, h('span', { className: 'sp-num' }, String(index + 1)), step.label),
    h('span', { className: 'sp-step-n' }, String(counts[step.id] || 0)),
    h('span', { className: 'sp-step-d' }, step.hint))))

  const toolbar = h('div', { key: 'tools', className: 'sp-toolbar' },
    h('div', { className: 'sp-seg', role: 'group', 'aria-label': 'List' },
      h('button', { key: 'p', type: 'button', 'aria-pressed': view === 'pipeline', onClick: () => setView('pipeline') }, 'Pipeline', h('span', { className: 'sp-count' }, String(prospects.length - (counts.closed || 0)))),
      h('button', { key: 'i', type: 'button', 'aria-pressed': view === 'imported', onClick: () => setView('imported') }, 'Imported', h('span', { className: 'sp-count' }, String(importedRows.length))),
      h('button', { key: 'c', type: 'button', 'aria-pressed': view === 'pipeline' && stage === 'closed', onClick: () => { setView('pipeline'); setStage(stage === 'closed' ? '' : 'closed') } }, 'Inactive', h('span', { className: 'sp-count' }, String(counts.closed || 0)))),
    h('div', { className: 'sp-search' }, icon('search'),
      h('input', { className: 'sp-input', 'aria-label': 'Search customers', placeholder: 'Search company, email or evidence', value: query, onChange: e => setQuery(e.target.value) })),
    stage ? h('button', { type: 'button', className: 'sp-btn sp-btn-ghost sp-btn-sm', onClick: () => setStage('') }, icon('x'), 'Clear filter') : null)

  let list
  if (view === 'imported') {
    list = h(ImportedTable, { rows: importedRows.filter(c => !q || `${c.company} ${c.email} ${c.contact_name} ${c.segment}`.toLowerCase().includes(q)), brandName, notify, onImport: () => setImporting(true) })
  } else if (!prospects.length) {
    list = h(Empty, { iconName: 'users', title: 'No customers yet', body: 'Start with a list you already have, or let Hermes collect companies with quoted public evidence. Nothing is ever sent without your approval.' },
      h('div', { className: 'sp-start' },
        h('button', { key: 'i', type: 'button', onClick: () => setImporting(true) }, icon('upload'), h('strong', null, 'Import a CSV'), h('span', null, 'Bring your existing customers. You map the columns.')),
        h('button', { key: 'f', type: 'button', onClick: () => askHermes(PROMPTS.findLeads(brandName), notify) }, icon('chat'), h('strong', null, 'Find leads with Hermes'), h('span', null, 'Hermes researches companies that match your ICP.'))))
  } else if (!rows.length) {
    list = h(Empty, { iconName: 'search', title: 'Nothing here', body: q ? `No customer matches “${query}”.` : 'No customer is at this step right now.' })
  } else {
    list = h('div', { className: 'sp-table', role: 'table', 'aria-label': 'Customers' },
      h('div', { key: 'th', className: 'sp-tr sp-th', role: 'row' },
        h('span', { role: 'columnheader' }, 'Company'), h('span', { role: 'columnheader' }, 'Status'),
        h('span', { role: 'columnheader' }, 'Emailed'), h('span', { role: 'columnheader' }, 'Replied'),
        h('span', { role: 'columnheader' }, 'Next step')),
      rows.map(p => {
        const follow = followLine(p)
        return h('button', { key: p.id, type: 'button', role: 'row', className: 'sp-tr', 'aria-selected': p.id === focusLead, onClick: () => setFocusLead(p.id === focusLead ? '' : p.id) },
          h('span', { className: 'sp-cell' }, h('span', { className: 'sp-avatar' }, initials(p.company)),
            h('span', { className: 'sp-cell-stack' }, h('span', { className: 'sp-strong' }, p.company || 'Unnamed company'), h('span', { className: 'sp-muted sp-small sp-trunc' }, p.email || p.contact_name || 'No contact on file'))),
          h('span', { className: 'sp-cell' }, h(StatusPill, { status: p.status })),
          h(DateCell, { value: p.introduced_at, empty: 'Not yet' }),
          h(DateCell, { value: p.last_reply_at, empty: p.introduced_at ? 'No reply' : '—', strong: !!p.last_reply_at }),
          h('span', { className: 'sp-cell sp-small sp-trunc' }, h('span', { className: 'sp-dot', style: { '--tone': `var(--sp-${follow.tone === 'neutral' ? 'line' : follow.tone})` } }), h('span', { className: 'sp-trunc', style: { color: follow.tone === 'amber' ? 'var(--sp-amber)' : 'var(--sp-text-2)' } }, follow.text)))
      }))
  }

  return h('div', { className: 'sp-page' },
    header,
    h(Checklist, { key: 'start', setup: (data && data.setup) || {}, hasCustomers: prospects.length + importedRows.length > 0, onSettings: target => setSection('settings', target), onImport: () => setImporting(true), onFind: () => askHermes(PROMPTS.findLeads(brandName), notify) }),
    h(Today, { key: 'today', prospects, drafts, onOpen: id => { setView('pipeline'); setStage(''); setFocusLead(id) } }),
    journey, toolbar,
    h('div', { key: 'split', className: `sp-split ${selected && view === 'pipeline' ? 'sp-open' : ''}` },
      list,
      selected && view === 'pipeline' ? h(CustomerPanel, { key: selected.id, p: selected, drafts, businessId: pipe.business_id, mail: pipe.mail || {}, notify, refresh, brandName, version, setSection, onClose: () => setFocusLead('') }) : null),
    importing ? h(ImportDialog, { businessId: pipe.business_id, brandName, notify, onClose: () => setImporting(false), onDone: () => { setImporting(false); setView('imported'); refresh() } }) : null)
}

// ---------------------------------------------------------------------------------------------
// Getting started + Today: answer "where do I start" and "who needs me today" before anything else.
// ---------------------------------------------------------------------------------------------

function Checklist({ setup, hasCustomers, onSettings, onImport, onFind }) {
  if (!setup || setup.ok === false || !setup.business_id) return null
  const mail = setup.mail || {}
  const icp = safeIcp(setup)
  const steps = [
    { id: 'brand', label: 'Describe your business', done: !!(setup.business && setup.business.products && setup.business.target_market), action: () => onSettings('sp-set-brand'), cta: 'Describe' },
    { id: 'email', label: 'Connect your email', done: mail.connection === 'connected' || mail.connection === 'unverified', note: mail.research_only ? 'research-only for now' : mail.connection === 'missing_credentials' ? 'add the mailbox password' : '', action: () => onSettings('sp-set-email'), cta: 'Connect' },
    { id: 'icp', label: 'Define your ideal customer', done: icp.status === 'configured', action: () => onSettings('sp-set-icp'), cta: 'Define' },
    { id: 'leads', label: 'Add your first customers', done: hasCustomers, action: onImport, cta: 'Import CSV', alt: onFind, altCta: 'Ask Hermes' }
  ]
  const left = steps.filter(step => !step.done)
  if (!left.length) return null
  const doneCount = steps.length - left.length
  return h('section', { className: 'sp-getting', 'aria-label': 'Getting started' },
    h('div', { key: 'h', className: 'sp-getting-h' },
      h('strong', null, 'Getting started'),
      h('span', { className: 'sp-muted sp-small' }, `${doneCount} of ${steps.length} done`),
      h('span', { className: 'sp-progress', 'aria-hidden': 'true' }, h('i', { style: { width: `${(doneCount / steps.length) * 100}%` } }))),
    h('ol', { key: 'l', className: 'sp-getting-l' }, steps.map((step, index) => h('li', { key: step.id, className: step.done ? 'done' : '' },
      h('span', { className: 'sp-getting-n' }, step.done ? icon('check') : String(index + 1)),
      h('span', { className: 'sp-getting-t' }, step.label, step.note && !step.done ? h('span', { className: 'sp-faint' }, ` · ${step.note}`) : null),
      !step.done ? h('span', { className: 'sp-row' },
        step.alt ? h('button', { type: 'button', className: 'sp-btn sp-btn-ghost sp-btn-sm', onClick: step.alt }, step.altCta) : null,
        h('button', { type: 'button', className: 'sp-btn sp-btn-sm', onClick: step.action }, step.cta)) : null))))
}

function Today({ prospects, drafts, onOpen }) {
  const groups = [
    { id: 'reply', label: 'Replied, answer them', tone: 'green', items: prospects.filter(p => stageOf(p) === 'replied') },
    { id: 'follow', label: 'Follow up today', tone: 'amber', items: prospects.filter(p => stageOf(p) === 'followup' && p.status !== 'followed_up') },
    { id: 'approve', label: 'Waiting for your approval', tone: 'blue', items: prospects.filter(p => stageOf(p) === 'approve' || (stageOf(p) === 'prepare' && drafts.some(d => d.lead_id === p.id))) }
  ].filter(group => group.items.length)
  if (!groups.length) return null
  const total = groups.reduce((n, g) => n + g.items.length, 0)
  return h('section', { className: 'sp-today', 'aria-label': 'Today' },
    h('div', { key: 'h', className: 'sp-today-h' }, h('strong', null, 'Today'), h('span', { className: 'sp-muted sp-small' }, `${total} customer${total === 1 ? ' needs' : 's need'} you`)),
    h('div', { key: 'g', className: 'sp-today-g' }, groups.map(group => h('div', { key: group.id, className: 'sp-today-col' },
      h('span', { className: `sp-pill tone-${group.tone}` }, `${group.label} · ${group.items.length}`),
      group.items.slice(0, 3).map(p => h('button', { key: p.id, type: 'button', className: 'sp-today-item', onClick: () => onOpen(p.id) },
        h('span', { className: 'sp-avatar' }, initials(p.company)),
        h('span', { className: 'sp-cell-stack' }, h('span', { className: 'sp-strong' }, p.company),
          h('span', { className: 'sp-small sp-muted sp-trunc' }, group.id === 'reply' ? (p.last_reply_excerpt || `Replied ${ago(p.last_reply_at)}`) : group.id === 'follow' ? `${followLine(p).text}${p.introduced_at ? ` · emailed ${shortDate(p.introduced_at)}` : ''}` : 'Read the draft, then send with approval')),
        icon('right', 'sp-today-go'))),
      group.items.length > 3 ? h('span', { className: 'sp-small sp-faint' }, `+${group.items.length - 3} more below`) : null))))
}

// A date the user can act on: the calendar day on top, how long ago underneath.
function DateCell({ value, empty, strong }) {
  if (!parseDate(value)) return h('span', { className: 'sp-small sp-faint' }, empty || '—')
  return h('span', { className: 'sp-cell-stack sp-small sp-tabnum', title: parseDate(value).toLocaleString() },
    h('span', { style: { fontWeight: strong ? 550 : 450 } }, shortDate(value)),
    h('span', { className: 'sp-faint' }, ago(value)))
}

function ImportedTable({ rows, brandName, notify, onImport }) {
  if (!rows.length) {
    return h(Empty, { iconName: 'upload', title: 'No imported customers', body: 'Import a CSV of customers you already know. Each row keeps its source and permission note.' },
      h('button', { type: 'button', className: 'sp-btn sp-btn-primary', onClick: onImport }, icon('upload'), 'Import CSV'))
  }
  return h('div', { className: 'sp-table', role: 'table', 'aria-label': 'Imported customers' },
    h('div', { key: 'th', className: 'sp-tr sp-tr-imp sp-th', role: 'row' },
      h('span', null, 'Company'), h('span', null, 'Contact'), h('span', null, 'Segment'), h('span', null, 'Added'), h('span', null, '')),
    rows.map(c => h('div', { key: c.id, role: 'row', className: 'sp-tr sp-tr-imp', style: { cursor: 'default' } },
      h('span', { className: 'sp-cell' }, h('span', { className: 'sp-avatar' }, initials(c.company)),
        h('span', { className: 'sp-cell-stack' }, h('span', { className: 'sp-strong' }, c.company), h('span', { className: 'sp-muted sp-small sp-trunc' }, `From ${c.source}`))),
      h('span', { className: 'sp-cell-stack sp-small' },
        h('span', { className: 'sp-trunc' }, c.contact_name || c.email || c.phone || '—'),
        h('span', { className: 'sp-muted sp-trunc' }, c.contact_name && c.email ? `${c.email}${c.email_valid ? '' : ' · invalid format'}` : c.email && !c.email_valid ? 'Invalid email format' : (c.phone || (c.email ? 'No name on file' : 'No email')))),
      h('span', { className: 'sp-small sp-muted sp-trunc' }, c.segment || '—'),
      h('span', { className: 'sp-small sp-muted sp-tabnum' }, ago(c.created_at)),
      h('span', { className: 'sp-cell', style: { justifyContent: 'flex-end' } },
        h('button', { type: 'button', className: 'sp-btn sp-btn-sm', onClick: () => askHermes(PROMPTS.researchImported(c, brandName), notify) }, icon('chat'), 'Research')))))
}

function CustomerPanel({ p, drafts, businessId, mail, notify, refresh, brandName, version, onClose, setSection }) {
  const [timeline, setTimeline] = useState(null)
  const [busy, setBusy] = useState('')
  const [note, setNote] = useState(p.note || '')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const draft = drafts.filter(d => d.lead_id === p.id && d.channel !== 'whatsapp').sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0] || null

  useEffect(() => {
    let stop = false
    if (!rest) return undefined
    rest(`/timeline?lead_id=${encodeURIComponent(p.id)}&business_id=${encodeURIComponent(businessId || '')}`)
      .then(body => { if (!stop) setTimeline(body || { ok: false }) })
      .catch(err => { if (!stop) setTimeline({ ok: false, error: err && err.message }) })
    return () => { stop = true }
  }, [p.id, version])

  const post = (path, body, success, key) => {
    if (!rest) return Promise.resolve(null)
    setBusy(key || path)
    return rest(path, { method: 'POST', body: { business_id: businessId, lead_id: p.id, ...body } })
      .then(result => {
        if (!result || result.ok === false) { notify(errText(result, 'That did not save.'), 'err'); return result }
        if (success) notify(typeof success === 'function' ? success(result) : success)
        refresh()
        return result
      })
      .catch(err => { notify(err && err.message ? err.message : 'That did not save.', 'err'); return null })
      .finally(() => setBusy(''))
  }
  const setStatus = (status, label) => post('/pipeline', { action: 'status', status }, label, status)

  const qualify = () => post('/qualify', {}, result => {
    const q = result.qualification || {}
    if (q.decision === 'qualified') return 'Qualified. You can prepare the email draft now.'
    const why = (q.reasons || []).slice(0, 2).join(', ').replace(/_/g, ' ')
    return q.decision === 'reject' ? `Not a fit${why ? `: ${why}` : ''}.` : `On hold${why ? `: ${why}` : ''}. Ask Hermes to research it.`
  }, 'qualify')
  const prepare = () => post('/draft', {}, 'Draft ready. Review it, then send with approval.', 'draft')

  const f = p.followup || {}
  const stage = stageOf(p)
  // Ready means a send can actually succeed: settings saved, both credentials present, not research-only.
  // A saved host alone is not enough; the button must not promise a send that will be refused.
  const mailReady = !!(mail && mail.configured && mail.username_present && mail.password_present && !mail.research_only)
  const connectEmail = h('button', { key: 'ce', type: 'button', className: 'sp-btn', onClick: () => setSection && setSection('settings', 'sp-set-email') }, icon('mail'), 'Connect email')
  let next
  if (stage === 'closed') {
    next = { k: 'Closed', t: (STATUS[p.status] || [p.status])[0], body: p.next_action, actions: p.status === 'do_not_contact' ? [] : [
      h('button', { key: 'r', type: 'button', className: 'sp-btn', disabled: !!busy, onClick: () => setStatus('discovered', 'Moved back to New.') }, 'Reopen')] }
  } else if (draft && (p.status === 'draft_ready' || p.status === 'qualified' || stage === 'prepare')) {
    next = { k: 'Step 3 · Approve', t: 'Your draft is waiting for approval', body: mailReady ? 'Send with approval opens Hermes chat. Hermes shows the email and asks you to confirm before exactly one message leaves.' : 'Connect your email first. The draft stays saved, and nothing is sent until you approve it.', actions: [
      mailReady ? h('button', { key: 's', type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => askHermes(PROMPTS.send(draft.id), notify) }, icon('send'), 'Send with approval') : connectEmail,
      h('button', { key: 'c', type: 'button', className: 'sp-btn sp-btn-ghost', onClick: () => askHermes(`Improve the SalesPilot email draft ${draft.id} for ${p.company}. Keep it short and specific. Do not send it.`, notify) }, icon('chat'), 'Refine in chat')] }
  } else if (stage === 'replied') {
    next = { k: 'Step 5 · Respond', t: 'They replied — answer personally', body: p.last_reply_excerpt || 'Read the reply in the timeline below.', quote: !!p.last_reply_excerpt, actions: [
      h('button', { key: 'r', type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => askHermes(PROMPTS.reply(p), notify) }, icon('reply'), 'Draft reply with Hermes'),
      h('button', { key: 'n', type: 'button', className: 'sp-btn sp-btn-ghost', disabled: !!busy, onClick: () => setStatus('not_interested', 'Marked not interested.') }, 'Not interested')] }
  } else if (stage === 'followup') {
    next = { k: 'Step 6 · Follow up', t: p.status === 'followed_up' ? 'Followed up — waiting for a reply' : 'A follow-up is due', body: f.reason ? `${f.reason.charAt(0).toUpperCase()}${f.reason.slice(1)} · attempt ${f.attempts || 0}.` : p.next_action, actions: p.status === 'followed_up' ? [
      h('button', { key: 'i', type: 'button', className: 'sp-btn', disabled: !!busy, onClick: () => post('/inbox', { action: 'sync' }, r => `Inbox checked. ${(r.recorded || r.matched || 0)} new message(s).`, 'inbox') }, icon('refresh'), 'Check inbox')] : [
      h('button', { key: 'w', type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => askHermes(PROMPTS.followup(p), notify) }, icon('chat'), 'Write follow-up with Hermes'),
      h('button', { key: 'd', type: 'button', className: 'sp-btn sp-btn-ghost', disabled: !!busy, onClick: () => setStatus('followed_up', 'Marked as followed up.') }, icon('check'), 'Mark done')] }
  } else if (stage === 'sent') {
    next = { k: 'Step 4 · Watch replies', t: 'Waiting for a reply', body: `${p.introduced_at ? `Emailed ${shortDate(p.introduced_at)}. ` : ''}${f.next_due ? `A follow-up comes due ${inDays(f.next_due)}. ` : ''}Replies are matched from your inbox when reply tracking is on.`, actions: [
      h('button', { key: 'i', type: 'button', className: 'sp-btn', disabled: !!busy, onClick: () => post('/inbox', { action: 'sync' }, r => `Inbox checked. ${(r.recorded || r.matched || 0)} new message(s).`, 'inbox') }, icon('refresh'), busy === 'inbox' ? 'Checking…' : 'Check inbox')] }
  } else if (p.status === 'qualified' || stage === 'prepare' || stage === 'approve') {
    next = { k: 'Step 2 · Prepare', t: 'Prepare the first email', body: 'SalesPilot writes a draft from your offer and the quoted evidence. Nothing is sent.', actions: [
      h('button', { key: 'p', type: 'button', className: 'sp-btn sp-btn-primary', disabled: !!busy, onClick: prepare }, icon('mail'), busy === 'draft' ? 'Preparing…' : 'Prepare email draft')] }
  } else {
    next = { k: 'Step 1 · Qualify', t: 'Check the fit', body: p.next_action || 'Review the evidence, then qualify.', actions: [
      h('button', { key: 'q', type: 'button', className: 'sp-btn sp-btn-primary', disabled: !!busy, onClick: qualify }, icon('check'), busy === 'qualify' ? 'Checking…' : 'Qualify'),
      h('button', { key: 'r', type: 'button', className: 'sp-btn sp-btn-ghost', onClick: () => askHermes(PROMPTS.research(p, brandName), notify) }, icon('chat'), 'Research with Hermes')] }
  }

  const events = []
  if (timeline && timeline.ok) {
    (timeline.messages || []).forEach(m => events.push({ id: `m${m.id}`, at: m.at, kind: m.direction === 'inbound' ? 'in' : 'out', title: m.direction === 'inbound' ? `Reply${m.intent ? ` · ${m.intent.replace(/_/g, ' ')}` : ''}` : `Email sent${m.subject ? ` · ${m.subject}` : ''}`, body: m.excerpt }))
    ;(timeline.events || []).forEach(e => {
      if (['smtp_accepted', 'reply_observed'].includes(e.kind)) return
      events.push({ id: `e${e.id || e.created_at}${e.kind}`, at: e.created_at, kind: 'ev', title: e.kind.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()), body: '' })
    })
    events.sort((a, b) => String(b.at).localeCompare(String(a.at)))
  }
  const readiness = p.readiness || {}

  return h('aside', { className: 'sp-panel', 'aria-label': `${p.company} details` },
    h('div', { key: 'h', className: 'sp-panel-head' },
      h('span', { className: 'sp-avatar sp-avatar-lg' }, initials(p.company)),
      h('div', { style: { flex: 1, minWidth: 0 } },
        h('h2', { className: 'sp-panel-title' }, p.company || 'Unnamed company'),
        h('div', { className: 'sp-row', style: { marginTop: 6 } }, h(StatusPill, { status: p.status }),
          p.email ? h('button', { type: 'button', className: 'sp-btn sp-btn-ghost sp-btn-sm', title: 'Copy email', onClick: () => Promise.resolve(osApi && osApi.writeClipboard ? osApi.writeClipboard(p.email) : false).then(ok => notify(ok ? 'Email copied.' : p.email)) }, icon('copy'), h('span', { className: 'sp-trunc', style: { maxWidth: 190 } }, p.email)) : null)),
      h('button', { type: 'button', className: 'sp-btn sp-btn-ghost sp-icon-btn', 'aria-label': 'Close', onClick: onClose }, icon('x'))),
    h('div', { key: 'b', className: 'sp-panel-body' },
      h('section', { key: 'next', className: 'sp-next' },
        h('span', { className: 'sp-next-k' }, next.k),
        h('span', { className: 'sp-next-t' }, next.t),
        next.body ? (next.quote ? h('p', { className: 'sp-quote sp-quote-hot' }, next.body) : h('p', null, next.body)) : null,
        next.actions.length ? h('div', { className: 'sp-row' }, next.actions) : null),
      draft ? h('section', { key: 'draft' },
        h('p', { className: 'sp-label' }, 'Email draft'),
        h('div', { className: 'sp-draft' },
          h('div', { className: 'sp-draft-h' },
            h('span', null, h('span', { className: 'sp-muted' }, 'To '), draft.recipient || '—'),
            h('strong', null, draft.subject || 'No subject')),
          h('div', { className: 'sp-draft-b' }, draft.body, draft.signature ? `\n\n${draft.signature}` : ''))) : null,
      h('section', { key: 'facts' },
        h('p', { className: 'sp-label' }, 'Details'),
        h('dl', { className: 'sp-facts' },
          h('dt', { key: 'a' }, 'Contact'), h('dd', { key: 'b' }, [p.contact_name, p.recipient && p.recipient.role].filter(Boolean).join(' · ') || (p.email ? 'Business inbox' : 'None on file')),
          h('dt', { key: 'c' }, 'Who reads it'), h('dd', { key: 'd' }, READINESS[readiness.status] || (readiness.status ? readiness.status.replace(/_/g, ' ') : '—'), readiness.deliverability === 'unverified' ? h('span', { className: 'sp-faint' }, ' · address not verified') : null),
          h('dt', { key: 'e' }, 'Company fit'), h('dd', { key: 'f' }, p.company_fit === 'fit' ? 'Matches your ICP' : p.company_fit === 'excluded' ? 'Excluded' : 'Not proven yet'),
          h('dt', { key: 'g' }, 'Sender'), h('dd', { key: 'h' }, (p.sender && p.sender.address) || (mail && mail.from_address) || 'Not set'),
          h('dt', { key: 'i' }, 'First email'), h('dd', { key: 'j' }, p.introduced_at ? `${shortDate(p.introduced_at)} · ${ago(p.introduced_at)}` : 'Not sent'),
          h('dt', { key: 'm' }, 'Last reply'), h('dd', { key: 'n' }, p.last_reply_at ? `${shortDate(p.last_reply_at)} · ${ago(p.last_reply_at)}` : 'None yet'),
          h('dt', { key: 'k' }, 'Follow-ups'), h('dd', { key: 'l' }, `${f.attempts || 0} sent · ${followLine(p).text}`))),
      p.evidence ? h('section', { key: 'ev' },
        h('p', { className: 'sp-label' }, 'Why this company'),
        h('p', { className: 'sp-quote' }, p.evidence),
        p.source_url ? h('div', { className: 'sp-small sp-muted', style: { marginTop: 6 } }, icon('link', 'sp-inline'), ' ', h('a', { href: p.source_url, target: '_blank', rel: 'noreferrer' }, p.source_url.replace(/^https?:\/\//, ''))) : null) : null,
      h('section', { key: 'tl' },
        h('p', { className: 'sp-label' }, 'Activity'),
        timeline === null ? h('div', { className: 'sp-skel', style: { height: 60 } }) :
          !events.length ? h('p', { className: 'sp-muted sp-small', style: { margin: 0 } }, timeline && timeline.ok === false ? errText(timeline, 'History is unavailable.') : 'No activity yet.') :
            h('ul', { className: 'sp-tl' }, events.slice(0, 20).map(e => h('li', { key: e.id, className: e.kind === 'in' ? 'sp-tl-in' : e.kind === 'out' ? 'sp-tl-out' : '' },
              h('span', { className: 'sp-tl-dot' }, icon(e.kind === 'in' ? 'reply' : e.kind === 'out' ? 'send' : 'clock')),
              h('div', { style: { minWidth: 0 } },
                h('div', { className: 'sp-small' }, h('strong', { style: { fontWeight: 550 } }, e.title), h('span', { className: 'sp-faint' }, ` · ${ago(e.at)}`)),
                e.body ? h('div', { className: 'sp-small sp-muted', style: { overflowWrap: 'anywhere' } }, e.body) : null))))),
      h('section', { key: 'note' },
        h('p', { className: 'sp-label' }, 'Note'),
        h('textarea', { className: 'sp-textarea', 'aria-label': 'Note', placeholder: 'Add context for your team…', value: note, onChange: e => setNote(e.target.value), style: { minHeight: 60 } }),
        note.trim() !== (p.note || '').trim() ? h('div', { className: 'sp-row', style: { marginTop: 8 } },
          h('button', { type: 'button', className: 'sp-btn sp-btn-sm', disabled: !note.trim() || !!busy, onClick: () => post('/pipeline', { action: 'note', note: note.trim() }, 'Note saved.', 'note') }, 'Save note')) : null),
      h('div', { key: 'div', className: 'sp-divider' }),
      h('section', { key: 'more', className: 'sp-row' },
        p.status !== 'not_interested' ? h('button', { key: 'ni', type: 'button', className: 'sp-btn sp-btn-sm', disabled: !!busy, onClick: () => setStatus('not_interested', 'Marked not interested.') }, 'Not interested') : null,
        p.status !== 'do_not_contact' ? h('button', { key: 'dn', type: 'button', className: 'sp-btn sp-btn-sm', disabled: !!busy, onClick: () => setStatus('do_not_contact', 'Will never be contacted.') }, 'Do not contact') : null,
        !p.archived ? h('button', { key: 'ar', type: 'button', className: 'sp-btn sp-btn-sm', disabled: !!busy, onClick: () => post('/pipeline', { action: 'archive' }, 'Archived.', 'archive').then(() => onClose()) }, 'Archive') : null,
        h('button', { key: 'del', type: 'button', className: 'sp-btn sp-btn-sm sp-btn-danger', disabled: !!busy, onClick: () => confirmDelete ? post('/pipeline', { action: 'delete', confirm_delete: true }, 'Deleted.', 'delete').then(() => onClose()) : setConfirmDelete(true) }, confirmDelete ? 'Click again to delete' : 'Delete'))))
}

// ---------------------------------------------------------------------------------------------
// CSV import
// ---------------------------------------------------------------------------------------------

const FIELDS = [['company', 'Company'], ['contact_name', 'Contact name'], ['email', 'Email'], ['phone', 'Phone'], ['segment', 'Segment'], ['notes', 'Notes']]
const GUESS = [
  ['company', /^(company|perusahaan|nama perusahaan|organi[sz]ation|account|business|toko|instansi|customer|pelanggan)/i],
  ['email', /e-?mail/i],
  ['phone', /(phone|telp|telepon|tel\b|hp\b|^wa\b|whatsapp|mobile|no\.? ?hp)/i],
  ['contact_name', /(contact|pic\b|^name$|^nama$|full ?name|nama kontak)/i],
  ['segment', /(segment|industr|sector|sektor|kategori|category)/i],
  ['notes', /(note|catatan|keterangan|remark)/i]
]

function csvHeader(text) {
  const line = String(text || '').replace(/^\uFEFF/, '').split(/\r?\n/)[0] || ''
  const out = []
  let cur = ''
  let quoted = false
  for (let i = 0; i < line.length; i += 1) {
    const c = line[i]
    if (quoted) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i += 1 } else if (c === '"') quoted = false
      else cur += c
    } else if (c === '"') quoted = true
    else if (c === ',') { out.push(cur); cur = '' } else cur += c
  }
  out.push(cur)
  return out.filter(name => name.trim())
}

function guessMapping(headers) {
  const mapping = {}
  const used = new Set()
  for (const [field, pattern] of GUESS) {
    const match = headers.find(name => !(name in mapping) && pattern.test(name.trim()))
    if (match && !used.has(field)) { mapping[match] = field; used.add(field) }
  }
  return mapping
}

function ImportDialog({ businessId, brandName, notify, onClose, onDone }) {
  const [text, setText] = useState('')
  const [fileName, setFileName] = useState('')
  const [mapping, setMapping] = useState({})
  const [agree, setAgree] = useState(false)
  const [origin, setOrigin] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const headers = csvHeader(text)
  const rowCount = text ? Math.max(0, text.split(/\r?\n/).filter(line => line.trim()).length - 1) : 0
  const hasCompany = Object.values(mapping).includes('company')

  const load = (raw, name) => {
    setText(raw)
    setFileName(name || '')
    setMapping(guessMapping(csvHeader(raw)))
    setResult(null)
  }
  const pick = e => {
    const file = e.target.files && e.target.files[0]
    if (!file) return
    if (file.size > 2_000_000) return notify('Keep one import under 2 MB.', 'err')
    file.text().then(raw => load(raw, file.name)).catch(() => notify('That file could not be read.', 'err'))
  }
  const setField = (header, field) => setMapping(current => {
    const next = { ...current }
    Object.keys(next).forEach(key => { if (field && next[key] === field) delete next[key] })
    if (field) next[header] = field
    else delete next[header]
    return next
  })
  const submit = () => {
    if (!rest) return
    setBusy(true)
    rest('/import', { method: 'POST', body: { business_id: businessId, csv_text: text, mapping, authorized: agree, authorization_note: origin.trim(), source: fileName || 'pasted csv' } })
      .then(body => {
        if (!body || body.ok === false) return notify(errText(body, 'The import did not run.'), 'err')
        setResult(body)
      })
      .catch(err => notify(err && err.message ? err.message : 'The import did not run.', 'err'))
      .finally(() => setBusy(false))
  }

  let content
  if (result) {
    const errors = result.row_errors || []
    content = h('div', { className: 'sp-dialog-b' },
      h('div', { className: 'sp-stats', style: { gridTemplateColumns: 'repeat(3,minmax(0,1fr))' } },
        h('div', { key: 'a', className: 'sp-stat' }, h('div', { className: 'sp-stat-n' }, String(result.inserted_count || 0)), h('div', { className: 'sp-stat-k' }, 'Added')),
        h('div', { key: 'b', className: 'sp-stat' }, h('div', { className: 'sp-stat-n' }, String(result.skipped_count || 0)), h('div', { className: 'sp-stat-k' }, 'Already on file')),
        h('div', { key: 'c', className: 'sp-stat' }, h('div', { className: 'sp-stat-n' }, String(errors.length)), h('div', { className: 'sp-stat-k' }, 'Rows skipped'))),
      errors.length ? h('div', { className: 'sp-callout sp-callout-warn' }, icon('alert'), h('span', null, errors.slice(0, 4).map(e => `Row ${e.row}: ${String(e.code).replace(/_/g, ' ')}`).join(' · '), errors.length > 4 ? ` · +${errors.length - 4} more` : '')) : null,
      h('p', { className: 'sp-muted', style: { margin: 0 } }, 'Imported customers stay in the Imported list. Ask Hermes to research one to add it to your outreach pipeline with evidence.'))
  } else {
    content = h('div', { className: 'sp-dialog-b' },
      h('label', { key: 'drop', className: 'sp-drop' },
        h('input', { type: 'file', accept: '.csv,text/csv', 'aria-label': 'Choose CSV file', onChange: pick }),
        h('span', { className: 'sp-empty-icon' }, icon('upload')),
        h('strong', null, fileName || 'Choose a CSV file'),
        h('span', { className: 'sp-muted sp-small' }, text ? `${rowCount} row${rowCount === 1 ? '' : 's'} · ${headers.length} columns` : 'CSV with column names in the first row. From Excel: File → Save As → CSV. Max 2 MB.')),
      !text ? h('details', { key: 'paste' }, h('summary', { className: 'sp-small sp-muted', style: { cursor: 'pointer' } }, 'Or paste CSV text'),
        h('textarea', { className: 'sp-textarea', style: { marginTop: 8 }, 'aria-label': 'CSV text', placeholder: 'company,email\nPT Contoh,halo@contoh.test', onChange: e => load(e.target.value, '') })) : null,
      headers.length ? h('div', { key: 'map' },
        h('p', { className: 'sp-label' }, 'Match your columns'),
        h('div', { className: 'sp-map' }, headers.map(name => [
          h('span', { key: `${name}-a`, className: 'sp-trunc' }, name),
          h('span', { key: `${name}-b` }, icon('right')),
          h(Select, {
            key: `${name}-c`, className: 'sp-dd-sm', ariaLabel: `Field for ${name}`,
            value: mapping[name] || '', placeholder: 'Skip column',
            options: [{ value: '', label: 'Skip column' }].concat(FIELDS.map(([id, label]) => ({ value: id, label }))),
            onChange: next => setField(name, next)
          })])),
        !hasCompany ? h('p', { className: 'sp-small', style: { color: 'var(--sp-red)', margin: '8px 0 0' } }, 'Pick which column holds the company name.') : null) : null,
      text ? h('div', { key: 'perm', className: 'sp-field' },
        h('span', null, 'Where is this list from?'),
        h('input', { className: 'sp-input', value: origin, onChange: e => setOrigin(e.target.value), placeholder: 'e.g. Customers from our 2026 trade show' })) : null,
      text ? h('label', { key: 'agree', className: 'sp-check' },
        h('input', { type: 'checkbox', checked: agree, onChange: e => setAgree(e.target.checked) }),
        h('span', null, `I have permission to contact these customers on behalf of ${brandName}.`)) : null)
  }

  return h('div', { className: 'sp-overlay', role: 'presentation', onMouseDown: e => { if (e.target === e.currentTarget) onClose() } },
    h('div', { className: 'sp-dialog', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Import customers' },
      h('div', { key: 'h', className: 'sp-dialog-h' }, h('h2', null, result ? 'Import finished' : 'Import customers'),
        h('button', { type: 'button', className: 'sp-btn sp-btn-ghost sp-icon-btn', 'aria-label': 'Close', onClick: onClose }, icon('x'))),
      content,
      h('div', { key: 'f', className: 'sp-dialog-f' },
        result ? h('button', { type: 'button', className: 'sp-btn sp-btn-primary', onClick: onDone }, 'View imported') : [
          h('button', { key: 'c', type: 'button', className: 'sp-btn sp-btn-ghost', onClick: onClose }, 'Cancel'),
          h('button', { key: 's', type: 'button', className: 'sp-btn sp-btn-primary', disabled: busy || !text || !hasCompany || !agree || !origin.trim(), onClick: submit }, busy ? 'Importing…' : `Import ${rowCount || ''} rows`.replace('  ', ' '))])))
}

// ---------------------------------------------------------------------------------------------
// Hot prospects
// ---------------------------------------------------------------------------------------------

const EVIDENCE = { imap_verified: 'read from your inbox', smtp_accepted: 'accepted by your mail server', manual: 'logged by you' }

function heatOf(item) {
  const interested = (item.interest_evidence || []).length
  let level = interested >= 2 ? 3 : interested === 1 ? 2 : 1
  if (item.needs_human) level = Math.max(level, 2)
  return level
}

function recommend(item) {
  const f = item.followup || {}
  if (item.needs_human) return { t: 'Reply personally', b: 'They asked something a template cannot answer. A human reply keeps the momentum.', tone: 'heat' }
  const hours = item.replied_at ? (Date.now() - (parseDate(item.replied_at) || new Date()).getTime()) / 3600000 : 0
  if (hours > 48) return { t: 'Reply today', b: `Their reply is ${ago(item.replied_at)}. Interest fades quickly after two days.`, tone: 'amber' }
  if (f.state === 'replied') return { t: 'Propose a next step', b: 'Answer with one concrete next step: a call, a sample or a quote.', tone: 'green' }
  return { t: 'Respond to the reply', b: 'Read the reply and answer while it is fresh.', tone: 'green' }
}

function HotView({ data, notify, refresh, brandName, openCustomer }) {
  const hot = (data && data.hot) || {}
  const pipe = (data && data.pipeline) || {}
  const [busy, setBusy] = useState(false)
  // Who to call first: a reply that needs a person, then the hottest, then the most recent.
  const items = (Array.isArray(hot.prospects) ? hot.prospects : []).slice().sort((a, b) =>
    (Number(!!b.needs_human) - Number(!!a.needs_human)) || (heatOf(b) - heatOf(a)) || String(b.replied_at || '').localeCompare(String(a.replied_at || '')))
  const prospects = Array.isArray(pipe.prospects) ? pipe.prospects : []
  const awaiting = prospects.filter(p => p.followup && p.followup.state === 'awaiting_reply').length
  const due = prospects.filter(p => p.followup && p.followup.state === 'followup_due').length
  const human = items.filter(i => i.needs_human).length

  const checkInbox = () => {
    if (!rest) return
    setBusy(true)
    rest('/inbox', { method: 'POST', body: { action: 'sync', business_id: pipe.business_id } })
      .then(body => {
        if (!body || body.ok === false) return notify(errText(body, 'The inbox check did not run.').replace(/_/g, ' '), 'err')
        notify('Inbox checked. New replies appear here once they are matched.')
        refresh()
      })
      .catch(err => notify(err && err.message ? err.message : 'The inbox check did not run.', 'err'))
      .finally(() => setBusy(false))
  }

  if (hot.ok === false) return h('div', { className: 'sp-page' }, h(Empty, { iconName: 'alert', title: 'Hot prospects unavailable', body: errText(hot, 'The hot list did not answer.') }))

  return h('div', { className: 'sp-page' },
    h('div', { key: 'head', className: 'sp-head' },
      h('div', null, h('h1', { className: 'sp-h1' }, 'Hot Prospects'),
        h('p', { className: 'sp-sub' }, 'Customers who answered your email with interest, hottest first. Auto-replies, bounces and neutral answers never count.')),
      h('button', { type: 'button', className: 'sp-btn', disabled: busy, onClick: checkInbox }, icon('refresh'), busy ? 'Checking…' : 'Check inbox')),
    h('div', { key: 'stats', className: 'sp-stats' },
      h('div', { key: 'a', className: 'sp-stat' }, h('div', { className: 'sp-stat-n', style: { color: items.length ? 'var(--sp-heat)' : undefined } }, String(items.length)), h('div', { className: 'sp-stat-k' }, 'Showed interest')),
      h('div', { key: 'b', className: 'sp-stat' }, h('div', { className: 'sp-stat-n' }, String(human)), h('div', { className: 'sp-stat-k' }, 'Need your reply')),
      h('div', { key: 'c', className: 'sp-stat' }, h('div', { className: 'sp-stat-n' }, String(awaiting)), h('div', { className: 'sp-stat-k' }, 'Awaiting reply')),
      h('div', { key: 'd', className: 'sp-stat' }, h('div', { className: 'sp-stat-n' }, String(due)), h('div', { className: 'sp-stat-k' }, 'Follow-ups due'))),
    !items.length ? h(Empty, { key: 'empty', iconName: 'flame', title: 'No verified interest yet', body: awaiting ? `${awaiting} customer${awaiting === 1 ? ' is' : 's are'} waiting on your email. When someone replies with interest, they appear here with their own words as proof.` : 'Send your first approved emails from Customers. Interested replies land here with their own words as proof.' },
      h('div', { className: 'sp-row', style: { justifyContent: 'center' } },
        h('button', { type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => openCustomer('') }, 'Go to Customers', icon('right')),
        due ? h('button', { type: 'button', className: 'sp-btn', onClick: () => openCustomer('') }, `${due} follow-up${due === 1 ? '' : 's'} due`) : null)) :
      items.map(item => {
        const rec = recommend(item)
        const level = heatOf(item)
        const firstOut = (item.evidence || []).find(e => e.direction === 'outbound')
        return h('article', { key: item.lead_id, className: 'sp-hot' },
          h('div', { className: 'sp-hot-main' },
            h('div', { className: 'sp-row', style: { justifyContent: 'space-between' } },
              h('div', { className: 'sp-cell' }, h('span', { className: 'sp-avatar sp-avatar-lg' }, initials(item.company || item.email)),
                h('div', { className: 'sp-cell-stack' }, h('span', { className: 'sp-strong', style: { fontSize: 14 } }, item.company || item.email || 'Unnamed contact'), h('span', { className: 'sp-muted sp-small sp-trunc' }, item.email))),
              h('span', { className: 'sp-row', title: `Heat ${level} of 3` },
                h('span', { className: 'sp-heat', 'aria-hidden': 'true' }, [6, 10, 14].map((height, i) => h('i', { key: i, className: i < level ? 'on' : '', style: { height } }))),
                h('span', { className: 'sp-small sp-muted' }, `${firstOut ? `Emailed ${shortDate(firstOut.at)} · ` : ''}Replied ${ago(item.replied_at)}`))),
            item.reply_excerpt ? h('blockquote', { className: 'sp-quote sp-quote-hot' }, item.reply_excerpt) : null,
            (item.interest_evidence || []).length ? h('div', null,
              h('p', { className: 'sp-label' }, 'Proof of interest'),
              h('ul', { className: 'sp-ev' }, item.interest_evidence.map((ev, i) => h('li', { key: ev.message_id || i },
                h('span', { className: 'sp-pill tone-green' }, (ev.intent || 'interested').replace(/_/g, ' ')),
                h('span', { className: 'sp-faint sp-tabnum' }, shortDate(ev.at)),
                h('span', { className: 'sp-faint' }, EVIDENCE[ev.level] || (ev.level || '').replace(/_/g, ' ')),
                ev.excerpt && ev.excerpt.trim() !== String(item.reply_excerpt || '').trim() ? h('span', { className: 'sp-ev-x' }, ev.excerpt) : null)))) : null),
          h('div', { className: 'sp-hot-side' },
            h('span', { className: 'sp-next-k', style: { color: `var(--sp-${rec.tone})` } }, 'Recommended'),
            h('strong', { style: { fontSize: 14 } }, rec.t),
            h('p', { className: 'sp-muted sp-small', style: { margin: 0 } }, rec.b),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: 6, marginTop: 'auto' } },
              h('button', { type: 'button', className: 'sp-btn sp-btn-primary', onClick: () => askHermes(PROMPTS.reply({ company: item.company || item.email, id: item.lead_id }), notify) }, icon('reply'), 'Draft reply with Hermes'),
              h('button', { type: 'button', className: 'sp-btn', onClick: () => openCustomer(item.lead_id) }, 'Open customer'))))
      }))
}

// ---------------------------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------------------------

const MAIL_STATE = {
  not_configured: ['Not connected', 'neutral'],
  missing_credentials: ['Needs credentials', 'amber'],
  unverified: ['Not tested', 'amber'],
  connected: ['Connected', 'green'],
  failed: ['Connection failed', 'red']
}

const EMPTY_ICP = { status: 'missing', industries: [], locations: [], buyer_roles: [], issues: [] }

function safeIcp(data) {
  const raw = data && data.icp && typeof data.icp === 'object' ? data.icp : {}
  return {
    ...EMPTY_ICP,
    ...raw,
    industries: Array.isArray(raw.industries) ? raw.industries : [],
    locations: Array.isArray(raw.locations) ? raw.locations : [],
    buyer_roles: Array.isArray(raw.buyer_roles) ? raw.buyer_roles : [],
    issues: Array.isArray(raw.issues) ? raw.issues : []
  }
}

function ChipInput({ label, values, onChange, placeholder, hint }) {
  const [draft, setDraft] = useState('')
  const list = Array.isArray(values) ? values : []
  const add = raw => {
    const parts = String(raw).split(',').map(s => s.trim()).filter(Boolean)
    if (!parts.length) return
    onChange(list.concat(parts.filter(p => !list.some(v => v.toLowerCase() === p.toLowerCase()))))
    setDraft('')
  }
  return h('label', { className: 'sp-field' },
    h('span', null, label),
    h('div', { className: 'sp-chips' },
      list.map(value => h('span', { key: value, className: 'sp-chip' }, value,
        h('button', { type: 'button', 'aria-label': `Remove ${value}`, onClick: e => { e.preventDefault(); onChange(list.filter(v => v !== value)) } }, icon('x')))),
      h('input', { 'aria-label': label, value: draft, placeholder: list.length ? '' : placeholder,
        onChange: e => { if (e.target.value.includes(',')) add(e.target.value); else setDraft(e.target.value) },
        onKeyDown: e => {
          if (e.key === 'Enter') { e.preventDefault(); add(draft) }
          if (e.key === 'Backspace' && !draft && list.length) onChange(list.slice(0, -1))
        },
        onBlur: () => add(draft) })),
    hint ? h('small', null, hint) : null)
}

function Card({ id, title, desc, aside, children, footer }) {
  return h('section', { id, className: 'sp-card' },
    h('div', { key: 'h', className: 'sp-card-h' }, h('div', null, h('h2', null, title), desc ? h('p', null, desc) : null), aside || null),
    h('div', { key: 'b', className: 'sp-card-b' }, children),
    footer ? h('div', { key: 'f', className: 'sp-card-f' }, footer) : null)
}

function Field({ label, hint, children }) {
  return h('label', { className: 'sp-field' }, h('span', null, label), children, hint ? h('small', null, hint) : null)
}

const SETTINGS_NAV = [['sp-set-brand', 'Brand'], ['sp-set-email', 'Email sending'], ['sp-set-icp', 'Ideal customer'], ['sp-set-follow', 'Follow-up'], ['sp-set-inbox', 'Reply tracking'], ['sp-set-cap', 'What works today'], ['sp-set-about', 'About']]

// Three honest states: works now, works once you set it up, not supported. Never a promise.
function capabilities(mail, imap) {
  const sending = mail.connection === 'connected' ? ['Ready', 'green', 'Each email still needs your confirmation in Hermes chat.']
    : mail.research_only ? ['Off', 'neutral', 'Research-only mode is on. Nothing can be sent.']
      : mail.connection === 'unverified' ? ['Untested', 'amber', 'Login saved. Run Test connection once; it sends nothing.']
      : mail.configured ? ['Set up', 'amber', 'Add the mailbox password in Hermes plugin settings, then test the connection.']
        : ['Set up', 'amber', 'Fill in Email sending above.']
  return [
    ['Import customers (CSV)', 'Works', 'green', 'Duplicates are skipped. From Excel, save as CSV first.'],
    ['Find leads with Hermes', 'Works', 'green', 'Runs in Hermes chat with web search. Only quoted, public evidence is saved.'],
    ['Draft first emails', 'Works', 'green', 'Written from your offer and the quoted evidence.'],
    ['Send after approval', sending[0], sending[1], sending[2]],
    ['Reply tracking', imap.configured ? 'On' : 'Set up', imap.configured ? 'green' : 'amber', imap.configured ? 'Replies are matched to the emails you sent.' : 'Add your incoming server under Reply tracking.'],
    ['Follow-up reminders', 'Works', 'green', 'Marked due on your rhythm. Never sent automatically.'],
    ['Separate mailbox per brand', 'Not yet', 'neutral', 'Hermes holds one mailbox login per profile.'],
    ['Automatic sending', 'Never', 'neutral', 'By design. A person approves every email.']
  ]
}

function SettingsView(props) {
  const setup = (props.data && props.data.setup) || {}
  return h(Setup, { ...props, data: setup })
}

function Setup({ data, setSection, brands, switchBrand, notify, refresh, anchor }) {
  const saved = data && data.business ? data.business : {}
  const mail = data && data.mail ? data.mail : {}
  // Read the ICP BEFORE the state initializer that consumes it: `const` bindings are in the
  // temporal dead zone until their declaration runs, so referencing `icp` further down threw
  // "Cannot access 'icp' before initialization" and crashed the whole Settings pane.
  const icp = safeIcp(data)
  const policy = (data && data.followup_policy) || {}
  const imap = (data && data.imap) || {}
  const defaults = mail.settings_defaults || {}
  const say = notify || (() => {})
  const [form, setForm] = useState({
    website: saved.website || '',
    products: saved.products || '',
    target_market: saved.target_market || '',
    host: mail.host || defaults.host || '',
    port: mail.port || defaults.port || 587,
    security: mail.security || defaults.security || 'starttls',
    from_address: mail.from_address || defaults.from_address || '',
    from_name: mail.from_name || defaults.from_name || '',
    signature: '',
    days: policy.days || 3,
    max_attempts: policy.max_attempts || 3,
    cold_days: policy.cold_days || 21,
    imap_host: imap.host || '',
    imap_port: imap.port || 993,
    imap_username: imap.username || ''
  })
  const [icpForm, setIcpForm] = useState({ industries: icp.industries, locations: icp.locations, buyer_roles: icp.buyer_roles })
  const [busy, setBusy] = useState('')
  useEffect(() => {
    setForm(current => ({
      ...current,
      website: saved.website || '',
      products: saved.products || '',
      target_market: saved.target_market || '',
      host: mail.host || current.host,
      port: mail.port || current.port,
      security: mail.security || current.security,
      from_address: mail.from_address || current.from_address,
      from_name: mail.from_name || current.from_name,
      days: policy.days || current.days,
      max_attempts: policy.max_attempts || current.max_attempts,
      cold_days: policy.cold_days || current.cold_days,
      imap_host: imap.host || current.imap_host,
      imap_port: imap.port || current.imap_port,
      imap_username: imap.username || current.imap_username
    }))
    setIcpForm({ industries: icp.industries, locations: icp.locations, buyer_roles: icp.buyer_roles })
  }, [data && data.business_id])
  const set = key => event => setForm(current => ({ ...current, [key]: event.target.value }))
  useEffect(() => {
    if (!anchor || typeof document === 'undefined' || typeof window === 'undefined') return undefined
    const timer = window.setTimeout(() => {
      const node = document.getElementById(anchor)
      if (node && node.scrollIntoView) node.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 60)
    return () => window.clearTimeout && window.clearTimeout(timer)
  }, [anchor, data && data.business_id])

  const post = (path, body, success, key) => {
    if (!rest) { say('Backend route is not bound.', 'err'); return Promise.resolve(null) }
    setBusy(key)
    return rest(path, { method: 'POST', body: { business_id: data && data.business_id, ...body } })
      .then(result => {
        if (!result || result.ok === false || (result.check && result.check.ok === false && key !== 'check')) {
          say(errText(result, 'That did not save.'), 'err')
          return result
        }
        if (key === 'check') {
          const ok = result.check ? result.check.ok : result.mail && result.mail.last_check && result.mail.last_check.ok
          say(ok ? 'Connection works. No email was sent.' : `Connection failed${result.check && result.check.code ? `: ${String(result.check.code).replace(/_/g, ' ')}` : ''}. No email was sent.`, ok ? 'ok' : 'err')
        } else say(success)
        if (refresh) refresh()
        return result
      })
      .catch(err => { say(err && err.message ? err.message : 'That did not save.', 'err'); return null })
      .finally(() => setBusy(''))
  }

  if (!data || data.ok === false) return h('div', { className: 'sp-page' }, h(Empty, { iconName: 'alert', title: 'Settings unavailable', body: data && data.error ? data.error : 'The setup route did not answer.' }))

  const list = (brands && brands.brands) || []
  const active = brands && brands.active
  const [stateLabel, stateTone] = MAIL_STATE[mail.connection] || MAIL_STATE.not_configured
  const last = mail.last_check || {}
  const go = id => {
    if (typeof document === 'undefined') return
    const node = document.getElementById(id)
    if (node && node.scrollIntoView) node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const icpTone = icp.status === 'configured' ? 'green' : icp.status === 'needs_configuration' ? 'amber' : 'neutral'
  const icpLabel = icp.status === 'configured' ? 'Configured' : icp.status === 'needs_configuration' ? 'Needs attention' : 'Not set'

  return h('div', { className: 'sp-page' },
    h('div', { key: 'head', className: 'sp-head' }, h('div', null, h('h1', { className: 'sp-h1' }, 'Settings'),
      h('p', { className: 'sp-sub' }, `Everything here applies to ${(active && active.display_name) || saved.name || 'the active brand'}.`))),
    h('div', { key: 'grid', className: 'sp-settings' },
      h('nav', { className: 'sp-snav', 'aria-label': 'Settings sections' },
        SETTINGS_NAV.map(([id, label]) => h('button', { key: id, type: 'button', onClick: () => go(id) }, label,
          id === 'sp-set-email' ? h('span', { className: 'sp-dot', style: { '--tone': `var(--sp-${stateTone === 'neutral' ? 'line' : stateTone})` } }) :
            id === 'sp-set-icp' ? h('span', { className: 'sp-dot', style: { '--tone': `var(--sp-${icpTone === 'neutral' ? 'line' : icpTone})` } }) : null))),
      h('div', { className: 'sp-sections' },
        h(Card, { key: 'brand', id: 'sp-set-brand', title: 'Brand', desc: 'Each brand keeps its own customers, sender and profile.',
          children: [
            list.length ? h('div', { key: 'list', className: 'sp-brands', role: 'radiogroup', 'aria-label': 'Active brand' },
              list.map(item => h('button', { key: item.id, type: 'button', role: 'radio', className: 'sp-brand-row', 'aria-checked': !!(active && active.id === item.id), onClick: () => switchBrand && active && active.id !== item.id && switchBrand(item.id) },
                h('span', { className: 'sp-radio' }), h('span', { className: 'sp-avatar' }, initials(item.display_name)),
                h('span', { className: 'sp-strong', style: { flex: 1 } }, item.display_name),
                active && active.id === item.id ? h('span', { className: 'sp-small sp-muted' }, 'Active') : null))) : null,
            h('div', { key: 'f', className: 'sp-grid2' },
              h(Field, { label: 'Brand name', hint: 'To add another brand, ask Hermes in chat.', children: h('input', { className: 'sp-input', readOnly: true, value: saved.name || '', 'aria-label': 'Brand name' }) }),
              h(Field, { label: 'Website', children: h('input', { className: 'sp-input', value: form.website, onChange: set('website'), placeholder: 'https://', 'aria-label': 'Website' }) })),
            h(Field, { key: 'p', label: 'What you sell', children: h('textarea', { className: 'sp-textarea', value: form.products, onChange: set('products'), placeholder: 'Your products or services, in one or two sentences', 'aria-label': 'Products' }) }),
            h(Field, { key: 'm', label: 'Who you sell to', hint: 'Discovery searches for this market.', children: h('input', { className: 'sp-input', value: form.target_market, onChange: set('target_market'), placeholder: 'e.g. Logistics companies in Jakarta', 'aria-label': 'Target market' }) })],
          footer: [h('span', { key: 's', className: 'sp-small sp-muted' }, `Applies to ${saved.name || 'this brand'} only.`),
            h('button', { key: 'b', type: 'button', className: 'sp-btn sp-btn-primary', disabled: busy === 'business' || !saved.name, onClick: () => post('/setup', { action: 'business', name: saved.name, website: form.website, products: form.products, target_market: form.target_market }, 'Brand profile saved.', 'business') }, busy === 'business' ? 'Saving…' : 'Save brand')] }),
        h(Card, { key: 'email', id: 'sp-set-email', title: 'Email sending', desc: 'SalesPilot sends from your own mailbox, one approved email at a time. Your provider lists these settings under “SMTP”.',
          aside: h('span', { className: `sp-pill tone-${stateTone}` }, stateLabel),
          children: [
            h('div', { key: 'g1', className: 'sp-grid3' },
              h(Field, { label: 'Outgoing server (SMTP)', hint: 'e.g. smtp.gmail.com', children: h('input', { className: 'sp-input', value: form.host, onChange: set('host'), placeholder: 'smtp.yourdomain.com', 'aria-label': 'SMTP host' }) }),
              h(Field, { label: 'Port', children: h('input', { className: 'sp-input', inputMode: 'numeric', value: String(form.port), onChange: set('port'), 'aria-label': 'SMTP port' }) }),
              h(Field, { label: 'Security', children: h('div', { className: 'sp-seg', role: 'group', 'aria-label': 'SMTP security' },
                [['starttls', 'STARTTLS'], ['tls', 'SSL/TLS']].map(([id, label]) => h('button', { key: id, type: 'button', 'aria-pressed': form.security === id, onClick: () => setForm(c => ({ ...c, security: id, port: id === 'tls' && Number(c.port) === 587 ? 465 : id === 'starttls' && Number(c.port) === 465 ? 587 : c.port })) }, label))) })),
            h('div', { key: 'g2', className: 'sp-grid2' },
              h(Field, { label: 'Sender name', children: h('input', { className: 'sp-input', value: form.from_name, onChange: set('from_name'), placeholder: 'Your name', 'aria-label': 'Sender name' }) }),
              h(Field, { label: 'Sender email', hint: 'Must match the mailbox you sign in with.', children: h('input', { className: 'sp-input', value: form.from_address, onChange: set('from_address'), placeholder: 'you@yourdomain.com', 'aria-label': 'Sender email' }) })),
            h(Field, { key: 'sig', label: 'Signature', hint: mail.signature_present ? 'A signature is saved. Type a new one to replace it.' : 'Added in plain text below every approved email.', children: h('textarea', { className: 'sp-textarea', value: form.signature, onChange: set('signature'), placeholder: 'Best regards,\nYour name', 'aria-label': 'Signature', style: { minHeight: 64 } }) }),
            (data.accounts || []).length ? h('div', { key: 'acc', className: 'sp-field' }, h('span', null, `Sender accounts · ${(data.accounts || []).length}`),
              h('div', { className: 'sp-senders' }, (data.accounts || []).map(acc => h('div', { key: acc.id },
                h('span', { className: 'sp-avatar' }, initials(acc.display_name || acc.address)),
                h('span', { className: 'sp-cell-stack', style: { flex: 1 } }, h('span', { className: 'sp-strong' }, acc.display_name || acc.address), h('span', { className: 'sp-muted sp-small' }, acc.address)),
                h('span', { className: `sp-pill tone-${acc.status === 'active' ? 'green' : 'neutral'}` }, acc.status || 'saved')))),
              h('small', null, 'Hermes keeps one mailbox login per profile, so every brand sends through it. Separate mailboxes per brand are not supported yet.')) : null,
            h('div', { key: 'cred', className: `sp-callout ${mail.username_present && mail.password_present ? '' : 'sp-callout-warn'}` }, icon(mail.username_present && mail.password_present ? 'info' : 'alert'),
              h('span', null, mail.username_present && mail.password_present ? 'Mailbox username and password are stored in Hermes credentials.' : `Add your mailbox username and password in ${(mail.native_path || ['Capabilities', 'Plugins', 'SalesPilot', 'Settings']).join(' → ')}. SalesPilot never stores or shows them.`)),
            h('p', { key: 'last', className: 'sp-small sp-muted', style: { margin: 0 } }, last.ran ? `Last test ${last.ok ? 'succeeded' : 'failed'} ${ago(last.at)}${last.code && !last.ok ? ` · ${String(last.code).replace(/_/g, ' ')}` : ''}. Tests never send email.` : 'Not tested yet. A test signs in once and sends nothing.')],
          footer: [
            h('button', { key: 'r', type: 'button', className: 'sp-btn sp-btn-ghost sp-btn-sm', disabled: !!busy, onClick: () => post('/setup', { action: 'skip_mail' }, 'Research-only mode on. Nothing can be sent.', 'skip') }, mail.research_only ? 'Research-only mode is on' : 'Use research-only mode'),
            h('div', { key: 'b', className: 'sp-row' },
              h('button', { type: 'button', className: 'sp-btn', disabled: !!busy || !mail.configured, onClick: () => post('/setup', { action: 'check' }, '', 'check') }, busy === 'check' ? 'Testing…' : 'Test connection'),
              h('button', { type: 'button', className: 'sp-btn sp-btn-primary', disabled: !!busy, onClick: () => post('/setup', { action: 'mail', host: form.host, port: form.port, security: form.security, from_address: form.from_address, from_name: form.from_name, signature: form.signature }, 'Sender saved.', 'mail') }, busy === 'mail' ? 'Saving…' : 'Save sender'))] }),
        h(Card, { key: 'icp', id: 'sp-set-icp', title: 'Ideal customer profile', desc: 'Companies are only marked a fit when they match these. Press Enter after each value.',
          aside: h('span', { className: `sp-pill tone-${icpTone}` }, icpLabel),
          children: [
            h(ChipInput, { key: 'i', label: 'Industries', values: icpForm.industries, onChange: v => setIcpForm(c => ({ ...c, industries: v })), placeholder: 'e.g. logistics, hospitality' }),
            h(ChipInput, { key: 'l', label: 'Locations', values: icpForm.locations, onChange: v => setIcpForm(c => ({ ...c, locations: v })), placeholder: 'e.g. Jakarta, Bali' }),
            h(ChipInput, { key: 'r', label: 'Buyer roles', values: icpForm.buyer_roles, onChange: v => setIcpForm(c => ({ ...c, buyer_roles: v })), placeholder: 'e.g. Fleet Manager, Procurement' }),
            icp.status === 'needs_configuration' && icp.issues.length ? h('div', { key: 'w', className: 'sp-callout sp-callout-warn' }, icon('alert'), h('span', null, 'Keep industries, places and job titles in their own fields. ', icp.issues.slice(0, 2).map(s => s.replace(/_/g, ' ').replace(':', ': ')).join(' · '))) : null],
          footer: [h('span', { key: 's', className: 'sp-small sp-muted' }, `${icp.industries.length} industries · ${icp.locations.length} locations · ${icp.buyer_roles.length} roles saved`),
            h('button', { key: 'b', type: 'button', className: 'sp-btn sp-btn-primary', disabled: busy === 'icp', onClick: () => post('/setup', { action: 'icp', industries: icpForm.industries, locations: icpForm.locations, buyer_roles: icpForm.buyer_roles }, 'Ideal customer profile saved.', 'icp') }, busy === 'icp' ? 'Saving…' : 'Save profile')] }),
        h(Card, { key: 'follow', id: 'sp-set-follow', title: 'Follow-up rhythm', desc: 'When a customer has not replied, SalesPilot marks a follow-up as due. It never sends one on its own.',
          children: h('div', { className: 'sp-grid3' },
            h(Field, { key: 'd', label: 'Follow up after', hint: 'days without a reply', children: h('input', { className: 'sp-input', type: 'number', min: 1, max: 60, value: form.days, onChange: set('days'), 'aria-label': 'Follow-up days' }) }),
            h(Field, { key: 'm', label: 'Stop after', hint: 'emails in total', children: h('input', { className: 'sp-input', type: 'number', min: 1, max: 10, value: form.max_attempts, onChange: set('max_attempts'), 'aria-label': 'Max attempts' }) }),
            h(Field, { key: 'c', label: 'Mark cold after', hint: 'days of silence', children: h('input', { className: 'sp-input', type: 'number', min: 1, max: 365, value: form.cold_days, onChange: set('cold_days'), 'aria-label': 'Cold after days' }) })),
          footer: [h('span', { key: 's' }), h('button', { key: 'b', type: 'button', className: 'sp-btn sp-btn-primary', disabled: busy === 'policy', onClick: () => post('/policy', { days: Number(form.days), max_attempts: Number(form.max_attempts), cold_days: Number(form.cold_days) }, 'Follow-up rhythm saved.', 'policy') }, busy === 'policy' ? 'Saving…' : 'Save rhythm')] }),
        h(Card, { key: 'inbox', id: 'sp-set-inbox', title: 'Reply tracking', desc: 'SalesPilot reads your inbox (IMAP) to match replies to emails it sent. A reply only counts when it answers one of those emails. Nothing is deleted or marked read.',
          aside: h('span', { className: `sp-pill tone-${imap.configured ? 'green' : 'neutral'}` }, imap.configured ? 'On' : 'Off'),
          children: [
            h('div', { key: 'g', className: 'sp-grid3' },
              h(Field, { label: 'Incoming server (IMAP)', hint: 'e.g. imap.gmail.com', children: h('input', { className: 'sp-input', value: form.imap_host, onChange: set('imap_host'), placeholder: 'imap.yourdomain.com', 'aria-label': 'IMAP host' }) }),
              h(Field, { label: 'Port', children: h('input', { className: 'sp-input', inputMode: 'numeric', value: String(form.imap_port), onChange: set('imap_port'), 'aria-label': 'IMAP port' }) }),
              h(Field, { label: 'Username', children: h('input', { className: 'sp-input', value: form.imap_username, onChange: set('imap_username'), placeholder: 'you@yourdomain.com', 'aria-label': 'IMAP username' }) })),
            h('p', { key: 's', className: 'sp-small sp-muted', style: { margin: 0 } }, imap.configured ? `Last checked ${imap.last_sync_at ? ago(imap.last_sync_at) : 'never'} · ${imap.review_count || 0} message(s) need review. Uses the same mailbox password as sending.` : 'Uses the same mailbox password stored in Hermes credentials.')],
          footer: [
            h('button', { key: 'c', type: 'button', className: 'sp-btn sp-btn-sm', disabled: !!busy || !imap.configured, onClick: () => post('/inbox', { action: 'sync' }, 'Inbox checked.', 'sync') }, icon('refresh'), busy === 'sync' ? 'Checking…' : 'Check inbox now'),
            h('button', { key: 'b', type: 'button', className: 'sp-btn sp-btn-primary', disabled: !!busy || !form.imap_host || !form.imap_username, onClick: () => post('/imap', { host: form.imap_host.trim(), port: Number(form.imap_port) || 993, username: form.imap_username.trim() }, 'Reply tracking saved.', 'imap') }, busy === 'imap' ? 'Saving…' : 'Save')] }),
        h(Card, { key: 'cap', id: 'sp-set-cap', title: 'What works today', desc: 'Live status for this brand. Anything not listed as working is not offered in the app.',
          children: h('ul', { className: 'sp-caps' }, capabilities(mail, imap).map(([label, state, tone, note]) => h('li', { key: label },
            h('span', { className: 'sp-strong' }, label),
            h('span', { className: `sp-pill tone-${tone}` }, state),
            h('span', { className: 'sp-small sp-muted' }, note)))) }),
        h(Card, { key: 'about', id: 'sp-set-about', title: 'About SalesPilot', desc: `Created by ROCK · Version ${VERSION} · Built for Hermes Agent. Not affiliated with Nous Research. MIT License.`,
          children: h('div', { className: 'sp-row' },
            h('a', { href: GITHUB, target: '_blank', rel: 'noreferrer', className: 'sp-small' }, 'github.com/ranggaoscar'),
            h('span', { className: 'sp-faint sp-small' }, '·'),
            h('span', { className: 'sp-small sp-muted' }, 'Email only leaves through ', h('span', { className: 'sp-kbd' }, '/salespilot-send'), ' after you confirm in Hermes.')) }))))
}

// The host disposes and re-runs register() when it rescans desktop-plugins, so the guard is per
// REGISTRATION CYCLE, never a one-shot flag: a boolean "already registered" would leave the plugin
// unregistered for good (no page, no sidebar row) after the first reload. Same ctx twice is a
// no-op; a new cycle after dispose registers cleanly.
let activeCycle = null
let cycleDisposers = []

function disposeCycle() {
  const pending = cycleDisposers
  cycleDisposers = []
  activeCycle = null
  for (const dispose of pending) {
    try {
      dispose()
    } catch {
      // A contribution the host already tore down must not break the reload.
    }
  }
}

export default {
  id: 'hermes-salespilot',
  name: 'SalesPilot',
  description: 'AI sales CRM for Hermes: collect customers, prepare outreach, send after approval, track replies.',
  defaultEnabled: false,
  register(ctx) {
    if (!ctx || typeof ctx.register !== 'function') return () => {}
    // Same registration cycle called twice (the host may re-invoke register without a dispose):
    // keep the first cycle, add nothing.
    if (activeCycle === ctx) return disposeCycle
    if (activeCycle !== null) disposeCycle()

    activeCycle = ctx
    rest = ctx.rest
    osApi = ctx.os || null
    cycleDisposers = []
    const keep = disposer => {
      if (typeof disposer === 'function') cycleDisposers.push(disposer)
    }

    keep(ctx.register({
      id: 'page',
      area: ROUTES_AREA,
      // A stable title: without it the pane title flips from the humanized path to the plugin label
      // after a reload, which re-registers the pane and re-fronts it.
      title: 'SalesPilot',
      data: { path: '/salespilot' },
      render: () => jsx(Page, {})
    }))
    keep(ctx.register({
      id: 'nav',
      area: SIDEBAR_NAV_AREA,
      order: 60,
      data: { codicon: 'compass', label: 'SalesPilot', path: '/salespilot' }
    }))

    return disposeCycle
  }
}

// Test seam: the desktop bundle exports one default object to the host; these named exports are
// inert for the host and let the lifecycle tests render the real components.
export const __components = { Page, Setup, Select, BrandSwitch, safeIcp, EMPTY_ICP, stageOf, csvHeader, guessMapping, CustomersView, HotView, Today, Checklist, errText, capabilities, Mark }
export const __state = () => ({ cycleActive: activeCycle !== null, disposers: cycleDisposers.length })
