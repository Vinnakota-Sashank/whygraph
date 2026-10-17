"""Load organization data (people + teams) into the FalkorDB graph."""

import json
from backend.config import config
from backend.graph.connection import get_graph


def _compute_expertise_score(signals: dict) -> int:
    """
    Compute a weighted expertise score from multiple signals.
    
    Weights:
    - commits: 1 point each (direct code contribution)
    - reviews: 0.5 points each (code awareness without authorship)
    - incidents_resolved: 10 points each (deep operational knowledge)
    - docs_authored: 3 points each (knowledge codification)
    
    Score is normalized to 0-100 range.
    """
    raw = (
        signals.get("commits", 0) * 1.0
        + signals.get("reviews", 0) * 0.5
        + signals.get("incidents_resolved", 0) * 10.0
        + signals.get("docs_authored", 0) * 3.0
    )
    # Normalize: cap at 300 raw -> 100 score
    return min(100, int((raw / 300.0) * 100))


def load_org_data():
    """Parse org.json and create Person, Team nodes with relationships."""
    g = get_graph()

    with open(config.ORG_FILE, "r", encoding="utf-8") as f:
        org = json.load(f)

    # Create Team nodes
    for team in org["teams"]:
        g.query(
            """
            MERGE (t:Team {name: $name})
            SET t.lead = $lead,
                t.domain = $domain,
                t.slack_channel = $slack_channel
            """,
            {
                "name": team["name"],
                "lead": team["lead"],
                "domain": team["domain"],
                "slack_channel": team.get("slack_channel", ""),
            },
        )

    print(f"  ✅ Created {len(org['teams'])} Team nodes")

    # Create Person nodes + MEMBER_OF edges
    for person in org["people"]:
        g.query(
            """
            MERGE (p:Person {email: $email})
            SET p.name = $name,
                p.githubHandle = $githubHandle,
                p.slackId = $slackId,
                p.role = $role,
                p.isActive = $isActive
            """,
            {
                "email": person["email"],
                "name": person["name"],
                "githubHandle": person.get("githubHandle", ""),
                "slackId": person.get("slackId", ""),
                "role": person["role"],
                "isActive": person.get("isActive", True),
            },
        )

        # MEMBER_OF edge
        g.query(
            """
            MATCH (p:Person {email: $email})
            MATCH (t:Team {name: $team})
            MERGE (p)-[:MEMBER_OF]->(t)
            """,
            {"email": person["email"], "team": person["team"]},
        )

    print(f"  ✅ Created {len(org['people'])} Person nodes with MEMBER_OF edges")

    # Create EXPERT_IN edges based on expertise signals
    for person in org["people"]:
        for service_name, signals in person.get("expertise_signals", {}).items():
            score = _compute_expertise_score(signals)
            g.query(
                """
                MATCH (p:Person {email: $email})
                MATCH (svc:Service {name: $serviceName})
                MERGE (p)-[e:EXPERT_IN]->(svc)
                SET e.score = $score,
                    e.commits = $commits,
                    e.reviews = $reviews,
                    e.incidents_resolved = $incidents_resolved,
                    e.docs_authored = $docs_authored
                """,
                {
                    "email": person["email"],
                    "serviceName": service_name,
                    "score": score,
                    "commits": signals.get("commits", 0),
                    "reviews": signals.get("reviews", 0),
                    "incidents_resolved": signals.get("incidents_resolved", 0),
                    "docs_authored": signals.get("docs_authored", 0),
                },
            )

    print("  ✅ Created EXPERT_IN edges with computed scores")
