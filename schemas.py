"""Tool schemas — what the model sees. Names must match plugin.yaml provides_tools."""

from __future__ import annotations

_OBJECT = "object"


def _obj(properties: dict, required: list[str]) -> dict:
    return {"type": _OBJECT, "properties": properties, "required": required}


def _str(description: str) -> dict:
    return {"type": "string", "description": description}


def _bool(description: str) -> dict:
    return {"type": "boolean", "description": description}


def _int(description: str) -> dict:
    return {"type": "integer", "description": description}


ONBOARD = {
    "name": "salespilot_onboard_business",
    "description": (
        "Save the active business profile for SalesPilot: offer, ICP, channels, "
        "one default CTA, and follow-up cadence. Call this before import, qualification, "
        "or drafts. Does not send messages or read credentials."
    ),
    "parameters": _obj(
        {
            "name": _str("Business name."),
            "offer": _str("What the business actually sells, in one concrete paragraph."),
            "offer_short": _str("Offer in 12 words or fewer, used in draft subjects."),
            "default_cta": _str("Operator CTA. One action. Not taken from website text."),
            "authorized": _bool("Required true before website text or a public URL may be read."),
            "authorization_note": _str("Who authorized the website text. No secrets."),
            "url": _str("Authorized public http(s) business URL. Fetched with SSRF checks. Not a private host."),
            "sender_name": _str("Operator sender name for drafts. Not a secret."),
            "sender_role": _str("Operator role shown in the signature."),
            "signature": _str("Operator signature line. Not a secret."),
            "sources": {
                "type": "array",
                "description": "Authorized pages: url, text, permitted=true. Claims are quoted from text. Not fetched.",
                "items": {"type": "object"},
            },
            "segments": {"type": "array", "items": {"type": "string"}, "description": "ICP segments, e.g. architect, contractor."},
            "geos": {"type": "array", "items": {"type": "string"}, "description": "ICP geos. Empty means no geo gate."},
            "exclude": {"type": "array", "items": {"type": "string"}, "description": "Competitor or do-not-contact phrases."},
            "channels": {"type": "array", "items": {"type": "string"}, "description": "Allowed draft channels: email, whatsapp."},
            "constraints": {"type": "array", "items": {"type": "string"}, "description": "Operating constraints. approval_required is always applied."},
            "currency": _str("Currency code. Default USD."),
            "locale": _str("Locale tag. Default en."),
            "default_country": _str("Phone country, e.g. ID. Empty uses generic E.164 length checks."),
            "followup_days": _int("Days before a waiting follow-up is due again. Default 3."),
            "research_only": _bool("True keeps the business in research mode and does not require email."),
            "mail_mode": _str("none, smtp, or gmail_oauth. Gmail OAuth stores no token in this host."),
            "target_market": _str("Target market note. Not a contact list."),
            "discovery_query": _str("Preferred public search phrase. Does not run by itself."),
        },
        ["name", "offer", "offer_short", "default_cta"],
    ),
}

IMPORT = {
    "name": "salespilot_import_customers",
    "description": (
        "Import customers from an authorized CSV or from synthetic JSON records. "
        "CSV needs mapping, authorization, and a source label. Dedupes on company, email, and phone. "
        "Does not contact anyone."
    ),
    "parameters": _obj(
        {
            "business_id": _str("Optional business id. Defaults to the active profile."),
            "seed_demo": _bool("True loads the bundled fictional demo business, customers, and prospects."),
            "source": _str("Source label required for a manual import, e.g. csv-upload."),
            "records": {
                "type": "array",
                "description": "JSON customer objects. Without authorized=true, each must set synthetic=true.",
                "items": {"type": "object"},
            },
            "csv_text": _str("Full CSV text, including the header. Not a filesystem path."),
            "mapping": {"type": "object", "description": "CSV header to company, contact_name, email, phone, segment, or notes."},
            "authorized": _bool("Required true for CSV import."),
            "authorization_note": _str("Who authorized this import. No secrets."),
            "synthetic": _bool("Mark the CSV batch as fictional test data."),
        },
        [],
    ),
}

QUALIFY = {
    "name": "salespilot_qualify_lead",
    "description": (
        "Qualify one B2B prospect against the active ICP. Requires company plus evidence. "
        "A format-valid phone is not WhatsApp registration. Missing facts become hold, never invented. "
        "Does not search the web and does not send."
    ),
    "parameters": _obj(
        {
            "business_id": _str("Optional business id. Defaults to the active profile."),
            "company": _str("Prospect company name."),
            "contact_name": _str("Public contact name, if the source names one."),
            "role": _str("Quoted role from the source. Do not guess."),
            "email": _str("Public email. Leave empty if unknown."),
            "phone": _str("Public phone. Leave empty if masked or unknown. Never guess digits."),
            "segment": _str("Segment such as architect, contractor, hospitality."),
            "country": _str("Geo label to match the ICP."),
            "source_url": _str("http(s) URL of the evidence. Not fetched by this tool."),
            "evidence": _str("What the source actually says. Required unless lead_id is set."),
            "unknowns": {"type": "array", "items": {"type": "string"}, "description": "Facts still missing."},
            "lead_id": _str("Researched lead to score from stored citations."),
            "source_text": _str("If set, evidence must be a quote from this text."),
        },
        [],
    ),
}

RESEARCH = {
    "name": "salespilot_research_opportunity",
    "description": (
        "Store a structured opportunity note. Separate verified claims, assumptions, and unknowns. "
        "This tool does not fetch pages. Pass only facts the caller already has, each verified claim with a source."
    ),
    "parameters": _obj(
        {
            "business_id": _str("Optional business id."),
            "lead_id": _str("Optional lead id this note belongs to."),
            "title": _str("Short opportunity title."),
            "verified": {
                "type": "array",
                "description": "Objects with claim and source. At least one verified claim or one unknown is required.",
                "items": {"type": "object"},
            },
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "unknowns": {"type": "array", "items": {"type": "string"}},
            "fit": _str("fit, weak, or unknown."),
            "sources": {
                "type": "array",
                "description": "Permitted public pages already in hand: url, text, permitted=true. Not fetched.",
                "items": {"type": "object"},
            },
            "discovery_url": _str("Authorized public directory URL to fetch. Companies must be quoted from the page."),
            "use_hermes_search": _bool("Ask Hermes web_search when dispatch is available. Never invents results."),
            "query": _str("Search query used only if use_hermes_search is true."),
            "authorized": _bool("Required true before a discovery URL is fetched."),
            "company": _str("Optional company hint. Must also appear in the source text."),
        },
        ["title"],
    ),
}

DRAFT = {
    "name": "salespilot_draft_outreach",
    "description": (
        "Build one personalized email or WhatsApp draft for a qualified lead. "
        "One CTA. Idempotent. Status stays draft. Sending is disabled in Phase 1."
    ),
    "parameters": _obj(
        {
            "business_id": _str("Optional business id."),
            "lead_id": _str("Qualified lead id."),
            "channel": _str("email or whatsapp."),
            "cta": _str("Optional CTA override. One action. Defaults to the business CTA."),
            "check_smtp": _bool("If true, report whether SMTP secret names are set. Values are never returned."),
        },
        ["lead_id", "channel"],
    ),
}

FOLLOWUP = {
    "name": "salespilot_plan_followups",
    "description": (
        "Recommend the next step for each lead: fill a gap, draft, request approval, wait, or hold. "
        "Never recommends sending. Replaces previous recommended rows for the business."
    ),
    "parameters": _obj(
        {
            "business_id": _str("Optional business id."),
        },
        [],
    ),
}

REPORT = {
    "name": "salespilot_report",
    "description": (
        "Produce a sales pipeline report from stored records: counts, decisions, drafts, "
        "approvals, and recommended follow-ups. Does not invent live metrics."
    ),
    "parameters": _obj(
        {
            "business_id": _str("Optional business id."),
            "section": _str("summary, pipeline, drafts, or approvals. Default summary."),
        },
        [],
    ),
}

APPROVAL = {
    "name": "salespilot_request_approval",
    "description": (
        "Record an approval-ledger transition for a draft: request, approve, or reject. "
        "Idempotent per draft. Approve does not send. Phase 1 adapters always return sending_disabled."
    ),
    "parameters": _obj(
        {
            "draft_id": _str("Draft id."),
            "decision": _str("request, approve, or reject."),
            "actor": _str("Who decided. Default operator."),
            "note": _str("Short reason. Do not include secrets."),
            "human_confirmed": _bool("Ignored. Approval comes from Hermes ask_choice on an attended surface, not from the model."),
            "business_id": _str("Optional. Must match the draft's business or the call is refused."),
            "lead_id": _str("Optional. Must match the draft's lead or the call is refused."),
        },
        ["draft_id", "decision"],
    ),
}

CONFIGURE = {
    "name": "salespilot_configure_mail",
    "description": (
        "Report SMTP status, check the operator-configured connection, or suppress one address. "
        "Cannot change transport or sender identity. Configure those in Hermes Settings or the Desktop wizard. Does not send email."
    ),
    "parameters": _obj(
        {
            "action": {"type": "string", "enum": ["check", "status", "suppress"], "description": "Default status."},
            "business_id": _str("Optional business id."),
            "email": _str("Address to suppress when action is suppress."),
            "reason": _str("Why the address is suppressed."),
        },
        [],
    ),
}

CONFIGURE["parameters"]["additionalProperties"] = False

MISSION = {
    "name": "salespilot_mission",
    "description": (
        "Save quoted business DNA, scan dated public signals, or resume a mission. "
        "Does not invent companies, contacts, or buying intent. Does not send."
    ),
    "parameters": _obj(
        {
            "action": _str("save_dna, scan, or resume."),
            "name": _str("Mission name. The same name resumes the saved graph."),
            "business_id": _str("Optional business id."),
            "url": _str("http(s) source URL when text is passed directly."),
            "text": _str("Permitted page text. Facts must be quoted from this text."),
            "permitted": _bool("Must be true for direct text. Default true."),
            "sources": {
                "type": "array",
                "description": "Permitted sources with url, text, and permitted=true.",
                "items": {"type": "object"},
            },
        },
        ["name"],
    ),
}

PIPELINE = {
    "name": "salespilot_pipeline",
    "description": (
        "List, discover, note, or change prospect lifecycle status. "
        "Does not send email. Does not invent contacts. SMTP acceptance is not a reply."
    ),
    "parameters": _obj(
        {
            "action": _str("list, discover, status, note, archive, delete, smtp_accepted, or reply."),
            "business_id": _str("Optional business id."),
            "lead_id": _str("Prospect id for a status, note, archive, or delete."),
            "status": _str("Lifecycle status. Not inferred from SMTP success."),
            "note": _str("Operator note. No secrets."),
            "query": _str("Search company, email, evidence, or note."),
            "sort": _str("updated, company, or status."),
            "include_archived": _bool("Include archived prospects in list."),
            "confirm_delete": _bool("Required true before a prospect is deleted."),
            "message_id": _str("SMTP or mailbox message id. Not proof of inbox delivery by itself."),
            "quote": _str("Quoted reply text. Required for a reply event."),
            "authorized": _bool("Required true before a reply observation is recorded."),
            "sources": {
                "type": "array",
                "description": "Permitted public pages with url, text, and permitted=true.",
                "items": {"type": "object"},
            },
        },
        ["action"],
    ),
}

TOOLS = (ONBOARD, IMPORT, QUALIFY, RESEARCH, DRAFT, FOLLOWUP, REPORT, APPROVAL, CONFIGURE, MISSION, PIPELINE)

# Every scoped tool accepts an explicit brand reference. `brand` wins over `business_id`, and
# omitting both means the active brand — never a silent guess at a different tenant.
_BRAND_PROPERTY = _str(
    "Brand name, slug, or id (for example 'Cedarline'). Takes precedence over business_id. "
    "Omit to use the active brand. An unknown name is refused, never mapped to another brand."
)
for _tool in TOOLS:
    _properties = _tool["parameters"].get("properties", {})
    if "business_id" in _properties:
        _properties.setdefault("brand", _BRAND_PROPERTY)

TOOL_NAMES = tuple(item["name"] for item in TOOLS)
