"""
WhyGraph — GitHub Actions Pull Request Architectural Enforcement Script

Intended for CI/CD workflows:
- Scans files and dependency changes in a Pull Request
- Queries the FalkorDB constraint graph
- Posts a formatted architectural audit report to GITHUB_STEP_SUMMARY / PR comment
- Exits with code 1 if blocking constraints (MUST severity) are violated
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from backend.agent.violation_checker import check_violations


def generate_pr_comment_markdown(result: dict, service_name: str) -> str:
    lines = [
        "## 🚨 WhyGraph Architectural Radar: Constraint Violations Detected",
        f"> **Service Being Modified:** `{service_name}`",
        f"> **Total Constraints Checked:** `{result['constraints_checked']}` active rules in FalkorDB",
        "",
        "This Pull Request proposes changes that breach documented team architectural decisions.",
        "",
        "| Severity | Violated Constraint | Original Source | Historical Outage Evidence |",
        "|---|---|---|---|",
    ]

    for v in result["violations"]:
        evidence_str = "None"
        if v.get("evidence"):
            ev = v["evidence"]
            evidence_str = f"💥 **{ev['incident_id']} ({ev['incident_severity']})**: {ev['postmortem_title']}"

        source_str = f"{v['source_type']}: {v['source_id']} (*{v['source_title']}*)"
        rule_desc = v["description"].replace("\n", " ")
        lines.append(f"| **`{v['severity']}`** | {rule_desc} | {source_str} | {evidence_str} |")

    lines.append("")
    lines.append("### 🔗 Graph Traversal Lineage (FalkorDB Sub-Millisecond Path)")
    for v in result["violations"]:
        lines.append(f"- `{v['traversal_path']}`")

    if result.get("recommended_experts"):
        lines.append("")
        lines.append("### 👤 Required Architectural Reviewers (Dynamic Multi-Signal Scoring)")
        lines.append("These domain experts have the deepest operational understanding of this service:")
        for exp in result["recommended_experts"][:3]:
            lines.append(f"- **{exp['name']}** ({exp['team']}, *{exp['role']}*) — Score: **{exp['score']}/100**")

    lines.append("")
    lines.append("---")
    lines.append("*Automated architectural review powered by [WhyGraph](https://github.com/vinnavan/whygraph) &bull; Track 3: Company Brain (FalkorDB)*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="WhyGraph PR Violation Checker for CI/CD")
    parser.add_argument("--service", required=True, help="Target microservice name")
    parser.add_argument("--deps", default="", help="Comma-separated list of new dependencies")
    parser.add_argument("--files", default="", help="Comma-separated list of changed files")
    parser.add_argument("--fail-on-violation", action="store_true", default=True, help="Exit code 1 if violations found")
    args = parser.parse_args()

    deps_list = [d.strip() for d in args.deps.split(",") if d.strip()]
    files_list = [f.strip() for f in args.files.split(",") if f.strip()]

    result = check_violations(
        changed_services=[args.service],
        new_dependencies=deps_list if deps_list else None,
        changed_files=files_list if files_list else None,
    )

    if result["status"] == "VIOLATIONS_FOUND":
        markdown = generate_pr_comment_markdown(result, args.service)
        print(markdown)

        # Write to GitHub Step Summary if running in GitHub Actions
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file:
            try:
                with open(summary_file, "a", encoding="utf-8") as f:
                    f.write(markdown + "\n")
            except Exception:
                pass

        if args.fail_on_violation:
            sys.exit(1)
    else:
        clean_msg = f"✅ WhyGraph: PR is compliant with all {result['constraints_checked']} active constraints for {args.service}."
        print(clean_msg)
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file:
            try:
                with open(summary_file, "a", encoding="utf-8") as f:
                    f.write(f"## ✅ WhyGraph Architectural Radar: Compliant\n\nNo violations detected for `{args.service}`.\n")
            except Exception:
                pass
        sys.exit(0)


if __name__ == "__main__":
    main()
