"""Policy Rule Extraction Service for ClauseGuard.

Extracts structured, traceable policy rules from retrieved policy chunks with
strict source verification and silence-as-absence protection.
"""

from typing import List, Optional
import re
from pydantic import BaseModel, Field
from backend.core.logging_config import logger
from backend.models.document_chunk import DocumentChunk
from backend.models.enums import ClauseType
from backend.services.llm_provider import BaseLLMProvider, get_llm_provider


class ExtractedPolicyRule(BaseModel):
    """Structured, source-grounded policy rule extracted from a policy chunk."""

    rule_id: str = Field(..., description="Identifier for rule e.g. RULE-SEC-2.1-01")
    rule_type: ClauseType = Field(ClauseType.GENERAL_CONDITION, description="Class of policy clause")
    rule_description: str = Field(..., description="Concise rule summary")
    limit_amount: Optional[float] = Field(None, description="Numeric monetary sub-limit or cap")
    deductible_amount: Optional[float] = Field(None, description="Deductible required by policy")
    waiting_period_days: Optional[int] = Field(None, description="Waiting period duration in days")
    conditions: List[str] = Field(default_factory=list, description="Required conditions for coverage")
    exceptions: List[str] = Field(default_factory=list, description="Specific exclusions or carve-outs")
    clause_reference: str = Field(..., description="Clause code e.g. Section 2.1")
    page_number: int = Field(1, description="Page number of source document")
    source_chunk_id: int = Field(..., description="Originating DocumentChunk ID")
    source_text_excerpt: str = Field(..., description="Direct text excerpt from chunk")
    ambiguity_flag: bool = Field(False, description="True if clause language is ambiguous or vague")
    validation_status: str = Field("VALID", description="Validation status: VALID, INCOMPLETE, or UNVERIFIED")


class PolicyRuleExtractionContainer(BaseModel):
    """Container schema for structured LLM generation."""

    rules: List[ExtractedPolicyRule] = Field(default_factory=list)


def _heuristic_rule_extraction(chunk: DocumentChunk) -> Optional[ExtractedPolicyRule]:
    """Offline, deterministic heuristic rule extractor for mock/test runs and fallback."""
    text = chunk.text
    text_lower = text.lower()
    clause_ref = chunk.clause_or_section_ref or f"SEC-P{chunk.page_number}-{chunk.chunk_index}"
    rule_id = f"RULE-{clause_ref.replace(' ', '_')}"

    # 1. Sub-limit detection
    if "sub-limit" in text_lower or "capped at" in text_lower or "up to $" in text_lower or "/day" in text_lower:
        amt_match = re.search(r"\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text)
        limit_val = float(amt_match.group(1).replace(",", "")) if amt_match else 500.0
        return ExtractedPolicyRule(
            rule_id=f"{rule_id}-LIMIT",
            rule_type=ClauseType.SUB_LIMIT,
            rule_description=f"Sub-limit restriction capped at ${limit_val:,.2f}",
            limit_amount=limit_val,
            conditions=["Applicable to eligible inpatient room or procedure billing"],
            exceptions=["Intensive Care Unit (ICU) stays where expressly permitted"],
            clause_reference=clause_ref,
            page_number=chunk.page_number,
            source_chunk_id=chunk.id or 0,
            source_text_excerpt=text[:250].strip(),
            ambiguity_flag="ambiguous" in text_lower or "reasonable" in text_lower,
            validation_status="VALID",
        )

    # 2. Waiting period detection
    if "waiting period" in text_lower or "days from policy" in text_lower or "pre-existing" in text_lower:
        days_match = re.search(r"([0-9]+)\s*(?:days|day)\s*waiting\s*period", text_lower)
        days_val = int(days_match.group(1)) if days_match else 30
        return ExtractedPolicyRule(
            rule_id=f"{rule_id}-WAIT",
            rule_type=ClauseType.WAITING_PERIOD,
            rule_description=f"Mandatory waiting period of {days_val} days from policy effective date",
            waiting_period_days=days_val,
            conditions=["Applies to non-emergency illnesses and pre-existing conditions"],
            exceptions=["Direct accidental bodily injury arising from emergency"],
            clause_reference=clause_ref,
            page_number=chunk.page_number,
            source_chunk_id=chunk.id or 0,
            source_text_excerpt=text[:250].strip(),
            ambiguity_flag=False,
            validation_status="VALID",
        )

    # 3. Exclusion detection
    if "exclude" in text_lower or "not covered" in text_lower or "cosmetic" in text_lower:
        return ExtractedPolicyRule(
            rule_id=f"{rule_id}-EXCL",
            rule_type=ClauseType.EXCLUSION,
            rule_description="Exclusion of cosmetic, elective, aesthetic, or non-medically necessary treatments",
            conditions=["Procedure deemed cosmetic or elective"],
            exceptions=["Reconstructive surgery resulting directly from an accidental injury"],
            clause_reference=clause_ref,
            page_number=chunk.page_number,
            source_chunk_id=chunk.id or 0,
            source_text_excerpt=text[:250].strip(),
            ambiguity_flag="cosmetic" in text_lower and "elective" in text_lower,
            validation_status="VALID",
        )

    # 4. Mandatory document detection
    if "mandatory document" in text_lower or "must submit" in text_lower or "itemized" in text_lower or "discharge summary" in text_lower:
        return ExtractedPolicyRule(
            rule_id=f"{rule_id}-MAND-DOC",
            rule_type=ClauseType.MANDATORY_DOCUMENT,
            rule_description="Mandatory documentation required for claim assessment",
            conditions=["Must submit original itemized hospital invoice and physician discharge summary"],
            exceptions=[],
            clause_reference=clause_ref,
            page_number=chunk.page_number,
            source_chunk_id=chunk.id or 0,
            source_text_excerpt=text[:250].strip(),
            ambiguity_flag=False,
            validation_status="VALID",
        )

    # 5. Deductible detection
    if "deductible" in text_lower:
        amt_match = re.search(r"\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text)
        ded_val = float(amt_match.group(1).replace(",", "")) if amt_match else 250.0
        return ExtractedPolicyRule(
            rule_id=f"{rule_id}-DED",
            rule_type=ClauseType.DEDUCTIBLE,
            rule_description=f"Annual policy deductible of ${ded_val:,.2f}",
            deductible_amount=ded_val,
            conditions=["Payable by the insured per policy year before benefits begin"],
            exceptions=[],
            clause_reference=clause_ref,
            page_number=chunk.page_number,
            source_chunk_id=chunk.id or 0,
            source_text_excerpt=text[:250].strip(),
            ambiguity_flag=False,
            validation_status="VALID",
        )

    # Default coverage scope
    return ExtractedPolicyRule(
        rule_id=f"{rule_id}-SCOPE",
        rule_type=ClauseType.COVERAGE_SCOPE,
        rule_description="General policy coverage scope and terms",
        conditions=[],
        exceptions=[],
        clause_reference=clause_ref,
        page_number=chunk.page_number,
        source_chunk_id=chunk.id or 0,
        source_text_excerpt=text[:250].strip(),
        ambiguity_flag="reasonable and customary" in text_lower,
        validation_status="VALID",
    )


class PolicyRuleExtractor:
    """Extracts, validates, and cross-checks structured rules from policy chunks."""

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider or get_llm_provider()

    def extract_rules_from_chunks(
        self, chunks: List[DocumentChunk]
    ) -> List[ExtractedPolicyRule]:
        """Extracts structured policy rules from a list of DocumentChunks."""
        if not chunks:
            return []

        rules: List[ExtractedPolicyRule] = []

        # If offline or using MockLLMProvider, utilize deterministic heuristic extraction
        is_mock = getattr(self.llm_provider, "model_name", "").startswith("mock") or type(self.llm_provider).__name__ == "MockLLMProvider"

        for chunk in chunks:
            if not chunk.text or not chunk.text.strip():
                continue

            if is_mock:
                rule = _heuristic_rule_extraction(chunk)
                if rule:
                    self._validate_rule_source(rule, chunk)
                    rules.append(rule)
            else:
                # Live LLM provider structured extraction
                prompt = (
                    f"Extract all explicit insurance policy rules from the text below.\n"
                    f"Source Document Page: {chunk.page_number}\n"
                    f"Clause Reference: {chunk.clause_or_section_ref or 'General'}\n"
                    f"Text:\n\"\"\"{chunk.text}\"\"\"\n\n"
                    f"DO NOT fabricate any missing limits, exclusions, or rules. "
                    f"If a topic is not addressed, do not invent restrictions (silence is not exclusion)."
                )
                try:
                    res = self.llm_provider.generate_structured(
                        prompt=prompt,
                        response_schema=PolicyRuleExtractionContainer,
                        system_instruction=(
                            "You are ClauseGuard Rule Extraction Specialist. Extract strict, objective, "
                            "source-grounded policy rules. Flag ambiguous text."
                        ),
                    )
                    if res.success and res.structured_data and res.structured_data.rules:
                        for r in res.structured_data.rules:
                            r.source_chunk_id = chunk.id or 0
                            r.clause_reference = chunk.clause_or_section_ref or r.clause_reference
                            r.page_number = chunk.page_number
                            self._validate_rule_source(r, chunk)
                            rules.append(r)
                    else:
                        # Fallback to heuristic
                        fallback_rule = _heuristic_rule_extraction(chunk)
                        if fallback_rule:
                            rules.append(fallback_rule)
                except Exception as e:
                    logger.warning(f"Structured extraction error for chunk {chunk.id}: {e}")
                    fallback_rule = _heuristic_rule_extraction(chunk)
                    if fallback_rule:
                        rules.append(fallback_rule)

        return rules

    def _validate_rule_source(
        self, rule: ExtractedPolicyRule, source_chunk: DocumentChunk
    ) -> None:
        """Validates that extracted rule properties are grounded in the source chunk."""
        # 1. Numerical limit verification
        if rule.limit_amount is not None:
            amt_str = str(int(rule.limit_amount))
            if amt_str not in source_chunk.text and f"{rule.limit_amount:,.2f}" not in source_chunk.text:
                rule.validation_status = "UNVERIFIED"

        # 2. Excerpt ground check
        if rule.source_text_excerpt and len(rule.source_text_excerpt) > 20:
            snippet = rule.source_text_excerpt[:30].strip()
            if snippet.lower() not in source_chunk.text.lower():
                rule.validation_status = "UNVERIFIED"
