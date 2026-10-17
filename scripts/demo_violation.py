"""
WhyGraph — Live Demo Simulation Script
Runs the 3 core hackathon demo flows directly in the terminal:
1. Proactive Constraint Violation Detection (PR with unauthorized dependency)
2. Incident Evidence & Lineage Traversal
3. Dynamic Multi-Signal Expertise Ranking
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from backend.agent.violation_checker import check_violations
from backend.agent.expertise_finder import find_experts
from backend.agent.chat import chat


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def run_demo():
    print_banner("WHYGRAPH HACKATHON DEMO: TRACK 3 (COMPANY BRAIN)")
    print("The Engineering Decision Memory that stops teams & AI from repeating mistakes.")

    # ── DEMO 1: The Killer Feature — PR Violation Detection ────────────────────
    print_banner("DEMO 1: Proactive Pull Request Violation Check")
    print("Simulated Scenario:")
    print("  Engineer opens PR #402: 'Optimize checkout cache layer'")
    print("  Changed Service: checkout-service")
    print("  Added Dependency: 'pymemcache'")
    print("  Modified File: services/checkout/cache_client.py\n")

    print("🔍 WhyGraph analyzing PR against FalkorDB constraint graph...\n")

    result = check_violations(
        changed_services=["checkout-service"],
        new_dependencies=["pymemcache"],
        changed_files=["services/checkout/cache_client.py"],
    )

    if result["status"] == "VIOLATIONS_FOUND":
        print("🚨 [RESULT]: CONSTRAINT VIOLATIONS DETECTED!")
        print(f"   Total constraints checked across topology: {result['constraints_checked']}\n")

        for idx, v in enumerate(result["violations"], 1):
            print(f"   Violation #{idx}:")
            print(f"   ├── Rule:        {v['description']}")
            print(f"   ├── Severity:    [{v['severity']}] Type: {v['type']}")
            print(f"   ├── Origin:      {v['source_type']} {v['source_id']} ('{v['source_title']}')")
            print(f"   ├── Decided By:  {v['author_name']}")
            print(f"   ├── Trigger:     {v['trigger_reason']}")
            print(f"   └── Graph Path:  {v['traversal_path']}")

            if v.get("evidence"):
                ev = v["evidence"]
                print(f"       💥 HISTORICAL OUTAGE EVIDENCE:")
                print(f"          - PostMortem: {ev['postmortem_id']} ('{ev['postmortem_title']}')")
                print(f"          - Incident:   {ev['incident_id']} (Severity: {ev['incident_severity']})")
                print(f"          - Reality:    Memcached caused a 2h 15m major outage on 2026-05-22!")

        print("\n   👥 Recommended Experts to Review this PR:")
        for exp in result["recommended_experts"][:2]:
            print(f"      • {exp['name']:<15} | Team: {exp['team']:<10} | Role: {exp['role']:<16} (Score: {exp['score']}/100)")
    else:
        print("✅ No violations detected.")

    # ── DEMO 2: Dynamic Multi-Signal Expertise Ranking ─────────────────────────
    print_banner("DEMO 2: Dynamic Expertise Ranking (Beyond Static CODEOWNERS)")
    print("Query: 'Who genuinely understands checkout-service right now?'\n")

    experts = find_experts("checkout-service")
    print(f"Top Domain Experts for 'checkout-service':")
    print(f"{'Rank':<6}{'Name':<18}{'Team':<12}{'Score':<8}{'Signals Breakdown'}")
    print("-" * 75)
    for exp in experts["experts"]:
        sig = exp["signals"]
        sig_str = f"Commits: {sig['commits']}, Reviews: {sig['reviews']}, Incidents Fixed: {sig['incidents_resolved']}"
        print(f"#{exp['rank']:<5}{exp['name']:<18}{exp['team']:<12}{exp['score']:<8}{sig_str}")
        if exp.get("related_incidents"):
            for inc in exp["related_incidents"]:
                print(f"      └── Led resolution of {inc['id']} ({inc['severity']}): {inc['title']}")

    # ── DEMO 3: Decision Lineage Q&A ──────────────────────────────────────────
    print_banner("DEMO 3: Tracing 'Why' via Natural Language")
    query = "Why do we use Redis in checkout-service?"
    print(f"User Query: '{query}'\n")

    answer = chat(query)
    print("WhyGraph Response:")
    print("-" * 50)
    print(answer)
    print("-" * 50)

    print("\n🎉 Demo completed successfully!")


if __name__ == "__main__":
    run_demo()
