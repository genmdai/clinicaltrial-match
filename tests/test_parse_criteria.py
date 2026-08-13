from backend.tools.parse_criteria import split_criteria


def test_split_criteria_standard_order():
    text = (
        "Inclusion Criteria:\n\n* Age >= 18\n* NSCLC\n\n"
        "Exclusion Criteria:\n\n* Untreated brain metastases"
    )
    chunks = split_criteria(text)
    assert "Age >= 18" in chunks["inclusion"]
    assert "NSCLC" in chunks["inclusion"]
    assert "Untreated brain metastases" in chunks["exclusion"]
    assert "Exclusion Criteria" not in chunks["inclusion"]


def test_split_criteria_reversed_order():
    text = "Exclusion Criteria:\n\n* Prior chemo\n\nInclusion Criteria:\n\n* Age >= 18"
    chunks = split_criteria(text)
    assert "Prior chemo" in chunks["exclusion"]
    assert "Age >= 18" in chunks["inclusion"]
    assert "Inclusion Criteria" not in chunks["exclusion"]


def test_split_criteria_inclusion_only():
    chunks = split_criteria("Inclusion Criteria:\n\n* Age >= 18")
    assert chunks == {"inclusion": "* Age >= 18"}


def test_split_criteria_no_headers_falls_back_to_unspecified():
    chunks = split_criteria("Patients must be over 18 and have no prior chemo.")
    assert list(chunks.keys()) == ["unspecified"]
    assert "over 18" in chunks["unspecified"]


def test_split_criteria_case_insensitive_headers():
    text = "inclusion criteria:\n* Age >= 18\n\nEXCLUSION CRITERIA:\n* Prior chemo"
    chunks = split_criteria(text)
    assert "Age >= 18" in chunks["inclusion"]
    assert "Prior chemo" in chunks["exclusion"]
