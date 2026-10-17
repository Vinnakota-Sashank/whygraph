"""Parse ADR markdown files and load them into the FalkorDB graph."""

import os
import glob
import frontmatter
from backend.config import config
from backend.graph.connection import get_graph


def _parse_adr_file(filepath: str) -> dict:
    """Parse a single ADR markdown file with YAML frontmatter."""
    with open(filepath, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)

    return {
        "id": post.metadata.get("id", ""),
        "title": post.metadata.get("title", ""),
        "status": post.metadata.get("status", "proposed"),
        "date": str(post.metadata.get("date", "")),
        "authors": post.metadata.get("authors", []),
        "applies_to": post.metadata.get("applies_to", []),
        "supersedes": post.metadata.get("supersedes"),
        "content": post.content,
        "filepath": filepath,
    }


def _extract_constraints_section(content: str) -> list[str]:
    """
    Extract bullet points from the '## Constraints' section of an ADR.
    This is a deterministic extraction — no LLM needed for structured ADRs.
    """
    constraints = []
    in_constraints = False

    for line in content.split("\n"):
        stripped = line.strip()

        # Start of constraints section
        if stripped.lower().startswith("## constraint"):
            in_constraints = True
            continue

        # End of constraints section (next heading)
        if in_constraints and stripped.startswith("## "):
            break

        # Capture bullet points
        if in_constraints and (stripped.startswith("- ") or stripped.startswith("* ")):
            constraint_text = stripped[2:].strip()
            if constraint_text:
                constraints.append(constraint_text)

    return constraints


def _classify_constraint(text: str) -> tuple[str, str]:
    """
    Classify a constraint's type and severity from its text.
    Returns (type, severity).
    """
    text_lower = text.lower()

    # Determine type
    if any(kw in text_lower for kw in ["security", "auth", "encrypt", "secret", "credential"]):
        ctype = "SECURITY"
    elif any(kw in text_lower for kw in ["performance", "latency", "throughput", "timeout", "pool"]):
        ctype = "PERFORMANCE"
    elif any(kw in text_lower for kw in ["never", "not permitted", "prohibited", "not allowed", "must not"]):
        ctype = "ARCHITECTURAL"
    else:
        ctype = "OPERATIONAL"

    # Determine severity
    if any(kw in text_lower for kw in ["must", "never", "not permitted", "prohibited", "required", "mandatory"]):
        severity = "MUST"
    elif any(kw in text_lower for kw in ["should", "recommend", "prefer"]):
        severity = "SHOULD"
    else:
        severity = "SHOULD"

    return ctype, severity


def load_adrs():
    """Parse all ADR files and create ADR, Constraint nodes with relationships."""
    g = get_graph()

    adr_files = glob.glob(os.path.join(config.ADR_DIR, "*.md"))

    if not adr_files:
        print("  ⚠️  No ADR files found in data/adrs/")
        return

    constraint_count = 0

    for filepath in adr_files:
        adr = _parse_adr_file(filepath)

        # Create ADR node
        g.query(
            """
            MERGE (a:ADR {id: $id})
            SET a.title = $title,
                a.status = $status,
                a.date = $date,
                a.filePath = $filePath
            """,
            {
                "id": adr["id"],
                "title": adr["title"],
                "status": adr["status"],
                "date": adr["date"],
                "filePath": adr["filepath"],
            },
        )

        # ADR -> CONSTRAINS -> Service edges
        for service_name in adr["applies_to"]:
            g.query(
                """
                MATCH (a:ADR {id: $adrId})
                MATCH (s:Service {name: $serviceName})
                MERGE (a)-[:CONSTRAINS]->(s)
                """,
                {"adrId": adr["id"], "serviceName": service_name},
            )

        # Person -> AUTHORED -> ADR edges
        for author_handle in adr["authors"]:
            # Try matching by email pattern (author_handle might be email prefix)
            g.query(
                """
                MATCH (p:Person)
                WHERE p.email STARTS WITH $handle
                MATCH (a:ADR {id: $adrId})
                MERGE (p)-[:AUTHORED]->(a)
                """,
                {"handle": author_handle, "adrId": adr["id"]},
            )

        # Extract and create Constraint nodes from the ADR content
        raw_constraints = _extract_constraints_section(adr["content"])

        for i, text in enumerate(raw_constraints):
            c_id = f"{adr['id']}-C{i + 1}"
            c_type, c_severity = _classify_constraint(text)

            g.query(
                """
                MERGE (c:Constraint {id: $id})
                SET c.description = $description,
                    c.type = $type,
                    c.severity = $severity,
                    c.isActive = true,
                    c.extractedAt = $date,
                    c.lastValidatedAt = $date,
                    c.source = 'ADR'
                """,
                {
                    "id": c_id,
                    "description": text,
                    "type": c_type,
                    "severity": c_severity,
                    "date": adr["date"],
                },
            )

            # ADR -> DEFINES -> Constraint
            g.query(
                """
                MATCH (a:ADR {id: $adrId})
                MATCH (c:Constraint {id: $cId})
                MERGE (a)-[:DEFINES]->(c)
                """,
                {"adrId": adr["id"], "cId": c_id},
            )

            # Constraint -> APPLIES_TO -> Service (inherit from ADR)
            for service_name in adr["applies_to"]:
                g.query(
                    """
                    MATCH (c:Constraint {id: $cId})
                    MATCH (s:Service {name: $serviceName})
                    MERGE (c)-[:APPLIES_TO]->(s)
                    """,
                    {"cId": c_id, "serviceName": service_name},
                )

            constraint_count += 1

    print(f"  ✅ Loaded {len(adr_files)} ADRs with {constraint_count} extracted constraints")
