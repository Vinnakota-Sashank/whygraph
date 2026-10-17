"""Load service topology data into the FalkorDB graph."""

import json
from backend.config import config
from backend.graph.connection import get_graph


def load_service_data():
    """Parse services.json and create Service, CodeModule nodes with relationships."""
    g = get_graph()

    with open(config.SERVICES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    services = data["services"]

    # Create Service nodes
    for svc in services:
        g.query(
            """
            MERGE (s:Service {name: $name})
            SET s.repo = $repo,
                s.language = $language,
                s.description = $description
            """,
            {
                "name": svc["name"],
                "repo": svc["repo"],
                "language": svc["language"],
                "description": svc["description"],
            },
        )

        # Team -> RESPONSIBLE_FOR -> Service
        g.query(
            """
            MATCH (t:Team {name: $team})
            MATCH (s:Service {name: $service})
            MERGE (t)-[:RESPONSIBLE_FOR]->(s)
            """,
            {"team": svc["team"], "service": svc["name"]},
        )

        # Create CodeModule nodes
        for module in svc.get("modules", []):
            g.query(
                """
                MERGE (m:CodeModule {name: $name})
                SET m.filePath = $filePath
                """,
                {"name": module["name"], "filePath": module["filePath"]},
            )

            # CodeModule -> PART_OF -> Service
            g.query(
                """
                MATCH (m:CodeModule {name: $moduleName})
                MATCH (s:Service {name: $serviceName})
                MERGE (m)-[:PART_OF]->(s)
                """,
                {"moduleName": module["name"], "serviceName": svc["name"]},
            )

    print(f"  ✅ Created {len(services)} Service nodes with CodeModule children")

    # Create DEPENDS_ON edges (service dependencies)
    for svc in services:
        for dep_name in svc.get("dependencies", []):
            g.query(
                """
                MATCH (s:Service {name: $service})
                MATCH (d:Service {name: $dep})
                MERGE (s)-[:DEPENDS_ON]->(d)
                """,
                {"service": svc["name"], "dep": dep_name},
            )

    print("  ✅ Created service DEPENDS_ON edges")
