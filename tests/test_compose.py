from backend.tools.compose import AI_DISCLOSURE, compose_doctor_note, compose_email
from backend.tools.fetch_trial import get_contact

KEYTRUDA_MOM_PROFILE = {
    "subject": "relative",
    "relation": "mother",
    "age": 68,
    "sex": "female",
    "condition": "non-small cell lung cancer",
    "condition_raw": "advanced non-small cell lung cancer",
    "biomarkers": [],
    "prior_treatments": [
        {
            "raw_mention": "Keytruda for a year", "drug_brand": "Keytruda", "drug_generic": "pembrolizumab",
            "drug_class": "anti-PD-1 checkpoint inhibitor", "outcome": "progression", "inferred": True,
            "confidence": "high", "rxnorm_ingredient": None,
        }
    ],
    "treatment_line": 1,
    "ecog": None,
    "comorbidities": [],
    "location_zip": "43215",
    "assumptions": [],
}

VERDICTS_TWO_UNKNOWNS = [
    {"rule_id": "condition", "verdict": "PASS", "reason": "Condition matches.", "source_quote": "NSCLC", "follow_up_question": None},
    {"rule_id": "egfr", "verdict": "UNKNOWN", "reason": "No EGFR info.", "source_quote": "Known EGFR mutation status",
     "follow_up_question": "What is the patient's EGFR mutation status?"},
    {"rule_id": "ecog", "verdict": "UNKNOWN", "reason": "No ECOG info.", "source_quote": "ECOG 0-2",
     "follow_up_question": "What is the patient's ECOG performance status?"},
]

STUDY = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT-IO", "briefTitle": "A Trial of Something for NSCLC"},
        "designModule": {"phases": ["PHASE2"]},
        "contactsLocationsModule": {
            "centralContacts": [{"name": "Jane Doe", "role": "CONTACT", "email": "jane@example.com"}],
        },
    }
}


def test_compose_email_relative_voice():
    contact = get_contact(STUDY)
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "A Trial of Something for NSCLC", VERDICTS_TWO_UNKNOWNS, contact)
    assert "error" not in result
    assert "on behalf of my mother" in result["body"]


def test_compose_email_self_voice():
    self_profile = {**KEYTRUDA_MOM_PROFILE, "subject": "self", "relation": None}
    contact = get_contact(STUDY)
    result = compose_email(self_profile, "NCT-IO", "A Trial of Something for NSCLC", VERDICTS_TWO_UNKNOWNS, contact)
    assert "my own case" in result["body"]
    assert "on behalf of" not in result["body"]


def test_compose_email_includes_only_confirmed_fields():
    contact = get_contact(STUDY)
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "Trial", VERDICTS_TWO_UNKNOWNS, contact)
    body = result["body"]
    assert "68" in body
    assert "Keytruda" in body
    assert "pembrolizumab" not in body or "Keytruda" in body  # generic ok alongside brand, not required alone


def test_compose_email_lists_open_unknown_questions():
    contact = get_contact(STUDY)
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "Trial", VERDICTS_TWO_UNKNOWNS, contact)
    body = result["body"]
    assert "What is the patient's EGFR mutation status?" in body
    assert "What is the patient's ECOG performance status?" in body


def test_compose_email_mailto_built_when_email_present():
    contact = {"name": "Jane Doe", "email": "jane@example.com", "contact_source": "central_contact"}
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "Trial", VERDICTS_TWO_UNKNOWNS, contact)
    assert result["mailto"].startswith("mailto:jane@example.com?")


def test_compose_email_mailto_none_without_email():
    contact = {"name": None, "email": None, "contact_source": "sponsor_only", "guidance": "call the site"}
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "Trial", VERDICTS_TWO_UNKNOWNS, contact)
    assert result["mailto"] is None


def test_compose_email_always_has_ai_disclosure():
    contact = get_contact(STUDY)
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "Trial", VERDICTS_TWO_UNKNOWNS, contact)
    assert AI_DISCLOSURE in result["body"]


def test_compose_doctor_note_includes_quoted_criteria_and_site():
    contact = get_contact(STUDY)
    nearest_site = {"facility": "Downtown Clinic", "distance_mi": 22.1}
    result = compose_doctor_note(KEYTRUDA_MOM_PROFILE, "NCT-IO", STUDY, VERDICTS_TWO_UNKNOWNS, contact, nearest_site)
    assert "error" not in result
    body = result["body"]
    assert "NCT-IO" in body
    assert "NSCLC" in body  # quoted source_quote from the PASS verdict
    assert "Downtown Clinic" in body
    assert "22.1" in body
    assert AI_DISCLOSURE in body


# --- Phase 4 accept test: Keytruda-mom fixture ---
# "a complete draft renders containing NCT ID, the two UNKNOWN questions, correct
# relative voice, and contact from the fallback chain"

def test_keytruda_mom_fixture_end_to_end_accept():
    contact = get_contact(STUDY, patient_lat=39.9612, patient_lon=-82.9988)
    result = compose_email(KEYTRUDA_MOM_PROFILE, "NCT-IO", "A Trial of Something for NSCLC", VERDICTS_TWO_UNKNOWNS, contact)

    assert "error" not in result
    body = result["body"]
    assert "NCT-IO" in body
    assert "What is the patient's EGFR mutation status?" in body
    assert "What is the patient's ECOG performance status?" in body
    assert "on behalf of my mother" in body
    assert contact["contact_source"] == "central_contact"
    assert contact["email"] in result["mailto"]
