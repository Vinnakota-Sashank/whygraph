"""All Cypher query templates for WhyGraph.

Each query is a function returning the Cypher string and expected params.
This keeps all graph logic in one place for easy testing and modification.
"""


# ──────────────────────────────────────────────────────────────────────────────
# CONSTRAINT VIOLATION CHECKS
# ──────────────────────────────────────────────────────────────────────────────

FIND_CONSTRAINTS_FOR_SERVICE = """
    MATCH (c:Constraint {isActive: true})-[:APPLIES_TO]->(svc:Service {name: $serviceName})
    OPTIONAL MATCH (c)<-[:DEFINES]-(source)
    OPTIONAL MATCH (source)<-[:AUTHORED|WROTE]-(author:Person)
    OPTIONAL MATCH (c)<-[:PRODUCED]-(pm:PostMortem)
    OPTIONAL MATCH (inc:Incident)-[:DOCUMENTED_IN]->(pm)
    RETURN c.id AS constraint_id,
           c.description AS description,
           c.type AS type,
           c.severity AS severity,
           labels(source)[0] AS source_type,
           source.id AS source_id,
           source.title AS source_title,
           author.name AS author_name,
           pm.id AS postmortem_id,
           pm.title AS postmortem_title,
           inc.id AS incident_id,
           inc.severity AS incident_severity
"""

FIND_CONSTRAINTS_BY_KEYWORD = """
    MATCH (c:Constraint {isActive: true})
    WHERE toLower(c.description) CONTAINS toLower($keyword)
    MATCH (c)-[:APPLIES_TO]->(svc:Service)
    OPTIONAL MATCH (c)<-[:DEFINES]-(source)
    RETURN c.id AS constraint_id,
           c.description AS description,
           c.severity AS severity,
           svc.name AS service_name,
           labels(source)[0] AS source_type,
           source.id AS source_id,
           source.title AS source_title
"""


# ──────────────────────────────────────────────────────────────────────────────
# EXPERTISE QUERIES
# ──────────────────────────────────────────────────────────────────────────────

FIND_EXPERTS_FOR_SERVICE = """
    MATCH (p:Person)-[e:EXPERT_IN]->(svc:Service {name: $serviceName})
    WHERE p.isActive = true
    OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)
    RETURN p.name AS name,
           p.email AS email,
           p.role AS role,
           t.name AS team,
           e.score AS score,
           e.commits AS commits,
           e.reviews AS reviews,
           e.incidents_resolved AS incidents_resolved,
           e.docs_authored AS docs_authored
    ORDER BY e.score DESC
    LIMIT 5
"""


# ──────────────────────────────────────────────────────────────────────────────
# DECISION LINEAGE QUERIES
# ──────────────────────────────────────────────────────────────────────────────

FIND_ADR_FOR_SERVICE = """
    MATCH (adr:ADR)-[:CONSTRAINS]->(svc:Service {name: $serviceName})
    OPTIONAL MATCH (adr)<-[:AUTHORED]-(author:Person)
    OPTIONAL MATCH (adr)-[:DEFINES]->(c:Constraint {isActive: true})
    RETURN adr.id AS adr_id,
           adr.title AS title,
           adr.status AS status,
           adr.date AS date,
           author.name AS author_name,
           collect(c.description) AS active_constraints
"""

FIND_DECISION_LINEAGE = """
    MATCH (c:Constraint)-[:APPLIES_TO]->(svc:Service {name: $serviceName})
    MATCH (c)<-[:DEFINES]-(source)
    OPTIONAL MATCH (source)<-[:AUTHORED|WROTE]-(author:Person)
    OPTIONAL MATCH (c)<-[:PRODUCED]-(pm:PostMortem)<-[:DOCUMENTED_IN]-(inc:Incident)
    RETURN c.description AS constraint,
           c.type AS type,
           c.severity AS severity,
           labels(source)[0] AS source_type,
           source.id AS source_id,
           source.title AS source_title,
           source.date AS date,
           author.name AS author_name,
           pm.title AS validated_by_postmortem,
           inc.id AS related_incident
    ORDER BY source.date DESC
"""


# ──────────────────────────────────────────────────────────────────────────────
# INCIDENT & PATTERN QUERIES
# ──────────────────────────────────────────────────────────────────────────────

FIND_INCIDENTS_FOR_SERVICE = """
    MATCH (inc:Incident)-[:AFFECTED]->(svc:Service {name: $serviceName})
    OPTIONAL MATCH (inc)-[:DOCUMENTED_IN]->(pm:PostMortem)
    OPTIONAL MATCH (inc)-[:INSTANCE_OF]->(pat:Pattern)
    RETURN inc.id AS incident_id,
           inc.title AS title,
           inc.severity AS severity,
           inc.date AS date,
           inc.duration_minutes AS duration,
           pm.id AS postmortem_id,
           pat.description AS pattern
    ORDER BY inc.date DESC
"""

FIND_RECURRING_PATTERNS = """
    MATCH (pat:Pattern)
    WHERE pat.occurrenceCount >= 2
    MATCH (pat)<-[:INSTANCE_OF]-(inc:Incident)-[:AFFECTED]->(svc:Service)
    RETURN pat.id AS pattern_id,
           pat.description AS description,
           pat.occurrenceCount AS occurrences,
           collect(DISTINCT svc.name) AS affected_services,
           collect(DISTINCT inc.id) AS incident_ids
"""


# ──────────────────────────────────────────────────────────────────────────────
# GRAPH OVERVIEW / STATS
# ──────────────────────────────────────────────────────────────────────────────

COUNT_NODES = """
    MATCH (n)
    RETURN labels(n)[0] AS label, count(n) AS count
    ORDER BY count DESC
"""

COUNT_RELATIONSHIPS = """
    MATCH ()-[r]->()
    RETURN type(r) AS type, count(r) AS count
    ORDER BY count DESC
"""

GET_FULL_SERVICE_MAP = """
    MATCH (svc:Service)
    OPTIONAL MATCH (svc)-[:DEPENDS_ON]->(dep:Service)
    OPTIONAL MATCH (t:Team)-[:RESPONSIBLE_FOR]->(svc)
    OPTIONAL MATCH (c:Constraint {isActive: true})-[:APPLIES_TO]->(svc)
    RETURN svc.name AS service,
           t.name AS team,
           collect(DISTINCT dep.name) AS dependencies,
           count(DISTINCT c) AS active_constraints
"""
