from backend.models.document_chunk import DocumentChunk
from backend.models.enums import ClauseType
from backend.services.policy_rule_extractor import PolicyRuleExtractor, _heuristic_rule_extraction


def test_extractor_sub_limit_rule():
    chunk = DocumentChunk(
        id=1,
        page_number=2,
        clause_or_section_ref="SEC-2.1",
        text="Section 2.1: Inpatient room and board is subject to a daily sub-limit capped at $500 per day.",
    )
    extractor = PolicyRuleExtractor()
    rules = extractor.extract_rules_from_chunks([chunk])

    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_type == ClauseType.SUB_LIMIT
    assert rule.limit_amount == 500.0
    assert rule.source_chunk_id == 1
    assert rule.clause_reference == "SEC-2.1"
    assert rule.page_number == 2
    assert rule.validation_status == "VALID"


def test_extractor_waiting_period_rule():
    chunk = DocumentChunk(
        id=2,
        page_number=3,
        clause_or_section_ref="SEC-3.4",
        text="Section 3.4: A mandatory 30 days waiting period applies to all non-emergency illnesses.",
    )
    extractor = PolicyRuleExtractor()
    rules = extractor.extract_rules_from_chunks([chunk])

    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_type == ClauseType.WAITING_PERIOD
    assert rule.waiting_period_days == 30
    assert rule.clause_reference == "SEC-3.4"
    assert rule.validation_status == "VALID"


def test_extractor_exclusion_rule():
    chunk = DocumentChunk(
        id=3,
        page_number=4,
        clause_or_section_ref="EXCL-01",
        text="Section 4.1: Cosmetic and elective aesthetic procedures are strictly excluded from coverage.",
    )
    extractor = PolicyRuleExtractor()
    rules = extractor.extract_rules_from_chunks([chunk])

    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_type == ClauseType.EXCLUSION
    assert "cosmetic" in rule.rule_description.lower()


def test_extractor_mandatory_document_rule():
    chunk = DocumentChunk(
        id=4,
        page_number=5,
        clause_or_section_ref="DOC-01",
        text="Section 5.1: Claimant must submit an itemized hospital bill and discharge summary.",
    )
    extractor = PolicyRuleExtractor()
    rules = extractor.extract_rules_from_chunks([chunk])

    assert len(rules) == 1
    assert rules[0].rule_type == ClauseType.MANDATORY_DOCUMENT


def test_extractor_deductible_rule():
    chunk = DocumentChunk(
        id=5,
        page_number=1,
        clause_or_section_ref="SEC-1.2",
        text="Section 1.2: Standard annual policy deductible is $250 per policy year.",
    )
    extractor = PolicyRuleExtractor()
    rules = extractor.extract_rules_from_chunks([chunk])

    assert len(rules) == 1
    assert rules[0].rule_type == ClauseType.DEDUCTIBLE
    assert rules[0].deductible_amount == 250.0


def test_extractor_empty_chunk_list():
    extractor = PolicyRuleExtractor()
    assert extractor.extract_rules_from_chunks([]) == []


def test_extractor_silence_as_absence_no_invented_exclusions():
    chunk = DocumentChunk(
        id=6,
        page_number=1,
        clause_or_section_ref="SEC-GEN",
        text="This policy covers inpatient medical treatments in recognized hospitals.",
    )
    extractor = PolicyRuleExtractor()
    rules = extractor.extract_rules_from_chunks([chunk])

    assert len(rules) == 1
    # Scope rule, must not invent exclusions
    assert rules[0].rule_type == ClauseType.COVERAGE_SCOPE
    assert rules[0].rule_type != ClauseType.EXCLUSION
