"""
Expertise Finder — Dynamic expertise ranking using multi-signal scoring.

Unlike static CODEOWNERS files, this queries the graph for expertise edges
that are scored based on commits, reviews, incident responses, and doc authorship.
"""

from backend.graph.connection import get_graph
from backend.graph import queries


def find_experts(service_name: str, limit: int = 5) -> dict:
    """
    Find the top experts for a given service using multi-signal scoring.

    Args:
        service_name: The service to find experts for
        limit: Maximum number of experts to return

    Returns:
        Dict with ranked experts and scoring breakdown
    """
    g = get_graph()

    result = g.query(
        queries.FIND_EXPERTS_FOR_SERVICE,
        {"serviceName": service_name},
    )

    experts = []
    for row in result.result_set:
        experts.append({
            "rank": len(experts) + 1,
            "name": row[0],
            "email": row[1],
            "role": row[2],
            "team": row[3],
            "score": row[4],
            "signals": {
                "commits": row[5],
                "reviews": row[6],
                "incidents_resolved": row[7],
                "docs_authored": row[8],
            },
        })

    # Also find incidents this person was involved in for context
    for expert in experts:
        inc_result = g.query(
            """
            MATCH (p:Person {email: $email})-[:WROTE]->(pm:PostMortem)-[:DOCUMENTS]->(inc:Incident)
            MATCH (inc)-[:AFFECTED]->(svc:Service {name: $serviceName})
            RETURN inc.id, inc.title, inc.severity
            """,
            {"email": expert["email"], "serviceName": service_name},
        )
        expert["related_incidents"] = [
            {"id": r[0], "title": r[1], "severity": r[2]}
            for r in inc_result.result_set
        ]

    return {
        "service": service_name,
        "experts_found": len(experts),
        "experts": experts,
        "scoring_method": {
            "commits": "1 point each (direct code contribution)",
            "reviews": "0.5 points each (code awareness)",
            "incidents_resolved": "10 points each (deep operational knowledge)",
            "docs_authored": "3 points each (knowledge codification)",
            "normalization": "Raw score / 300 * 100, capped at 100",
        },
    }


def find_expert_for_constraint(constraint_id: str) -> dict:
    """Find the person who authored or is most relevant to a specific constraint."""
    g = get_graph()

    result = g.query(
        """
        MATCH (c:Constraint {id: $cId})
        MATCH (c)<-[:DEFINES|PRODUCED]-(source)<-[:AUTHORED|WROTE]-(author:Person)
        OPTIONAL MATCH (author)-[:MEMBER_OF]->(t:Team)
        RETURN author.name, author.email, author.role, t.name,
               labels(source)[0] AS source_type, source.id AS source_id
        """,
        {"cId": constraint_id},
    )

    if result.result_set:
        row = result.result_set[0]
        return {
            "name": row[0],
            "email": row[1],
            "role": row[2],
            "team": row[3],
            "authored_via": f"{row[4]}:{row[5]}",
        }

    return None
