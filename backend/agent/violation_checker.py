"""
Violation Checker — The killer feature of WhyGraph.

Given a simulated PR (list of changed services, new dependencies, changed files),
checks all active constraints and reports violations with full graph traversal paths.
"""

from backend.graph.connection import get_graph
from backend.graph import queries


def check_violations(
    changed_services: list[str],
    new_dependencies: list[str] = None,
    changed_files: list[str] = None,
) -> dict:
    """
    Check if proposed changes violate any active organizational constraints.

    Args:
        changed_services: List of service names being modified
        new_dependencies: Optional list of new package names being added
        changed_files: Optional list of file paths being modified

    Returns:
        Dict with violations list and summary
    """
    g = get_graph()
    violations = []
    checked_constraints = 0

    for service_name in changed_services:
        # Query all active constraints for this service
        result = g.query(
            queries.FIND_CONSTRAINTS_FOR_SERVICE,
            {"serviceName": service_name},
        )

        for row in result.result_set:
            checked_constraints += 1
            constraint_desc = row[1]  # description
            constraint_desc_lower = constraint_desc.lower()

            # Check if any new dependency or file change triggers this constraint
            is_violated = False
            trigger_reason = ""

            # Check new dependencies against constraint text
            if new_dependencies:
                for dep in new_dependencies:
                    dep_lower = dep.lower()
                    # Check if the constraint mentions this dependency negatively
                    if dep_lower in constraint_desc_lower or _fuzzy_match(dep_lower, constraint_desc_lower):
                        is_violated = True
                        trigger_reason = f"New dependency '{dep}' conflicts with constraint"
                        break

            # Check changed files for pattern matches
            if not is_violated and changed_files:
                for filepath in changed_files:
                    if _file_matches_constraint(filepath, constraint_desc_lower):
                        is_violated = True
                        trigger_reason = f"Changed file '{filepath}' may violate constraint"
                        break

            if is_violated:
                violation = {
                    "constraint_id": row[0],
                    "description": constraint_desc,
                    "type": row[2],
                    "severity": row[3],
                    "source_type": row[4],
                    "source_id": row[5],
                    "source_title": row[6],
                    "author_name": row[7],
                    "trigger_reason": trigger_reason,
                    "service": service_name,
                    "traversal_path": _build_traversal_path(row, service_name),
                }

                # Add post-mortem evidence if available
                if row[8]:  # postmortem_id
                    violation["evidence"] = {
                        "postmortem_id": row[8],
                        "postmortem_title": row[9],
                        "incident_id": row[10],
                        "incident_severity": row[11],
                    }

                violations.append(violation)

    # Find recommended experts for the affected services
    experts = []
    for service_name in changed_services:
        result = g.query(
            queries.FIND_EXPERTS_FOR_SERVICE,
            {"serviceName": service_name},
        )
        for row in result.result_set:
            experts.append({
                "name": row[0],
                "email": row[1],
                "role": row[2],
                "team": row[3],
                "score": row[4],
                "service": service_name,
            })

    return {
        "status": "VIOLATIONS_FOUND" if violations else "CLEAN",
        "violations_count": len(violations),
        "constraints_checked": checked_constraints,
        "services_checked": changed_services,
        "violations": violations,
        "recommended_experts": experts[:5],  # Top 5 across all services
    }


def _fuzzy_match(term: str, text: str) -> bool:
    """
    Simple fuzzy matching for dependency names against constraint text.
    Handles common variations like 'memcached' matching 'Memcached' or 'pymemcache'.
    """
    # Direct containment
    if term in text:
        return True

    # Common library name variations
    variations = {
        "pymemcache": ["memcached", "memcache"],
        "memcached": ["memcache", "pymemcache"],
        "pymongo": ["mongodb", "mongo"],
        "mongodb": ["mongo", "pymongo"],
        "motor": ["mongodb", "mongo"],
        "redis": ["redis"],
        "sqlalchemy": ["sql", "orm"],
    }

    for variant in variations.get(term, []):
        if variant in text:
            return True

    return False


def _file_matches_constraint(filepath: str, constraint_text: str) -> bool:
    """Check if a changed file path is relevant to a constraint."""
    filepath_lower = filepath.lower()

    # Extract meaningful terms from filepath, splitting on path separators, underscores, dashes, dots
    clean_path = filepath_lower.replace("/", " ").replace("\\", " ").replace("_", " ").replace("-", " ").replace(".", " ")
    path_terms = [t for t in clean_path.split() if len(t) > 2]

    # Direct keyword containment
    for term in path_terms:
        if term in constraint_text:
            return True

    # Semantic domain mapping for architecture components
    domain_keywords = {
        "crawler": ["crawler", "crawl", "playwright", "heuristics"],
        "scanner": ["scanner", "scan", "axe", "gemini", "wcag", "gigw", "compliance"],
        "axe": ["scanner", "scan", "axe", "gemini", "wcag", "gigw"],
        "orchestrator": ["pipeline", "stage", "stages", "modular", "artifact"],
        "app": ["pipeline", "stages", "modular", "orchestrator"],
        "pipeline": ["pipeline", "stages", "modular", "artifact"],
    }
    for term in path_terms:
        if term in domain_keywords:
            for related in domain_keywords[term]:
                if related in constraint_text:
                    return True

    return False



def _build_traversal_path(row, service_name: str) -> str:
    """Build a human-readable graph traversal path for the violation."""
    parts = [f"PR ({service_name})"]
    parts.append(f"Service:{service_name}")
    parts.append(f'Constraint:"{row[1][:50]}..."')

    if row[4]:  # source_type
        parts.append(f"{row[4]}:{row[5]}")

    if row[8]:  # postmortem_id
        parts.append(f"PostMortem:{row[8]} ({row[10]})")

    return " → ".join(parts)
