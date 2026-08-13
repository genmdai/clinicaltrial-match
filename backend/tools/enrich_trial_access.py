"""Bright Data enrichment: additional PUBLIC access information for a trial the
patient has already been matched to (contact/referral details, hospital and
sponsor pages, documents the site mentions needing) — never eligibility, never
a source of truth. ClinicalTrials.gov remains the source of truth for official
eligibility, recruiting status, official sites, and official contacts; this
module only adds what the registry doesn't carry: how to actually reach the
site and start the process.

Single entry point per the product spec: `enrich_trial_access(trial, site)`.

No PHI in, ever: the only inputs accepted are trial identity (NCT ID, title,
sponsor) and site identity (facility, city/state, optional hospital domain) —
modeled as `TrialEnrichmentInput`/`SiteEnrichmentInput` in schemas.py. Building
those Pydantic models from the caller's dicts is also the safety boundary:
Pydantic silently drops any extra keys (e.g. a caller accidentally passing
patient fields alongside trial/site), and nothing past that point ever touches
the raw input dicts again — only the validated, narrow models are threaded
through to the search queries and the LLM extraction prompts.

Flow: build a handful of targeted search queries -> Bright Data SERP search ->
rank/dedupe results (official hospital/sponsor domains first, ClinicalTrials.gov
itself excluded as redundant) -> scrape the top 3-5 pages via Bright Data's Web
Unlocker -> one LLM structured-extraction call per page (only pull facts
actually present in that page's text; null/empty when absent, never invented)
-> merge into one TrialAccessEnrichment, keeping the source URL that backed
each field. A Bright Data or LLM failure at any stage never raises into the
agent loop — a page that fails to scrape/extract is just skipped, and a total
failure returns a structured {"error": ...} the agent can treat as "no
enrichment available" without blocking the core trial result.
"""

import re
from urllib.parse import urlparse

from pydantic import BaseModel
from strands import Agent, tool

from ..schemas import (
    EnrichmentSource,
    HospitalTrialPage,
    SiteEnrichmentInput,
    TrialAccessEnrichment,
    TrialEnrichmentInput,
)
from . import _brightdata_client
from ._llm import get_model

MAX_PAGES = 5
MAX_PAGE_CHARS = 8000
CTGOV_HOST = "clinicaltrials.gov"
_HOSPITAL_HOST_HINTS = ("hospital", "health", "medicine", "medical", "clinic", "cancer", ".edu")
_DOMAIN_RANK = {"hospital": 0, "sponsor": 1, "other": 2}

SYSTEM_PROMPT = """You extract structured access/contact information about a specific \
clinical trial from ONE scraped web page's text. You will be given the trial's NCT ID, \
title, and the page's source URL and content.

Rules:
- Only extract a fact if it is EXPLICITLY present in the page text. Never infer, guess, \
or fill in typical/plausible values. Leave a field null (or an empty list) if the page \
doesn't state it.
- is_relevant: true only if the page is actually about this specific trial or the named \
recruiting site's research/trials program — not a generic hospital homepage with no \
trial-specific or research-office content, and not an unrelated result.
- trial_office_phone / trial_office_email: only phone/email specifically for a clinical \
trials office, research coordinator, or study contact — not a hospital's general \
switchboard number, unless that IS what's presented as the way to reach the trial team.
- physician_referral_required: true if the page says a physician referral is required or \
recommended, false if the page explicitly says patients can self-refer / no referral \
needed, null if the page doesn't address it at all.
- documents_mentioned: list ONLY documents the page explicitly says to bring/send/upload \
for referral or screening (e.g. "pathology report", "genomic/molecular testing results", \
"medical records", "imaging", "lab results", "treatment history", "referral form"). Do \
not list a document type unless the page names it.
- patient_resource_urls / sponsor_study_page_url: only URLs that are actually printed or \
linked in the page content for that purpose.
"""


class _PageExtraction(BaseModel):
    is_relevant: bool
    hospital_trial_page_title: str | None = None
    trial_office_name: str | None = None
    trial_office_phone: str | None = None
    trial_office_email: str | None = None
    contact_form_url: str | None = None
    referral_instructions: str | None = None
    physician_referral_required: bool | None = None
    referral_url: str | None = None
    documents_mentioned: list[str] = []
    sponsor_study_page_url: str | None = None
    patient_resource_urls: list[str] = []


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_queries(trial: TrialEnrichmentInput, site: SiteEnrichmentInput) -> list[str]:
    queries = [
        f'"{trial.nct_id}" "{site.facility}"',
        f'"{trial.title}" "{site.facility}"',
    ]
    if site.hospital_domain:
        queries.append(f"site:{site.hospital_domain} {trial.nct_id}")
    if trial.sponsor:
        queries.append(f'"{trial.nct_id}" "{trial.sponsor}"')
    return queries


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _domain_type(url: str, trial: TrialEnrichmentInput, site: SiteEnrichmentInput) -> str:
    host = _host(url)
    if site.hospital_domain and _normalize(site.hospital_domain) in _normalize(host):
        return "hospital"
    if any(hint in host for hint in _HOSPITAL_HOST_HINTS):
        return "hospital"
    if trial.sponsor and _normalize(trial.sponsor) and _normalize(trial.sponsor) in _normalize(host):
        return "sponsor"
    return "other"


def _rank_and_select(results: list[dict], trial: TrialEnrichmentInput, site: SiteEnrichmentInput, max_pages: int = MAX_PAGES) -> list[dict]:
    """Dedupe by URL, drop ClinicalTrials.gov itself (already the source of truth),
    and rank official hospital/sponsor domains ahead of everything else — stable
    sort so original search relevance order is preserved within each tier.
    """
    seen: set[str] = set()
    deduped = []
    for r in results:
        url = r.get("url")
        if not url or url in seen or CTGOV_HOST in _host(url):
            continue
        seen.add(url)
        deduped.append(r)
    deduped.sort(key=lambda r: _DOMAIN_RANK[_domain_type(r["url"], trial, site)])
    return deduped[:max_pages]


def _extract_page(trial: TrialEnrichmentInput, url: str, page_text: str) -> _PageExtraction:
    agent = Agent(model=get_model(), system_prompt=SYSTEM_PROMPT)
    prompt = (
        f"Trial: {trial.nct_id} — {trial.title}\n"
        f"Source URL: {url}\n\n"
        f"Page content:\n{page_text[:MAX_PAGE_CHARS]}"
    )
    result = agent(prompt, structured_output_model=_PageExtraction)
    if result.structured_output is None:
        raise ValueError("model returned no structured output")
    return result.structured_output


def _merge(pages: list[tuple[dict, _PageExtraction]], trial: TrialEnrichmentInput, site: SiteEnrichmentInput) -> TrialAccessEnrichment:
    out = TrialAccessEnrichment(trial_id=trial.nct_id, site=site.facility)
    sources: list[EnrichmentSource] = []

    for meta, ext in pages:
        if not ext.is_relevant:
            continue
        contributed = False

        if ext.hospital_trial_page_title and not out.hospital_trial_page.url:
            out.hospital_trial_page = HospitalTrialPage(url=meta["url"], title=ext.hospital_trial_page_title)
            contributed = True
        if ext.trial_office_name and not out.trial_office.name:
            out.trial_office.name = ext.trial_office_name
            contributed = True
        if ext.trial_office_phone and not out.trial_office.phone:
            out.trial_office.phone = ext.trial_office_phone
            contributed = True
        if ext.trial_office_email and not out.trial_office.email:
            out.trial_office.email = ext.trial_office_email
            contributed = True
        if ext.contact_form_url and not out.trial_office.contact_form:
            out.trial_office.contact_form = ext.contact_form_url
            contributed = True
        if ext.referral_instructions and not out.referral.instructions:
            out.referral.instructions = ext.referral_instructions
            contributed = True
        if ext.physician_referral_required is not None and out.referral.physician_referral_required is None:
            out.referral.physician_referral_required = ext.physician_referral_required
            contributed = True
        if ext.referral_url and not out.referral.url:
            out.referral.url = ext.referral_url
            contributed = True
        for doc in ext.documents_mentioned:
            if doc not in out.documents_mentioned:
                out.documents_mentioned.append(doc)
                contributed = True
        if ext.sponsor_study_page_url and not out.sponsor_study_page:
            out.sponsor_study_page = ext.sponsor_study_page_url
            contributed = True
        for resource_url in ext.patient_resource_urls:
            if resource_url not in out.patient_resources:
                out.patient_resources.append(resource_url)
                contributed = True

        if contributed:
            sources.append(EnrichmentSource(url=meta["url"], title=meta.get("title"), domain_type=meta["domain_type"]))

    out.sources = sources
    return out


@tool
def enrich_trial_access(trial: dict, site: dict, offline: bool = False) -> dict:
    """Enrich a matched trial/site with public access info via Bright Data web search + scrape.

    Call this AFTER a patient has selected a candidate trial (post
    check_eligibility/access_outlook) — this is supplementary access info, not
    part of the eligibility or matching pipeline, and CT.gov remains the
    source of truth for everything eligibility/recruiting-status related.

    Args:
        trial: {"nct_id": str, "title": str, "sponsor": str | None}. No patient
            data — trial identity only.
        site: {"facility": str, "city": str | None, "state": str | None,
            "hospital_domain": str | None}. No patient data — site identity only.
        offline: When true, only use the local fixtures/cache/ — never call
            Bright Data live. Also forced on by the OFFLINE=1 environment
            variable.

    Returns:
        {"enrichment": <TrialAccessEnrichment JSON>} on success — fields the
        source pages didn't confirm are left null/empty, never guessed. On a
        hard failure (bad input, missing Bright Data credentials, network
        error) returns {"error": "<message>"} — never raises into the agent
        loop, and the agent should treat that as "no enrichment available"
        rather than blocking the underlying trial result.
    """
    try:
        trial_in = TrialEnrichmentInput(**trial)
        site_in = SiteEnrichmentInput(**site)
    except Exception as e:  # noqa: BLE001 — bad input from the agent, not a Bright Data failure, but still must not raise
        return {"error": f"invalid input: {e}"}

    try:
        raw_results: list[dict] = []
        for query in _build_queries(trial_in, site_in):
            try:
                raw_results.extend(_brightdata_client.search(query, offline=offline))
            except Exception:  # noqa: BLE001, S112 — one bad query must not sink the others
                continue

        candidates = _rank_and_select(raw_results, trial_in, site_in)

        pages: list[tuple[dict, _PageExtraction]] = []
        for candidate in candidates:
            try:
                page_text = _brightdata_client.scrape(candidate["url"], offline=offline)
                extraction = _extract_page(trial_in, candidate["url"], page_text)
            except Exception:  # noqa: BLE001, S112 — one bad page must not sink the others
                continue
            meta = {
                "url": candidate["url"],
                "title": candidate.get("title"),
                "domain_type": _domain_type(candidate["url"], trial_in, site_in),
            }
            pages.append((meta, extraction))

        enrichment = _merge(pages, trial_in, site_in)
        return {"enrichment": enrichment.model_dump()}
    except Exception as e:  # noqa: BLE001 — tool boundary: Bright Data failure must never break the main agent
        return {"error": str(e)}
