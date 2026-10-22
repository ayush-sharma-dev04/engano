"""Local offline benchmark for Engano AI Review Engine.

Executes review engine against the official Nimbus Cloud test fixture
and displays structured benchmark metrics.
"""

import argparse
import json
from pathlib import Path
import sys
import time

# Ensure repo root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_engine.config import EngineConfig, ProviderType
from ai_engine.integrations.supabase_policy_repository import MockPolicyRepository
from ai_engine.providers.factory import get_provider
from ai_engine.review import run_brand_review
from ai_engine.schemas.review import ReviewInput


def run_benchmark(provider_name: str = "rules_only") -> int:
    """Execute local benchmark against the offline Nimbus fixture."""
    fixture_path = Path(__file__).resolve().parent.parent / "data" / "brand_library" / "nimbus_db.json"
    if not fixture_path.exists():
        print(f"Error: Fixture not found at {fixture_path}", file=sys.stderr)
        return 1

    # Load offline test fixture into isolated MockPolicyRepository
    repo = MockPolicyRepository()
    policy = repo.load_fixture(fixture_path)

    test_draft = (
        policy.test_fixtures.get("sample_draft")
        if policy.test_fixtures
        else "NimbusDB is the fastest database in the world, with 100% uptime. Try it free forever and see why teams love it!"
    )

    print("=" * 70)
    print("ENGANO AI/ML ENGINE LOCAL BENCHMARK")
    print("=" * 70)
    print(f"Brand Fixture:    {policy.brand_name} ({policy.brand_id})")
    print(f"Provider Mode:    {provider_name}")
    print(f"Test Draft Copy:  \"{test_draft}\"")
    print("-" * 70)

    config = EngineConfig(
        AI_PROVIDER=ProviderType(provider_name),
        STRICT_MODE=True,
    )
    provider = get_provider(provider_type=provider_name, config=config)

    req = ReviewInput(
        draft_id="bench_draft_001",
        brand_id=policy.brand_id,
        content_text=test_draft,
    )

    t0 = time.perf_counter()
    result = run_brand_review(request=req, repository=repo, config=config, provider=provider)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"Completion Status: {result.completion_status}")
    print(f"Overall Decision:  {result.decision.status.value}")
    print(f"Action Required:   {result.decision.action_required_by.value}")
    print(f"Reason:            {result.decision.reason}")
    print(f"Execution Time:    {elapsed_ms:.2f} ms (Engine reported: {result.metadata.processing_time_ms:.2f} ms)")
    print(f"Agents Executed:   {', '.join(result.metadata.agents_executed)}")
    print(f"Fallback Occurred: {result.metadata.fallback_occurred}")
    print("-" * 70)
    print(f"Total Findings Detected: {len(result.findings)}")

    for idx, f in enumerate(result.findings, 1):
        print(f"\n  Finding #{idx}:")
        print(f"    ID:               {f.finding_id}")
        print(f"    Category:         {f.category.value}")
        print(f"    Severity:         {f.severity.value}")
        print(f"    Highlighted:      \"{f.highlighted_text}\" [span: {f.text_span.start}:{f.text_span.end}]")
        print(f"    Evidence Status:  {f.evidence_status.value}")
        print(f"    Explanation:      {f.explanation}")
        if f.cited_source:
            print(f"    Cited Source:     {f.cited_source}")
        if f.suggested_fix:
            print(f"    Suggested Fix:    \"{f.suggested_fix}\"")

    print("\n" + "-" * 70)
    if result.proposed_rewrite:
        print("Proposed Safe Rewrite:")
        print(f"  \"{result.proposed_rewrite}\"")
    else:
        print("Proposed Safe Rewrite: None (Requires creator clarification)")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Engano review engine benchmark")
    parser.add_argument(
        "--provider",
        choices=["rules_only", "ollama", "gemini"],
        default="rules_only",
        help="Provider to execute (default: rules_only)",
    )
    args = parser.parse_args()
    sys.exit(run_benchmark(provider_name=args.provider))
