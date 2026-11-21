import datetime
import pytest
from pydantic import ValidationError
from backend.models.enums import PolicyStatus, ClauseType, ClaimStatus
from backend.schemas.policy import PolicyCreate, PolicyClauseCreate
from backend.schemas.claim import ClaimCreate


def test_valid_policy_create_schema():
    payload = {
        "policy_number": "POL-VAL-001",
        "title": "Health Protector Standard",
        "insurer_name": "Apex Mutual",
        "policyholder_name": "Bob Green",
        "effective_date": datetime.date(2026, 1, 1),
        "expiration_date": datetime.date(2027, 1, 1),
        "premium_amount": 950.0,
        "max_coverage_limit": 250000.0,
        "status": PolicyStatus.ACTIVE,
        "clauses": [
            {
                "clause_code": "WAIT-01",
                "clause_type": ClauseType.WAITING_PERIOD,
                "title": "Pre-existing Disease Waiting Period",
                "clause_text": "30-day initial waiting period applies to all non-emergency treatments.",
                "waiting_period_days": 30,
            }
        ],
    }
    schema = PolicyCreate(**payload)
    assert schema.policy_number == "POL-VAL-001"
    assert len(schema.clauses) == 1
    assert schema.clauses[0].waiting_period_days == 30


def test_invalid_policy_dates_raise_error():
    payload = {
        "policy_number": "POL-INVALID-DATE",
        "title": "Invalid Plan",
        "insurer_name": "Apex Mutual",
        "policyholder_name": "Bob Green",
        "effective_date": datetime.date(2026, 6, 1),
        "expiration_date": datetime.date(2026, 1, 1),  # Earlier than effective_date
        "max_coverage_limit": 10000.0,
    }
    with pytest.raises(ValidationError) as exc_info:
        PolicyCreate(**payload)
    assert "expiration_date cannot be earlier than effective_date" in str(exc_info.value)


def test_invalid_negative_claim_amount():
    payload = {
        "claim_number": "CLM-NEG-001",
        "policy_id": 1,
        "claimant_name": "John Doe",
        "incident_date": datetime.date(2026, 2, 1),
        "filing_date": datetime.date(2026, 2, 10),
        "claimed_amount": -500.0,  # Negative amount must fail
    }
    with pytest.raises(ValidationError):
        ClaimCreate(**payload)


def test_invalid_claim_filing_before_incident():
    payload = {
        "claim_number": "CLM-EARLY-001",
        "policy_id": 1,
        "claimant_name": "John Doe",
        "incident_date": datetime.date(2026, 3, 15),
        "filing_date": datetime.date(2026, 3, 10),  # Filing before incident occurred
        "claimed_amount": 1000.0,
    }
    with pytest.raises(ValidationError) as exc_info:
        ClaimCreate(**payload)
    assert "filing_date cannot be earlier than incident_date" in str(exc_info.value)
