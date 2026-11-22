"""End-to-end analysis runner for Claim 1 ground truth verification."""
import sys
sys.path.insert(0, '.')
from backend.core.database import SessionLocal
from backend.workflows.claim_analysis_workflow import run_claim_analysis
from backend.models.enums import FindingType, AdvisoryVerdict

db = SessionLocal()
try:
    print("Running end-to-end analysis on Claim 1 (CLM-2026-8801)...")
    report = run_claim_analysis(claim_id=1, db=db)

    print(f"Report ID (DB): {report.report_id}")
    print(f"Verdict: {report.verdict}")
    print(f"Recommendation: {report.recommendation}")
    print(f"Risk Score: {report.overall_risk_score}")
    print(f"Human Review Required: {report.human_review_required}")
    print(f"Fallback Used: {report.fallback_used}")
    print()

    print("=== DISCREPANCY FINDINGS (Fraud Signals) ===")
    for f in report.fraud_signals:
        print(f"  [{f.severity}] {f.finding_type} - {f.title}")

    print()
    print(f"Top Reasons: {report.top_reasons}")
    print(f"Missing Documents: {report.missing_documents}")
    print()

    print("=== CALCULATION SUMMARY ===")
    c = report.calculations
    print(f"  Claimed Amount:          ${c.claimed_amount:,.2f}")
    print(f"  Room Billed:             ${c.room_charges_billed:,.2f}")
    print(f"  Room Excess Deduction:   ${c.room_excess_deduction:,.2f}")
    print(f"  Exclusion Deduction:     ${c.exclusion_deduction:,.2f}")
    print(f"  Deductible Applied:      ${c.deductible_applied:,.2f}")
    print(f"  Total Non-Eligible:      ${c.total_non_eligible_amount:,.2f}")
    print(f"  Net Eligible:            ${c.net_eligible_amount:,.2f}")
    print(f"  Waiting Period Required: {c.waiting_period_days_required} days")
    print(f"  Days Since Inception:    {c.days_since_policy_inception} days")
    print(f"  Waiting Period Violated: {c.is_waiting_period_violated}")
    print(f"  Exclusion Violated:      {c.is_exclusion_violated}")
    print()
    print("  Calculation Steps:")
    for step in c.calculation_steps:
        print(f"    - {step}")

    print()
    print("=== POLICY LOOPHOLES ===")
    for lh in report.policy_loopholes:
        print(f"  [{lh.clause_reference}] {lh.loophole_type}")
        print(f"    {lh.description[:100]}")

    # Ground Truth Verification
    print()
    print("=" * 60)
    print("GROUND TRUTH VERIFICATION (sample_data/ground_truth.json)")
    print("=" * 60)
    signal_types = [f.finding_type for f in report.fraud_signals]
    
    checks = {
        "SCENARIO_B — Waiting Period Violation detected":
            FindingType.WAITING_PERIOD_VIOLATION in signal_types,
        "SCENARIO_C — Clause Exclusion (Cosmetic) detected":
            FindingType.CLAUSE_EXCLUSION in signal_types,
        "SCENARIO_C — Sub-Limit Breach (Room) detected":
            FindingType.SUB_LIMIT_BREACH in signal_types,
        "SCENARIO_D — Missing Document (Discharge Summary) detected":
            FindingType.MISSING_DOCUMENT in signal_types,
        "SCENARIO_E — Policy Loophole detected":
            len(report.policy_loopholes) > 0,
        "Verdict = DO_NOT_TAKE (critical violations present)":
            report.verdict == AdvisoryVerdict.DO_NOT_TAKE,
        "Waiting period math: 14 days (< 30 required)":
            c.days_since_policy_inception == 14 and c.is_waiting_period_violated,
        "Cosmetic exclusion amount >= $3200":
            c.exclusion_deduction >= 3200.0,
    }

    all_passed = True
    for desc, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {desc}")

    print()
    if all_passed:
        print("ALL GROUND TRUTH CHECKS PASSED ✓")
    else:
        print("SOME GROUND TRUTH CHECKS FAILED — see details above.")
finally:
    db.close()
