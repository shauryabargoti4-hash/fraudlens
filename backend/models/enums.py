from enum import Enum


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    DRAFT = "draft"


class ClauseType(str, Enum):
    EXCLUSION = "exclusion"
    SUB_LIMIT = "sub_limit"
    WAITING_PERIOD = "waiting_period"
    DEDUCTIBLE = "deductible"
    MANDATORY_DOCUMENT = "mandatory_document"
    COVERAGE_SCOPE = "coverage_scope"
    GENERAL_CONDITION = "general_condition"


class ClaimStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    FLAGGED = "flagged"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentType(str, Enum):
    CLAIM_FORM = "claim_form"
    MEDICAL_INVOICE = "medical_invoice"
    DISCHARGE_SUMMARY = "discharge_summary"
    REPAIR_ESTIMATE = "repair_estimate"
    PHOTO_EVIDENCE = "photo_evidence"
    POLICE_REPORT = "police_report"
    IDENTITY_PROOF = "identity_proof"
    POLICY_DOCUMENT = "policy_document"
    OTHER = "other"


class FindingType(str, Enum):
    DATE_MISMATCH = "date_mismatch"
    AMOUNT_INFLATION = "amount_inflation"
    MISSING_DOCUMENT = "missing_document"
    POLICY_VIOLATION = "policy_violation"
    CLAUSE_EXCLUSION = "clause_exclusion"
    WAITING_PERIOD_VIOLATION = "waiting_period_violation"
    SUB_LIMIT_BREACH = "sub_limit_breach"
    DUPLICATE_BILLING = "duplicate_billing"
    LOOPHOLE_EXPLOIT = "loophole_exploit"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MANUAL_INVESTIGATION = "manual_investigation"
    REQUEST_INFORMATION = "request_information"
    # Wave 3 advisory decision outcomes
    TAKE = "take"
    REVIEW_REQUIRED = "review_required"
    DO_NOT_TAKE = "do_not_take"


class AdvisoryVerdict(str, Enum):
    """Advisory claim review recommendations from the deterministic recommendation gate."""
    TAKE = "TAKE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DO_NOT_TAKE = "DO_NOT_TAKE"


class ReviewerOutcome(str, Enum):
    """Clause applicability status determined by the Reviewer node."""
    APPROVED = "approved"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class UserRole(str, Enum):
    """Role-based access control roles for claim auditors and adjudicators."""
    AUDITOR = "AUDITOR"
    SENIOR_ADJUDICATOR = "SENIOR_ADJUDICATOR"
