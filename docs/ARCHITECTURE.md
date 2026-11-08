# Architecture

SalesPilot stays one native plugin. The mission tool stores quoted DNA and dated signals. Sending still happens only from `/salespilot-send` after `ask_choice`.

```text
authorized URL
  -> assess_url (scheme, userinfo, IDN, DNS, private/metadata/CGNAT)
  -> pin first public IP, refuse proxy env, dial that IP
  -> Host header and TLS SNI stay the original hostname
  -> reassess every redirect
  -> extract_business / discover_companies (quotes only)
  -> SQLite under plugin_data_dir
  -> draft / follow-up / host approval ledger
  -> adapter.send always returns sending_disabled
```

Hermes `web_search` is optional and only through `ctx.dispatch_tool`. A search miss or an empty result creates no companies. SMTP names are read with `agent.secret_scope.get_secret` and only as booleans.

State is profile-scoped because `plugin_data_dir` follows `HERMES_HOME`. Approve and reject call `ctx.ask_choice` and require `ctx.session_surface()` to be `cli`, `tui`, or `desktop`. A model-supplied boolean is not authorization. The ledger stores business, lead, action, and draft revision. A mismatched revision is stale and is not reused.

Loopback is blocked in the tool. `fetch.allow_loopback_for_tests` is a process-local test seam. It is not a tool argument.
