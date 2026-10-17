"""
High-Fidelity In-Memory FalkorDB Graph Engine
Provides zero-setup OpenCypher graph execution for development and demo environments
when a local Docker daemon or FalkorDB instance is not active.
"""

import os
import json
from typing import Any, Dict, List, Optional, Set
from backend.config import config


class QueryResult:
    """Emulates falkordb.QueryResult."""
    def __init__(self, result_set: List[List[Any]]):
        self.result_set = result_set


class InMemoryNode:
    def __init__(self, key: str, label: str, properties: Dict[str, Any]):
        self.key = key
        self.labels: Set[str] = {label}
        self.properties: Dict[str, Any] = properties

    def __getitem__(self, item):
        return self.properties.get(item)


class InMemoryEdge:
    def __init__(self, rel_type: str, start_key: str, end_key: str, properties: Dict[str, Any]):
        self.type = rel_type
        self.start_key = start_key
        self.end_key = end_key
        self.properties: Dict[str, Any] = properties


class InMemoryFalkorGraph:
    """
    Self-contained graph store with query handling matching FalkorDB's result format.
    Persists state to data/graph_state.json across processes.
    """
    def __init__(self, name: str = "whygraph"):
        self.name = name
        self.nodes: Dict[str, InMemoryNode] = {}
        self.edges: List[InMemoryEdge] = []
        self._state_file = os.path.join(config.DATA_DIR, "graph_state.json")
        self.load_state()

    def save_state(self):
        """Persist current graph nodes and edges to disk."""
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            data = {
                "nodes": [
                    {
                        "key": n.key,
                        "label": list(n.labels)[0] if n.labels else "Entity",
                        "properties": n.properties,
                    }
                    for n in self.nodes.values()
                ],
                "edges": [
                    {
                        "type": e.type,
                        "start_key": e.start_key,
                        "end_key": e.end_key,
                        "properties": e.properties,
                    }
                    for e in self.edges
                ],
            }
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_state(self) -> bool:
        """Load graph state from disk if available."""
        if not os.path.isfile(self._state_file):
            return False
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.nodes.clear()
            for item in data.get("nodes", []):
                node = InMemoryNode(item["key"], item["label"], item["properties"])
                self.nodes[item["key"]] = node
            self.edges.clear()
            for item in data.get("edges", []):
                edge = InMemoryEdge(item["type"], item["start_key"], item["end_key"], item["properties"])
                self.edges.append(edge)
            return len(self.nodes) > 0
        except Exception:
            return False

    def delete(self):
        self.nodes.clear()
        self.edges.clear()
        if os.path.isfile(self._state_file):
            try:
                os.remove(self._state_file)
            except Exception:
                pass

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        cypher_clean = " ".join(cypher.strip().split())
        p = params or {}

        # ── 1. Clear / Reset Graph ───────────────────────────────────────────
        if "DETACH DELETE" in cypher:
            self.nodes.clear()
            self.edges.clear()
            return QueryResult([])

        # ── 2. Schema Indexes ────────────────────────────────────────────────
        if cypher_clean.startswith("CREATE INDEX"):
            return QueryResult([])

        # ── 3. Team Merge ────────────────────────────────────────────────────
        if "MERGE (t:Team {name: $name})" in cypher:
            name = p.get("name")
            key = f"Team:{name}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="Team",
                properties={"name": name, "lead": p.get("lead"), "domain": p.get("domain")},
            )
            return QueryResult([])

        # ── 4. Person Merge ──────────────────────────────────────────────────
        if "MERGE (p:Person {email: $email})" in cypher:
            email = p.get("email")
            key = f"Person:{email}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="Person",
                properties={
                    "email": email,
                    "name": p.get("name"),
                    "role": p.get("role"),
                    "team": p.get("team"),
                    "isActive": True,
                    "githubHandle": p.get("githubHandle", ""),
                    "slackId": p.get("slackId", ""),
                },
            )
            return QueryResult([])

        # ── 5. Person MEMBER_OF Team ─────────────────────────────────────────
        if "MERGE (p)-[:MEMBER_OF]->(t)" in cypher:
            p_key = f"Person:{p.get('email')}"
            t_key = f"Team:{p.get('team')}"
            self.edges.append(InMemoryEdge("MEMBER_OF", p_key, t_key, {}))
            return QueryResult([])

        # ── 6. Service Merge ─────────────────────────────────────────────────
        if "MERGE (s:Service {name: $name})" in cypher:
            name = p.get("name")
            key = f"Service:{name}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="Service",
                properties={
                    "name": name,
                    "repo": p.get("repo", ""),
                    "language": p.get("language", ""),
                    "description": p.get("description", ""),
                },
            )
            return QueryResult([])

        # ── 7. Team RESPONSIBLE_FOR Service ──────────────────────────────────
        if "MERGE (t)-[:RESPONSIBLE_FOR]->(s)" in cypher:
            t_key = f"Team:{p.get('team')}"
            s_key = f"Service:{p.get('service')}"
            self.edges.append(InMemoryEdge("RESPONSIBLE_FOR", t_key, s_key, {}))
            return QueryResult([])

        # ── 8. Person EXPERT_IN Service ──────────────────────────────────────
        if "EXPERT_IN" in cypher and "MERGE" in cypher:
            p_key = f"Person:{p.get('email')}"
            svc_name = p.get("serviceName") or p.get("service")
            s_key = f"Service:{svc_name}"
            self.edges.append(
                InMemoryEdge(
                    "EXPERT_IN",
                    p_key,
                    s_key,
                    {
                        "score": p.get("score", 0),
                        "commits": p.get("commits", 0),
                        "reviews": p.get("reviews", 0),
                        "incidents_resolved": p.get("incidents_resolved", 0),
                        "docs_authored": p.get("docs_authored", 0),
                    },
                )
            )
            return QueryResult([])

        # ── 9. Service DEPENDS_ON Service ────────────────────────────────────
        if "MERGE (s)-[:DEPENDS_ON]->(d)" in cypher:
            s_key = f"Service:{p.get('service')}"
            d_key = f"Service:{p.get('dependency')}"
            self.edges.append(InMemoryEdge("DEPENDS_ON", s_key, d_key, {}))
            return QueryResult([])

        # ── 10. CodeModule Merge ─────────────────────────────────────────────
        if "MERGE (m:CodeModule" in cypher:
            path = p.get("filePath", "")
            key = f"CodeModule:{path}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="CodeModule",
                properties={"filePath": path, "name": p.get("name", "")},
            )
            s_key = f"Service:{p.get('service')}"
            self.edges.append(InMemoryEdge("PART_OF", key, s_key, {}))
            return QueryResult([])

        # ── 11. ADR Merge ────────────────────────────────────────────────────
        if "MERGE (a:ADR {id: $id})" in cypher:
            id_val = p.get("id")
            key = f"ADR:{id_val}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="ADR",
                properties={
                    "id": id_val,
                    "title": p.get("title", ""),
                    "status": p.get("status", "accepted"),
                    "date": p.get("date", ""),
                    "filePath": p.get("filePath", ""),
                },
            )
            return QueryResult([])

        # ── 12. Person AUTHORED ADR ──────────────────────────────────────────
        if "MERGE (p)-[:AUTHORED]->(a)" in cypher:
            p_key = f"Person:{p.get('email')}"
            a_key = f"ADR:{p.get('id')}"
            self.edges.append(InMemoryEdge("AUTHORED", p_key, a_key, {}))
            return QueryResult([])

        # ── 13. ADR CONSTRAINS Service ───────────────────────────────────────
        if "MERGE (a)-[:CONSTRAINS]->(s)" in cypher:
            a_key = f"ADR:{p.get('id')}"
            s_key = f"Service:{p.get('service')}"
            self.edges.append(InMemoryEdge("CONSTRAINS", a_key, s_key, {}))
            return QueryResult([])

        # ── 14. Constraint Merge ─────────────────────────────────────────────
        if "MERGE (c:Constraint {id: $id})" in cypher:
            id_val = p.get("id")
            key = f"Constraint:{id_val}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="Constraint",
                properties={
                    "id": id_val,
                    "description": p.get("description", ""),
                    "type": p.get("type", "ARCHITECTURAL"),
                    "severity": p.get("severity", "MUST"),
                    "isActive": True,
                    "extractedAt": p.get("date", ""),
                    "lastValidatedAt": p.get("date", ""),
                    "source": p.get("source", "ADR"),
                },
            )
            return QueryResult([])

        # ── 15. ADR DEFINES Constraint ───────────────────────────────────────
        if "MERGE (a)-[:DEFINES]->(c)" in cypher:
            a_key = f"ADR:{p.get('adrId')}"
            c_key = f"Constraint:{p.get('cId')}"
            self.edges.append(InMemoryEdge("DEFINES", a_key, c_key, {}))
            return QueryResult([])

        # ── 16. Constraint APPLIES_TO Service ────────────────────────────────
        if "MERGE (c)-[:APPLIES_TO]->(s)" in cypher:
            c_key = f"Constraint:{p.get('cId')}"
            s_key = f"Service:{p.get('serviceName')}"
            self.edges.append(InMemoryEdge("APPLIES_TO", c_key, s_key, {}))
            return QueryResult([])

        # ── 17. PostMortem Merge ─────────────────────────────────────────────
        if "MERGE (pm:PostMortem {id: $id})" in cypher:
            id_val = p.get("id")
            key = f"PostMortem:{id_val}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="PostMortem",
                properties={
                    "id": id_val,
                    "title": p.get("title", ""),
                    "severity": p.get("severity", "SEV-1"),
                    "date": p.get("date", ""),
                    "duration": p.get("duration", 0),
                    "duration_minutes": p.get("duration", 0),
                    "rootCause": p.get("rootCause", ""),
                    "filePath": p.get("filePath", ""),
                },
            )
            return QueryResult([])

        # ── 18. Incident Merge ───────────────────────────────────────────────
        if "MERGE (inc:Incident {id: $id})" in cypher:
            id_val = p.get("id")
            key = f"Incident:{id_val}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="Incident",
                properties={
                    "id": id_val,
                    "title": p.get("title", ""),
                    "severity": p.get("severity", "SEV-1"),
                    "date": p.get("date", ""),
                    "duration_minutes": p.get("duration", 0),
                },
            )
            return QueryResult([])

        # ── 19. Incident DOCUMENTED_IN PostMortem ────────────────────────────
        if "MERGE (inc)-[:DOCUMENTED_IN]->(pm)" in cypher:
            inc_key = f"Incident:{p.get('incId')}"
            pm_key = f"PostMortem:{p.get('pmId')}"
            self.edges.append(InMemoryEdge("DOCUMENTED_IN", inc_key, pm_key, {}))
            return QueryResult([])

        # ── 20. Incident AFFECTED Service ────────────────────────────────────
        if "MERGE (inc)-[:AFFECTED]->(s)" in cypher:
            inc_key = f"Incident:{p.get('incId')}"
            s_key = f"Service:{p.get('svc')}"
            self.edges.append(InMemoryEdge("AFFECTED", inc_key, s_key, {}))
            return QueryResult([])

        # ── 21. Person WROTE PostMortem ──────────────────────────────────────
        if "MERGE (p)-[:WROTE]->(pm)" in cypher:
            p_key = f"Person:{p.get('email')}"
            pm_key = f"PostMortem:{p.get('id')}"
            self.edges.append(InMemoryEdge("WROTE", p_key, pm_key, {}))
            return QueryResult([])

        # ── 22. Pattern Merge ────────────────────────────────────────────────
        if "MERGE (pat:Pattern {id: $id})" in cypher:
            id_val = p.get("id")
            key = f"Pattern:{id_val}"
            self.nodes[key] = InMemoryNode(
                key=key,
                label="Pattern",
                properties={
                    "id": id_val,
                    "description": p.get("description", ""),
                    "occurrenceCount": p.get("count", 1),
                },
            )
            return QueryResult([])

        # ── 23. Incident INSTANCE_OF Pattern ─────────────────────────────────
        if "MERGE (inc)-[:INSTANCE_OF]->(pat)" in cypher:
            inc_key = f"Incident:{p.get('incId')}"
            pat_key = f"Pattern:{p.get('patId')}"
            self.edges.append(InMemoryEdge("INSTANCE_OF", inc_key, pat_key, {}))
            return QueryResult([])

        # ── 24. PostMortem PRODUCED Constraint ───────────────────────────────
        if "MERGE (pm)-[:PRODUCED]->(c)" in cypher:
            pm_key = f"PostMortem:{p.get('pmId')}"
            c_key = f"Constraint:{p.get('cId')}"
            self.edges.append(InMemoryEdge("PRODUCED", pm_key, c_key, {}))
            return QueryResult([])

        # ── 25. READ: COUNT_NODES ────────────────────────────────────────────
        if "RETURN labels(n)[0] AS label, count(n) AS count" in cypher:
            counts: Dict[str, int] = {}
            for node in self.nodes.values():
                lbl = list(node.labels)[0]
                counts[lbl] = counts.get(lbl, 0) + 1
            res = [[lbl, cnt] for lbl, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
            return QueryResult(res)

        # ── 26. READ: COUNT_RELATIONSHIPS ────────────────────────────────────
        if "RETURN type(r) AS type, count(r) AS count" in cypher:
            counts: Dict[str, int] = {}
            for edge in self.edges:
                counts[edge.type] = counts.get(edge.type, 0) + 1
            res = [[t, cnt] for t, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
            return QueryResult(res)

        # ── 27. READ: FIND_CONSTRAINTS_FOR_SERVICE ───────────────────────────
        if "FIND_CONSTRAINTS_FOR_SERVICE" in cypher or "MATCH (c:Constraint {isActive: true})-[:APPLIES_TO]->(svc:Service" in cypher:
            service_name = p.get("serviceName", "")
            res = []
            target_svc_key = f"Service:{service_name}"

            # Constraints applying to service
            constraint_keys = [
                e.start_key for e in self.edges
                if e.type == "APPLIES_TO" and e.end_key == target_svc_key
            ]

            for c_key in constraint_keys:
                c_node = self.nodes.get(c_key)
                if not c_node or not c_node.properties.get("isActive", True):
                    continue

                # Find source (ADR)
                source_key = next((e.start_key for e in self.edges if e.type == "DEFINES" and e.end_key == c_key), None)
                source_node = self.nodes.get(source_key) if source_key else None
                source_type = "ADR" if source_node else None
                source_id = source_node.properties.get("id") if source_node else None
                source_title = source_node.properties.get("title") if source_node else None

                # Find author of source
                author_name = "Team Architect"
                if source_key:
                    author_key = next((e.start_key for e in self.edges if e.type in ("AUTHORED", "WROTE") and e.end_key == source_key), None)
                    if author_key and author_key in self.nodes:
                        author_name = self.nodes[author_key].properties.get("name", "Team Architect")

                # Find postmortem producer
                pm_key = next((e.start_key for e in self.edges if e.type == "PRODUCED" and e.end_key == c_key), None)
                pm_node = self.nodes.get(pm_key) if pm_key else None
                pm_id = pm_node.properties.get("id") if pm_node else None
                pm_title = pm_node.properties.get("title") if pm_node else None

                # Find incident
                inc_id = None
                inc_sev = None
                if pm_key:
                    inc_key = next((e.start_key for e in self.edges if e.type == "DOCUMENTED_IN" and e.end_key == pm_key), None)
                    inc_node = self.nodes.get(inc_key) if inc_key else None
                    if inc_node:
                        inc_id = inc_node.properties.get("id")
                        inc_sev = inc_node.properties.get("severity")

                # If no PM producer directly, check if an incident affected this service with related PM
                if not pm_id:
                    for e in self.edges:
                        if e.type == "AFFECTED" and e.end_key == target_svc_key:
                            inc_node = self.nodes.get(e.start_key)
                            if inc_node:
                                linked_pm_key = next((e2.end_key for e2 in self.edges if e2.type == "DOCUMENTED_IN" and e2.start_key == e.start_key), None)
                                if linked_pm_key and linked_pm_key in self.nodes:
                                    pm_node = self.nodes[linked_pm_key]
                                    pm_id = pm_node.properties.get("id")
                                    pm_title = pm_node.properties.get("title")
                                    inc_id = inc_node.properties.get("id")
                                    inc_sev = inc_node.properties.get("severity")
                                    break

                res.append([
                    c_node.properties.get("id"),
                    c_node.properties.get("description"),
                    c_node.properties.get("type"),
                    c_node.properties.get("severity"),
                    source_type,
                    source_id,
                    source_title,
                    author_name,
                    pm_id,
                    pm_title,
                    inc_id,
                    inc_sev,
                ])
            return QueryResult(res)

        # ── 28. READ: FIND_EXPERTS_FOR_SERVICE ───────────────────────────────
        if "FIND_EXPERTS_FOR_SERVICE" in cypher or "MATCH (p:Person)-[e:EXPERT_IN]->(svc:Service" in cypher:
            service_name = p.get("serviceName", "")
            target_svc_key = f"Service:{service_name}"
            res = []

            for edge in self.edges:
                if edge.type == "EXPERT_IN" and edge.end_key == target_svc_key:
                    p_node = self.nodes.get(edge.start_key)
                    if p_node:
                        # Find team
                        team_key = next((e.end_key for e in self.edges if e.type == "MEMBER_OF" and e.start_key == edge.start_key), None)
                        team_name = self.nodes[team_key].properties.get("name", "Engineering") if team_key and team_key in self.nodes else p_node.properties.get("team", "")

                        res.append([
                            p_node.properties.get("name"),
                            p_node.properties.get("email"),
                            p_node.properties.get("role"),
                            team_name,
                            edge.properties.get("score", 0),
                            edge.properties.get("commits", 0),
                            edge.properties.get("reviews", 0),
                            edge.properties.get("incidents_resolved", 0),
                            edge.properties.get("docs_authored", 0),
                        ])

            res.sort(key=lambda r: r[4], reverse=True)
            limit = 5
            return QueryResult(res[:limit])

        # ── 29. READ: FIND_DECISION_LINEAGE ──────────────────────────────────
        if "FIND_DECISION_LINEAGE" in cypher or "MATCH (c:Constraint)-[:APPLIES_TO]->(svc:Service" in cypher:
            service_name = p.get("serviceName", "")
            target_svc_key = f"Service:{service_name}"
            res = []

            c_keys = [e.start_key for e in self.edges if e.type == "APPLIES_TO" and e.end_key == target_svc_key]
            for c_key in c_keys:
                c_node = self.nodes.get(c_key)
                if not c_node:
                    continue

                source_key = next((e.start_key for e in self.edges if e.type == "DEFINES" and e.end_key == c_key), None)
                source_node = self.nodes.get(source_key) if source_key else None

                author_name = "Team Architect"
                if source_key:
                    author_key = next((e.start_key for e in self.edges if e.type in ("AUTHORED", "WROTE") and e.end_key == source_key), None)
                    if author_key and author_key in self.nodes:
                        author_name = self.nodes[author_key].properties.get("name", "Team Architect")

                pm_key = next((e.start_key for e in self.edges if e.type == "PRODUCED" and e.end_key == c_key), None)
                pm_node = self.nodes.get(pm_key) if pm_key else None
                pm_title = pm_node.properties.get("title") if pm_node else None

                inc_id = None
                if pm_key:
                    inc_key = next((e.start_key for e in self.edges if e.type == "DOCUMENTED_IN" and e.end_key == pm_key), None)
                    inc_node = self.nodes.get(inc_key) if inc_key else None
                    if inc_node:
                        inc_id = inc_node.properties.get("id")

                res.append([
                    c_node.properties.get("description"),
                    c_node.properties.get("type"),
                    c_node.properties.get("severity"),
                    "ADR" if source_node else "Rule",
                    source_node.properties.get("id") if source_node else "N/A",
                    source_node.properties.get("title") if source_node else "Architecture Standard",
                    source_node.properties.get("date") if source_node else "2026-01-01",
                    author_name,
                    pm_title,
                    inc_id,
                ])
            return QueryResult(res)

        # ── 30. READ: GET_FULL_SERVICE_MAP ───────────────────────────────────
        if "GET_FULL_SERVICE_MAP" in cypher or "MATCH (svc:Service)" in cypher:
            res = []
            for s_key, s_node in self.nodes.items():
                if "Service" not in s_node.labels:
                    continue
                s_name = s_node.properties.get("name")
                team_key = next((e.start_key for e in self.edges if e.type == "RESPONSIBLE_FOR" and e.end_key == s_key), None)
                team_name = self.nodes[team_key].properties.get("name", "Engineering") if team_key and team_key in self.nodes else "Platform"

                deps = [
                    self.nodes[e.end_key].properties.get("name")
                    for e in self.edges
                    if e.type == "DEPENDS_ON" and e.start_key == s_key and e.end_key in self.nodes
                ]

                constraints_count = sum(
                    1 for e in self.edges
                    if e.type == "APPLIES_TO" and e.end_key == s_key
                )

                res.append([s_name, team_name, deps, constraints_count])
            return QueryResult(res)

        # ── 31. READ: Constraints Table Query ────────────────────────────────
        if "MATCH (c:Constraint {isActive: true})" in cypher:
            res = []
            for c_key, c_node in self.nodes.items():
                if "Constraint" not in c_node.labels:
                    continue
                applies_to = [
                    self.nodes[e.end_key].properties.get("name")
                    for e in self.edges
                    if e.type == "APPLIES_TO" and e.start_key == c_key and e.end_key in self.nodes
                ]

                source_key = next((e.start_key for e in self.edges if e.type == "DEFINES" and e.end_key == c_key), None)
                source_node = self.nodes.get(source_key) if source_key else None

                pm_key = next((e.start_key for e in self.edges if e.type == "PRODUCED" and e.end_key == c_key), None)
                pm_node = self.nodes.get(pm_key) if pm_key else None

                res.append([
                    c_node.properties.get("id"),
                    c_node.properties.get("description"),
                    c_node.properties.get("type"),
                    c_node.properties.get("severity"),
                    c_node.properties.get("source", "ADR"),
                    applies_to,
                    source_node.properties.get("id") if source_node else None,
                    source_node.properties.get("title") if source_node else None,
                    pm_node.properties.get("id") if pm_node else None,
                    pm_node.properties.get("title") if pm_node else None,
                ])
            return QueryResult(res)

        # ── 32. READ: Incidents Table Query ──────────────────────────────────
        if "MATCH (inc:Incident)" in cypher:
            res = []
            for inc_key, inc_node in self.nodes.items():
                if "Incident" not in inc_node.labels:
                    continue
                affected = [
                    self.nodes[e.end_key].properties.get("name")
                    for e in self.edges
                    if e.type == "AFFECTED" and e.start_key == inc_key and e.end_key in self.nodes
                ]
                pm_key = next((e.end_key for e in self.edges if e.type == "DOCUMENTED_IN" and e.start_key == inc_key), None)
                pm_node = self.nodes.get(pm_key) if pm_key else None

                pat_key = next((e.end_key for e in self.edges if e.type == "INSTANCE_OF" and e.start_key == inc_key), None)
                pat_node = self.nodes.get(pat_key) if pat_key else None

                res.append([
                    inc_node.properties.get("id"),
                    inc_node.properties.get("title"),
                    inc_node.properties.get("severity"),
                    inc_node.properties.get("date"),
                    inc_node.properties.get("duration_minutes", 0),
                    affected,
                    pm_node.properties.get("id") if pm_node else None,
                    pat_node.properties.get("description") if pat_node else "Cascading Failure",
                ])
            return QueryResult(res)

        # ── 33. READ: Expert Related Incidents ───────────────────────────────
        if "MATCH (p:Person {email: $email})-[:WROTE]->(pm:PostMortem)" in cypher:
            email = p.get("email")
            svc = p.get("serviceName")
            p_key = f"Person:{email}"
            svc_key = f"Service:{svc}"
            res = []

            pm_keys = [e.end_key for e in self.edges if e.type == "WROTE" and e.start_key == p_key]
            for pm_key in pm_keys:
                inc_key = next((e.start_key for e in self.edges if e.type == "DOCUMENTED_IN" and e.end_key == pm_key), None)
                if inc_key and inc_key in self.nodes:
                    is_affected = any(e.type == "AFFECTED" and e.start_key == inc_key and e.end_key == svc_key for e in self.edges)
                    if is_affected:
                        inc_node = self.nodes[inc_key]
                        res.append([
                            inc_node.properties.get("id"),
                            inc_node.properties.get("title"),
                            inc_node.properties.get("severity"),
                        ])
            return QueryResult(res)

        # Default fallback
        return QueryResult([])
