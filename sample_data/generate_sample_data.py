"""Sample synthetic dataset generator for ClauseGuard.

Generates realistic but completely synthetic insurance policies, claims, invoices,
supporting evidence, and ground-truth evaluation data illustrating 5 fraud/loophole scenarios:
  Scenario A: Valid Item (standard diagnostics & pharmaceuticals)
  Scenario B: Waiting Period Mismatch (incident within 30-day initial waiting window)
  Scenario C: Excluded & Sub-limit Item (elective cosmetic surgery & room rent cap breach)
  Scenario D: Missing Required Document (mandatory Physician Discharge Summary omitted)
  Scenario E: Policy Loophole (vague discretionary alternative therapy clause exploited)
"""

import json
from pathlib import Path
import pymupdf as fitz


def create_sample_policy_pdf(output_path: Path) -> None:
    """Generates a structured multi-page synthetic insurance policy document."""
    doc = fitz.open()

    # --- Page 1: Policy Overview, Limits & Coverage ---
    page1 = doc.new_page(width=595, height=842)  # A4 size
    text_p1 = """APEX MUTUAL ASSURANCE CORPORATION
COMPREHENSIVE HEALTH SHIELD CONTRACT
Policy Identification: POL-SHIELD-2026-8801
Effective Date: February 01, 2026 | Expiration Date: January 31, 2027
Policyholder: David K. Vance | Insurer: Apex Mutual Assurance

1. DEFINITIONS AND COVERAGE SCOPE
1.1 Total Aggregate Coverage Limit
The maximum aggregate coverage under this contract is $500,000 per policy year.

1.2 Deductible
A standard fixed deductible of $500 shall apply to each independent hospitalization event.

2. SPECIFIC SUB-LIMITS AND ALLOWANCES
2.1 Room and Board Sub-Limit
Reimbursement for inpatient room and board, inclusive of basic nursing and monitor services,
is capped at a strict maximum sub-limit of $500.00 per day. Any hospital charges exceeding
$500.00 per day are the exclusive personal liability of the policyholder.

2.2 Dental Emergency Care
Emergency dental treatments stemming from accidental trauma are subject to an annual
aggregate sub-limit of $1,500.00. Routine dental cleaning and cosmetic orthodontics are not covered.

3. WAITING PERIOD CONDITIONS
3.1 Initial Inception Waiting Period
A mandatory initial waiting period of thirty (30) days from the Effective Date (February 01, 2026)
applies to all non-emergency inpatient admissions and surgical treatments. Any treatment
rendered between February 01, 2026 and March 02, 2026 is strictly excluded from coverage.

3.2 Pre-Existing Conditions
Pre-existing chronic medical conditions are subject to a continuous twenty-four (24) month
waiting period prior to qualification for reimbursement.
"""
    page1.insert_text(fitz.Point(50, 60), text_p1, fontsize=10, fontname="helv", color=(0, 0, 0))

    # --- Page 2: Exclusions, Mandatory Documents & Discretionary Loophole ---
    page2 = doc.new_page(width=595, height=842)
    text_p2 = """APEX MUTUAL ASSURANCE CORPORATION
Policy Identification: POL-SHIELD-2026-8801 (Page 2)

4. GENERAL AND SPECIAL EXCLUSIONS
4.1 Cosmetic and Aesthetic Surgeries
All elective, aesthetic, or cosmetic procedures—including but not limited to rhinoplasty,
liposuction, and non-trauma reconstructive operations—are entirely excluded from coverage
under Section 4.1.

4.2 Experimental Therapies
Therapies or medical treatments not approved by federal healthcare authorities or considered
experimental in nature are non-reimbursable.

5. CLAIM SUBMISSION DEADLINES
5.1 Notice of Claim
The claimant must submit formal written notice of claim within thirty (30) calendar days
following hospital discharge. Late claims filed beyond 30 days are automatically declined.

6. MANDATORY DOCUMENTATION REQUIREMENTS
6.1 Required Substantiating Proof
To adjudicate any claim, the claimant MUST provide:
  (a) Original Itemized Hospital Bill showing daily line-item charges.
  (b) Detailed Physician Discharge Summary signed by the attending medical doctor.
  (c) Standard Claim Form fully completed and endorsed.
Failure to submit the Detailed Physician Discharge Summary shall result in administrative rejection.

9. MISCELLANEOUS DISCRETIONARY PROVISIONS
Clause 9.3 Alternative Therapy Discretion
The insurer may at its sole unreviewable discretion reimburse non-standard holistic supportive
wellness regimens if recommended as adjunctive comfort care by an authorized practitioner,
without requiring standard pharmacological certification or fee schedule adherence.
"""
    page2.insert_text(fitz.Point(50, 60), text_p2, fontsize=10, fontname="helv", color=(0, 0, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_sample_claim_form_pdf(output_path: Path) -> None:
    """Generates a synthetic formal insurance claim submission form."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """APEX MUTUAL HEALTH - OFFICIAL CLAIM FORM
Claim Reference: CLM-2026-8801
Submission Date: March 02, 2026

CLAIMANT INFORMATION
Claimant Name: David K. Vance
Policy Number: POL-SHIELD-2026-8801
Date of Birth: 1985-06-12
Phone: 555-019-4821

INCIDENT AND TREATMENT DETAILS
Incident Date: February 15, 2026
Admission Date: February 15, 2026
Discharge Date: February 19, 2026 (Hospitalized for 4 nights)
Attending Physician: Dr. Amanda Sterling, MD
Hospital Facility: St. Jude Metropolitan Medical Center
Primary Diagnosis: Fall from height during athletic activity resulting in joint sprain and contusions.

ITEMIZED CLAIM EXPENSES SUBMITTED
Line 1. Inpatient Bed & Nursing Care (4 nights @ $600/night): $2,400.00
Line 2. Orthopedic Diagnostic X-Ray Series: $850.00
Line 3. Prescribed Post-Op Antibiotics & Analgesics: $620.00
Line 4. Elective Cosmetic Rhinoplasty: $3,200.00
Line 5. Pre-existing Joint Chronic Therapy: $1,400.00
Line 6. Adjunctive Holistic Aromatherapy & Crystal Wellness: $1,100.00

TOTAL AMOUNT CLAIMED: $9,570.00

CLAIMANT DECLARATION
I certify that the information presented on this form represents true and accurate expenses
incurred for the treatment of injuries sustained on February 15, 2026.
Signed: David K. Vance
Date: March 02, 2026
"""
    page.insert_text(fitz.Point(50, 60), text, fontsize=10, fontname="helv", color=(0, 0, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_sample_invoice_pdf(output_path: Path) -> None:
    """Generates a synthetic itemized hospital medical invoice."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """ST. JUDE METROPOLITAN MEDICAL CENTER
100 Healthcare Pavilion, Metro City
INVOICE NUMBER: INV-SJM-2026-9041
Invoice Date: February 20, 2026

Billed To: David K. Vance
Policy ID: POL-SHIELD-2026-8801
Patient File: MRN-449102

SERVICES RENDERED (February 15, 2026 to February 19, 2026)
--------------------------------------------------------------------------------
Item Description                        Units     Unit Rate ($)    Total ($)
--------------------------------------------------------------------------------
1. Private Patient Room & Monitoring      4 days      600.00        2,400.00
2. Digital Radiography - Pelvis/Spine    1 series     850.00          850.00
3. Pharmaceuticals (Analgesics/IV)       Lot          620.00          620.00
4. Aesthetic Rhinoplasty Procedure       1 unit     3,200.00        3,200.00
5. Chronic Joint Physical Rehabilitation 1 lot      1,400.00        1,400.00
6. Integrative Aromatherapy Sessions     2 visits     550.00        1,100.00
--------------------------------------------------------------------------------
TOTAL INVOICE AMOUNT DUE:                                          $9,570.00
--------------------------------------------------------------------------------

Payment Terms: Due upon receipt.
Authorized Billing Representative: M. Jenkins, Accounts Directorate
"""
    page.insert_text(fitz.Point(50, 60), text, fontsize=10, fontname="helv", color=(0, 0, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_sample_evidence_txt(output_path: Path) -> None:
    """Generates supplementary physician clinical progress notes."""
    text = """ATTENDING PHYSICIAN CLINICAL MEMORANDUM
Patient: David K. Vance | Age: 40 | Gender: Male
Admit Date: 2026-02-15 | Discharge Date: 2026-02-19
Attending Physician: Dr. Amanda Sterling, MD (Lic # MD-88219)

CLINICAL NOTES & SUMMARY:
Patient presented following athletic tumble. Diagnostic radiographs demonstrated contusion
without frank structural fracture. Pain management regimen initiated with standard analgesics.
During hospitalization, patient elected to undergo aesthetic rhinoplasty at personal request.
Physical therapy was rendered for longstanding pre-existing knee crepitus.
Patient additionally requested ancillary aromatherapy comfort care during his inpatient stay.

DOCUMENTATION NOTICE:
Note: Formal Discharge Summary document is currently pending administrative sign-off by
department head and has NOT been finalized or attached to this patient packet.
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)


def create_ground_truth_json(output_path: Path) -> dict:
    """Creates ground-truth evaluation JSON mapping all 5 intentional audit scenarios."""
    ground_truth = {
        "dataset_version": "1.0.0",
        "policy_number": "POL-SHIELD-2026-8801",
        "claim_number": "CLM-2026-8801",
        "total_claimed_amount": 9570.00,
        "scenarios": [
            {
                "scenario_id": "SCENARIO_A",
                "name": "Valid Reimbursable Items",
                "status": "APPROVED",
                "items": [
                    {
                        "description": "Orthopedic Diagnostic X-Ray Series",
                        "amount": 850.00,
                        "applicable_clause": "Section 1.1",
                        "ruling": "Eligible diagnostic expense covered under primary hospitalization scope.",
                    },
                    {
                        "description": "Prescribed Post-Op Antibiotics & Analgesics",
                        "amount": 620.00,
                        "applicable_clause": "Section 1.1",
                        "ruling": "Standard pharmacy medications prescribed for acute trauma.",
                    },
                ],
            },
            {
                "scenario_id": "SCENARIO_B",
                "name": "Waiting Period / Timeline Mismatch",
                "status": "VIOLATION",
                "items": [
                    {
                        "description": "Incident occurred 14 days after policy inception",
                        "policy_effective_date": "2026-02-01",
                        "incident_date": "2026-02-15",
                        "treatment_window": "2026-02-15 to 2026-02-19",
                        "applicable_clause": "Section 3.1 Initial Inception Waiting Period",
                        "ruling": "Policy mandates 30-day initial waiting period from 2026-02-01 to 2026-03-02. Claimed incident occurred on day 14.",
                        "discrepancy_type": "waiting_period_violation",
                        "severity": "high",
                    },
                    {
                        "description": "Pre-existing Joint Chronic Therapy",
                        "amount": 1400.00,
                        "applicable_clause": "Section 3.2 Pre-Existing Conditions",
                        "ruling": "Subject to 24-month waiting period for chronic conditions; policy active for only 2 weeks.",
                        "discrepancy_type": "waiting_period_violation",
                        "severity": "high",
                    },
                ],
            },
            {
                "scenario_id": "SCENARIO_C",
                "name": "Excluded Item and Sub-Limit Breach",
                "status": "VIOLATION",
                "items": [
                    {
                        "description": "Elective Cosmetic Rhinoplasty",
                        "amount": 3200.00,
                        "applicable_clause": "Section 4.1 Cosmetic and Aesthetic Surgeries",
                        "ruling": "Strictly excluded. Rhinoplasty is elective aesthetic surgery not covered under policy.",
                        "discrepancy_type": "clause_exclusion",
                        "severity": "critical",
                    },
                    {
                        "description": "Inpatient Room Rent Sub-Limit Breach",
                        "amount_claimed": 2400.00,
                        "days": 4,
                        "rate_charged": 600.00,
                        "sub_limit_rate": 500.00,
                        "excess_amount": 400.00,
                        "applicable_clause": "Section 2.1 Room and Board Sub-Limit",
                        "ruling": "Room rent is capped at $500/day. $100/day excess ($400 total) must be disallowed.",
                        "discrepancy_type": "sub_limit_breach",
                        "severity": "medium",
                    },
                ],
            },
            {
                "scenario_id": "SCENARIO_D",
                "name": "Missing Required Documentation",
                "status": "MISSING_MANDATORY_DOC",
                "items": [
                    {
                        "missing_document": "Detailed Physician Discharge Summary",
                        "applicable_clause": "Section 6.1(b) Required Substantiating Proof",
                        "ruling": "Policy Section 6.1(b) explicitly mandates a Detailed Physician Discharge Summary. Only clinical memorandum provided; discharge summary is missing.",
                        "discrepancy_type": "missing_document",
                        "severity": "high",
                    }
                ],
            },
            {
                "scenario_id": "SCENARIO_E",
                "name": "Policy Loophole / Ambiguity Exploitation",
                "status": "AMBIGUOUS_LOOPHOLE",
                "items": [
                    {
                        "description": "Adjunctive Holistic Aromatherapy & Crystal Wellness",
                        "amount": 1100.00,
                        "applicable_clause": "Clause 9.3 Alternative Therapy Discretion",
                        "ruling": "Clause 9.3 allows discretionary comfort care without fee schedule or pharmacological proof. Claimant exploits vague wording to bill $1,100 for non-standard crystal therapy.",
                        "discrepancy_type": "loophole_exploit",
                        "severity": "medium",
                    }
                ],
            },
        ],
        "expected_audit_recommendation": "MANUAL_INVESTIGATION",
        "expected_risk_score_range": [75.0, 95.0],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


def generate_all_samples(base_dir: Path) -> dict:
    """Generates all synthetic demo files in the designated directory."""
    policy_path = base_dir / "policies" / "apex_shield_policy.pdf"
    claim_path = base_dir / "claims" / "claim_form_clm_8801.pdf"
    invoice_path = base_dir / "invoices" / "st_jude_medical_invoice.pdf"
    evidence_path = base_dir / "evidence" / "physician_notes.txt"
    ground_truth_path = base_dir / "ground_truth.json"

    create_sample_policy_pdf(policy_path)
    create_sample_claim_form_pdf(claim_path)
    create_sample_invoice_pdf(invoice_path)
    create_sample_evidence_txt(evidence_path)
    create_ground_truth_json(ground_truth_path)

    return {
        "policy": str(policy_path),
        "claim": str(claim_path),
        "invoice": str(invoice_path),
        "evidence": str(evidence_path),
        "ground_truth": str(ground_truth_path),
    }


if __name__ == "__main__":
    target_dir = Path(__file__).resolve().parent
    generated = generate_all_samples(target_dir)
    print("Successfully generated ClauseGuard demo pack:")
    for k, v in generated.items():
        print(f"  - {k}: {v}")
