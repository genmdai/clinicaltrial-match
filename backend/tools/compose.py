"""Draft outreach messages — compose only, NEVER send (CLAUDE.md P6). Pure
Python templating, not an LLM call: the draft can only ever contain confirmed
PatientProfile / trial fields, so there's no risk of the drafting step itself
inventing or speculating on anything. Every draft carries a fixed AI-disclosure
line and, for email, an optional `mailto:` link that only opens the user's own
mail client prefilled — still a human who clicks send.
"""

import urllib.parse

AI_DISCLOSURE = "Drafted with an AI assistant; please verify details."


def _subject_label(profile: dict) -> str:
    if profile.get("subject") == "relative":
        return f"my {profile.get('relation') or 'family member'}"
    return "myself"


def _background_lines(profile: dict) -> list[str]:
    lines = []
    if profile.get("age") is not None:
        lines.append(f"- Age: {profile['age']}")
    if profile.get("sex"):
        lines.append(f"- Sex: {profile['sex']}")
    condition = profile.get("condition") or profile.get("condition_raw")
    if condition:
        lines.append(f"- Condition: {condition}")
    for b in profile.get("biomarkers", []):
        lines.append(f"- Biomarker: {b}")
    for pt in profile.get("prior_treatments", []):
        drug = pt.get("drug_brand") or pt.get("drug_generic") or pt.get("raw_mention")
        cls = f" ({pt['drug_class']})" if pt.get("drug_class") else ""
        outcome = f" — {pt['outcome']}" if pt.get("outcome") else ""
        lines.append(f"- Prior treatment: {drug}{cls}{outcome}")
    if profile.get("ecog") is not None:
        lines.append(f"- ECOG performance status: {profile['ecog']}")
    for c in profile.get("comorbidities", []):
        lines.append(f"- Other medical history: {c}")
    return lines


def _match_summary_lines(verdicts: list[dict]) -> list[str]:
    passes = [v for v in verdicts if v["verdict"] == "PASS"]
    return [f"- {v['reason']}" for v in passes] or ["- (No criteria could be automatically confirmed yet.)"]


def _open_questions(verdicts: list[dict]) -> list[str]:
    return [v["follow_up_question"] for v in verdicts if v["verdict"] == "UNKNOWN" and v.get("follow_up_question")]


def _contact_line(contact: dict) -> str:
    parts = [p for p in [contact.get("name"), f"({contact['role']})" if contact.get("role") else None] if p]
    if contact.get("phone"):
        parts.append(f"— {contact['phone']}")
    if contact.get("email"):
        parts.append(f"— {contact['email']}")
    line = " ".join(parts)
    if contact.get("contact_source") == "sponsor_only" and contact.get("guidance"):
        line = f"{line} — {contact['guidance']}" if line else contact["guidance"]
    return line or "Not available — contact the trial site directly."


def _build_mailto(email: str, subject: str, body: str) -> str:
    params = urllib.parse.urlencode({"subject": subject, "body": body})
    return f"mailto:{email}?{params}"


def compose_email(profile: dict, nct_id: str, trial_title: str, verdicts: list[dict], contact: dict) -> dict:
    """Draft an email to the trial contact (P6: draft only, never sent).

    Args:
        profile: PatientProfile dict.
        nct_id: The trial's NCT identifier.
        trial_title: The trial's brief title.
        verdicts: CriterionVerdict dicts, from check_eligibility.
        contact: Contact dict, from fetch_trial.get_contact.

    Returns:
        {"subject", "body", "mailto"} on success ("mailto" is None if the
        contact has no email), or {"error": "<message>"} on failure.
    """
    try:
        condition = profile.get("condition") or profile.get("condition_raw") or "this condition"
        subject_label = _subject_label(profile)
        intro = (
            f"I am writing on behalf of {subject_label}" if profile.get("subject") == "relative"
            else "I am writing about my own case"
        )
        open_qs = _open_questions(verdicts)

        body_parts = [
            f"Dear {contact.get('name') or 'Trial Coordinator'},",
            "",
            f"{intro} regarding clinical trial {nct_id} ({trial_title}).",
            "",
            "Background:",
            *_background_lines(profile),
            "",
            "Based on the trial's published criteria, here is what appears to match so far:",
            *_match_summary_lines(verdicts),
        ]
        if open_qs:
            body_parts += [
                "",
                "A few things I'd like to confirm with your team before a pre-screening call:",
                *[f"- {q}" for q in open_qs],
            ]
        body_parts += [
            "",
            "Could we schedule a pre-screening call to discuss next steps?",
            "",
            "Thank you,",
            "",
            "---",
            AI_DISCLOSURE,
        ]
        body = "\n".join(body_parts)
        email_subject = f"Trial inquiry: {nct_id} — {condition}"
        mailto = _build_mailto(contact["email"], email_subject, body) if contact.get("email") else None

        return {"subject": email_subject, "body": body, "mailto": mailto}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}


def compose_doctor_note(
    profile: dict, nct_id: str, trial: dict, verdicts: list[dict], contact: dict,
    nearest_site: dict | None = None,
) -> dict:
    """Draft a one-pager the patient can hand their oncologist (P6: draft only).

    Args:
        profile: PatientProfile dict.
        nct_id: The trial's NCT identifier.
        trial: Raw study record dict, from fetch_trial (for title/phase).
        verdicts: CriterionVerdict dicts, from check_eligibility.
        contact: Contact dict, from fetch_trial.get_contact.
        nearest_site: Optional nearest-site dict (with "facility"/"distance_mi"),
            from geo.nearest_sites.

    Returns:
        {"title", "body"} on success, or {"error": "<message>"} on failure.
    """
    try:
        protocol = trial.get("protocolSection", trial)
        ident = protocol.get("identificationModule", {})
        design = protocol.get("designModule", {})
        title = ident.get("briefTitle", "")
        phase = ", ".join(design.get("phases", [])) or "not specified"

        passes = [v for v in verdicts if v["verdict"] == "PASS"]
        fit_lines = [f'- {v["reason"]} ("{v["source_quote"]}")' for v in passes] or ["- (matching still being confirmed)"]

        lines = [
            f"Clinical Trial Note — {nct_id}",
            f"Title: {title}",
            f"Phase: {phase}",
            "",
            f"Why this trial may fit {_subject_label(profile)}:",
            *fit_lines,
        ]
        if nearest_site:
            site_line = (
                f"Nearest site: {nearest_site.get('facility', 'unknown facility')} "
                f"({nearest_site.get('distance_mi', '?')} mi)"
            )
            lines += ["", site_line]
        lines += ["", f"Contact: {_contact_line(contact)}", "", "---", AI_DISCLOSURE]

        return {"title": f"Trial Note: {nct_id}", "body": "\n".join(lines)}
    except Exception as e:  # noqa: BLE001 — tool boundary: must never raise into the agent loop (CLAUDE.md §6)
        return {"error": str(e)}
