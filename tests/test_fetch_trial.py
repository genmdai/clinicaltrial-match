from backend.tools.fetch_trial import fetch_trial, get_contact


def test_offline_fetch_returns_cached_study():
    result = fetch_trial("NCT06917079", offline=True)

    assert "error" not in result
    study = result["study"]
    assert study["protocolSection"]["identificationModule"]["nctId"] == "NCT06917079"


def test_offline_fetch_unknown_nct_returns_structured_error():
    result = fetch_trial("NCT00000000", offline=True)

    assert "error" in result
    assert "study" not in result


def _study(protocol: dict) -> dict:
    return {"protocolSection": protocol}


# --- get_contact fallback chain (CLAUDE.md Phase 4) ---

def test_get_contact_prefers_central_contact_with_email():
    study = _study({
        "contactsLocationsModule": {
            "centralContacts": [{"name": "Jane Doe", "role": "CONTACT", "email": "jane@example.com"}],
            "overallOfficials": [{"name": "Dr. Smith", "role": "STUDY_DIRECTOR"}],
        },
    })
    contact = get_contact(study)
    assert contact["contact_source"] == "central_contact"
    assert contact["email"] == "jane@example.com"


def test_get_contact_falls_back_to_overall_official_when_no_usable_central_contact():
    study = _study({
        "contactsLocationsModule": {
            "centralContacts": [{"name": "Sponsor Desk"}],  # no phone/email -> not usable
            "overallOfficials": [{"name": "Dr. Smith", "role": "STUDY_DIRECTOR", "affiliation": "Big Hospital"}],
        },
    })
    contact = get_contact(study)
    assert contact["contact_source"] == "overall_official"
    assert contact["name"] == "Dr. Smith"


def test_get_contact_falls_back_to_nearest_site_contact():
    study = _study({
        "contactsLocationsModule": {
            "locations": [
                {"facility": "Far Site", "geoPoint": {"lat": 5.0, "lon": 5.0}, "contacts": [{"phone": "555-0001"}]},
                {"facility": "Near Site", "geoPoint": {"lat": 40.2812, "lon": -82.9988}, "contacts": [{"phone": "555-0002"}]},
            ],
        },
    })
    contact = get_contact(study, patient_lat=39.9612, patient_lon=-82.9988)
    assert contact["contact_source"] == "site_contact"
    assert contact["facility"] == "Near Site"
    assert contact["phone"] == "555-0002"


def test_get_contact_falls_back_to_sponsor_name_with_guidance():
    study = _study({
        "identificationModule": {"organization": {"fullName": "Acme Trials Inc."}},
        "contactsLocationsModule": {},
    })
    contact = get_contact(study)
    assert contact["contact_source"] == "sponsor_only"
    assert contact["name"] == "Acme Trials Inc."
    assert "call the site" in contact["guidance"].lower()
