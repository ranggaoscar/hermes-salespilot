# Screenshots

Every image in `v1.1/` is a **synthetic fixture**. The companies, people, addresses and replies are
fictional and use reserved `.test` / `.invalid` domains. No real customer, email history, credential
or database appears in any public image.

How they were made: a throwaway SalesPilot data directory was built with the plugin's own functions
(`tools.onboard_business`, `tools.qualify_lead`, `desk_actions.draft`, `desk_actions.import_csv`,
`inbox.record_message` / `inbox.apply_reply` for simulated sends and replies). The page is the real
`desktop/plugin.js` served by the real `dashboard/plugin_api.py`. No SMTP or IMAP connection was
opened. The demo mailbox login was stubbed in the preview process only, so the sender reads as
"saved, not tested".

| File | Shows |
| --- | --- |
| `v1.1/01-customers.png` | Customers: Today queue, six-step journey, table with Emailed / Replied / Next step |
| `v1.1/02-approve-drawer.png` | A drafted customer at step 3, Approve — "Send with approval" opens Hermes chat |
| `v1.1/03-replied-drawer.png` | A customer who replied with interest, quoted in the drawer |
| `v1.1/04-hot-prospects.png` | Hot Prospects: reply as proof, heat, recommended next step |
| `v1.1/05-import.png` | CSV import with column mapping, list origin and permission checkbox |
| `v1.1/06-settings.png` | Settings: brand switch and profile |
| `v1.1/07-what-works-today.png` | Live capability list: Works / Set up / Untested / Not yet / Never |
| `v1.1/08-dark.png` | Customers in the dark theme |
| `v1.1/09-narrow.png` | Narrow window (390 px) |

Do not replace these with captures of a live database. If a real capture is needed as acceptance
evidence, keep it out of the published tree.
