"""Parse post-mortem markdown files and load them into the FalkorDB graph."""

import os
import glob
import frontmatter
from backend.config import config
from backend.graph.connection import get_graph


def _parse_postmortem_file(filepath: str) -> dict:
    """Parse a single post-mortem markdown file with YAML frontmatter."""
    with open(filepath, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)

    return {
        "id": post.metadata.get("id", ""),
        "title": post.metadata.get("title", ""),
        "incident_id": post.metadata.get("incident_id", ""),
        "severity": post.metadata.get("severity", "SEV-3"),
        "date": str(post.metadata.get("date", "")),
        "duration_minutes": post.metadata.get("duration_minutes", 0),
        "affected_services": post.metadata.get("affected_services", []),
        "root_cause_service": post.metadata.get("root_cause_service", ""),
        "author": post.metadata.get("author", ""),
        "reviewers": post.metadata.get("reviewers", []),
        "content": post.content,
        "filepath": filepath,
    }


def _extract_lessons_constraints(content: str) -> list[str]:
    """
    Extract CONSTRAINT lines from 'Lessons Learned' section.
    Looks for lines containing '**CONSTRAINT**:' pattern.
    """
    constraints = []

    for line in content.split("\n"):
        stripped = line.strip()
        # Match "- **CONSTRAINT**: ..." pattern
        if "**CONSTRAINT**" in stripped or "**constraint**" in stripped.lower():
            # Extract the text after the CONSTRAINT marker
            parts = stripped.split("**:", 1)
            if len(parts) > 1:
                constraint_text = parts[1].strip()
            else:
                # Try splitting on **: 
                parts = stripped.split("**", 2)
                if len(parts) > 2:
                    constraint_text = parts[2].strip().lstrip(":").strip()
                else:
                    constraint_text = stripped
            
            if constraint_text:
                constraints.append(constraint_text)

    return constraints


def _detect_patterns(postmortems: list[dict]) -> list[dict]:
    """
    Detect recurring patterns across multiple post-mortems.
    Simple keyword-based clustering for MVP.
    """
    patterns = {}

    # Pattern detection keywords
    pattern_keywords = {
        "sync_call_cascade": ["synchronous", "sync", "timeout", "cascading", "thread pool"],
        "cache_misconfiguration": ["cache", "memcached", "redis", "connection pool"],
        "unauthorized_tech": ["unauthorized", "not permitted", "violated", "adr"],
        "missing_circuit_breaker": ["circuit breaker", "no fallback", "no retry"],
    }

    for pm in postmortems:
        content_lower = pm["content"].lower()
        for pattern_id, keywords in pattern_keywords.items():
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches >= 2:  # At least 2 keyword matches
                if pattern_id not in patterns:
                    patterns[pattern_id] = {
                        "id": pattern_id,
                        "description": pattern_id.replace("_", " ").title(),
                        "incidents": [],
                        "services": set(),
                    }
                patterns[pattern_id]["incidents"].append(pm["incident_id"])
                patterns[pattern_id]["services"].update(pm["affected_services"])

    # Only return patterns with 1+ occurrences (they'll show as recurring if >1)
    return [
        {
            **p,
            "services": list(p["services"]),
            "occurrenceCount": len(p["incidents"]),
        }
        for p in patterns.values()
    ]


def load_postmortems():
    """Parse all post-mortem files and create PostMortem, Incident, Pattern nodes."""
    g = get_graph()

    pm_files = glob.glob(os.path.join(config.POSTMORTEM_DIR, "*.md"))

    if not pm_files:
        print("  ⚠️  No post-mortem files found in data/postmortems/")
        return

    postmortems = []
    constraint_count = 0

    for filepath in pm_files:
        pm = _parse_postmortem_file(filepath)
        postmortems.append(pm)

        # Create PostMortem node
        g.query(
            """
            MERGE (pm:PostMortem {id: $id})
            SET pm.title = $title,
                pm.severity = $severity,
                pm.date = $date,
                pm.duration_minutes = $duration,
                pm.root_cause_service = $rootCause,
                pm.filePath = $filePath
            """,
            {
                "id": pm["id"],
                "title": pm["title"],
                "severity": pm["severity"],
                "date": pm["date"],
                "duration": pm["duration_minutes"],
                "rootCause": pm["root_cause_service"],
                "filePath": pm["filepath"],
            },
        )

        # Create Incident node
        g.query(
            """
            MERGE (inc:Incident {id: $id})
            SET inc.title = $title,
                inc.severity = $severity,
                inc.date = $date,
                inc.duration_minutes = $duration
            """,
            {
                "id": pm["incident_id"],
                "title": pm["title"],
                "severity": pm["severity"],
                "date": pm["date"],
                "duration": pm["duration_minutes"],
            },
        )

        # Incident -> DOCUMENTED_IN -> PostMortem
        g.query(
            """
            MATCH (inc:Incident {id: $incId})
            MATCH (pm:PostMortem {id: $pmId})
            MERGE (inc)-[:DOCUMENTED_IN]->(pm)
            """,
            {"incId": pm["incident_id"], "pmId": pm["id"]},
        )

        # Incident -> AFFECTED -> Service edges
        for service_name in pm["affected_services"]:
            g.query(
                """
                MATCH (inc:Incident {id: $incId})
                MATCH (s:Service {name: $serviceName})
                MERGE (inc)-[:AFFECTED]->(s)
                """,
                {"incId": pm["incident_id"], "serviceName": service_name},
            )

        # Incident -> ROOT_CAUSE_IN -> Service
        if pm["root_cause_service"]:
            g.query(
                """
                MATCH (inc:Incident {id: $incId})
                MATCH (s:Service {name: $serviceName})
                MERGE (inc)-[:ROOT_CAUSE_IN]->(s)
                """,
                {"incId": pm["incident_id"], "serviceName": pm["root_cause_service"]},
            )

        # Person -> WROTE -> PostMortem
        if pm["author"]:
            g.query(
                """
                MATCH (p:Person)
                WHERE p.email STARTS WITH $handle
                MATCH (pm:PostMortem {id: $pmId})
                MERGE (p)-[:WROTE]->(pm)
                """,
                {"handle": pm["author"], "pmId": pm["id"]},
            )

        # Extract constraints from lessons learned
        lesson_constraints = _extract_lessons_constraints(pm["content"])
        for i, text in enumerate(lesson_constraints):
            c_id = f"{pm['id']}-C{i + 1}"

            g.query(
                """
                MERGE (c:Constraint {id: $id})
                SET c.description = $description,
                    c.type = 'OPERATIONAL',
                    c.severity = 'MUST',
                    c.isActive = true,
                    c.extractedAt = $date,
                    c.lastValidatedAt = $date,
                    c.source = 'POSTMORTEM'
                """,
                {
                    "id": c_id,
                    "description": text,
                    "date": pm["date"],
                },
            )

            # PostMortem -> PRODUCED -> Constraint
            g.query(
                """
                MATCH (pm:PostMortem {id: $pmId})
                MATCH (c:Constraint {id: $cId})
                MERGE (pm)-[:PRODUCED]->(c)
                """,
                {"pmId": pm["id"], "cId": c_id},
            )

            # Constraint -> APPLIES_TO -> affected services
            for service_name in pm["affected_services"]:
                g.query(
                    """
                    MATCH (c:Constraint {id: $cId})
                    MATCH (s:Service {name: $serviceName})
                    MERGE (c)-[:APPLIES_TO]->(s)
                    """,
                    {"cId": c_id, "serviceName": service_name},
                )

            constraint_count += 1

    # Detect and create Pattern nodes
    patterns = _detect_patterns(postmortems)
    for pat in patterns:
        g.query(
            """
            MERGE (p:Pattern {id: $id})
            SET p.description = $description,
                p.occurrenceCount = $count
            """,
            {
                "id": pat["id"],
                "description": pat["description"],
                "count": pat["occurrenceCount"],
            },
        )

        # Incident -> INSTANCE_OF -> Pattern
        for inc_id in pat["incidents"]:
            g.query(
                """
                MATCH (inc:Incident {id: $incId})
                MATCH (p:Pattern {id: $patId})
                MERGE (inc)-[:INSTANCE_OF]->(p)
                """,
                {"incId": inc_id, "patId": pat["id"]},
            )

        # Pattern -> INVOLVES -> Service
        for svc_name in pat["services"]:
            g.query(
                """
                MATCH (p:Pattern {id: $patId})
                MATCH (s:Service {name: $svcName})
                MERGE (p)-[:INVOLVES]->(s)
                """,
                {"patId": pat["id"], "svcName": svc_name},
            )

    print(f"  ✅ Loaded {len(postmortems)} post-mortems with {constraint_count} constraints")
    print(f"  ✅ Detected {len(patterns)} recurring patterns")
