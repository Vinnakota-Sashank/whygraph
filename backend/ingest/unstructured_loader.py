"""
Unstructured Knowledge Ingestion Agent for WhyGraph.

Extracts entities, constraints, and relationships from raw documents:
- Architectural Decision Records (ADRs)
- Incident Post-Mortems
- Slack Engineering Incident Discussions
- JIRA / Linear Tickets

Uses Google Gemini to parse semantic entities into structured JSON,
then creates and links nodes in FalkorDB in real time.
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from backend.config import config
from backend.graph.connection import get_graph


EXTRACTION_PROMPT = """
You are WhyGraph's Entity Extraction Agent.
Analyze the following unstructured engineering document (it may be an ADR, an incident post-mortem, a Slack discussion, or an RFC).

Extract structured knowledge according to this JSON schema:
{
  "doc_type": "ADR" | "POSTMORTEM" | "INCIDENT" | "CONSTRAINT",
  "id": "Unique ID like ADR-004, INC-104, or PM-003 (generate one if not in text)",
  "title": "Short descriptive title",
  "author_name": "Full name of the engineer who wrote or led it (or 'Unknown Engineer')",
  "author_team": "checkout | platform | data | frontend (infer best fit)",
  "date": "YYYY-MM-DD (use today's date if not mentioned)",
  "target_services": ["List of exact microservice names like checkout-service, payment-service, analytics-service, order-service, inventory-service, user-service"],
  "severity": "MUST" | "SHOULD" | "SEV-1" | "SEV-2",
  "constraints": [
    {
      "id": "C-XXX",
      "description": "Clear actionable rule (e.g. MUST use Kafka batch consumer with commit-after-write)",
      "type": "PROHIBITED" | "MANDATORY" | "RESTRICTED",
      "severity": "MUST" | "SHOULD",
      "forbidden_keywords": ["list", "of", "trigger", "words"]
    }
  ],
  "incident_meta": {
    "duration_minutes": 60,
    "root_cause": "Brief summary of root cause",
    "recurring_pattern": "Name of pattern like Cascading Failover, Buffer Overflow, or Connection Exhaustion"
  }
}

Document Text:
\"\"\"
{document_text}
\"\"\"

Output ONLY valid JSON. Do not include markdown code block backticks if possible, or use standard ```json.
"""


def _parse_with_gemini(text: str) -> Dict[str, Any]:
    """Parse raw text using Google Gemini."""
    if not config.GOOGLE_API_KEY:
        return _heuristic_fallback_parse(text)

    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-3.8-flash")
        
        prompt = EXTRACTION_PROMPT.replace("{document_text}", text)
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Clean potential codeblock backticks
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\n", "", raw_text)
            raw_text = re.sub(r"\n```$", "", raw_text)
            
        data = json.loads(raw_text)
        return data
    except Exception as e:
        print(f"  ⚠️ Gemini extraction error: {e}. Using heuristic fallback.")
        return _heuristic_fallback_parse(text)


def _heuristic_fallback_parse(text: str) -> Dict[str, Any]:
    """Rule-based parser when LLM is unavailable."""
    is_incident = any(w in text.lower() for w in ["incident", "outage", "post-mortem", "postmortem", "sev-1", "sev-2", "root cause"])
    
    # Extract service mention
    services = []
    known = ["checkout-service", "payment-service", "analytics-service", "order-service", "inventory-service", "user-service"]
    for s in known:
        if s in text.lower() or s.split("-")[0] in text.lower():
            services.append(s)
    if not services:
        services = ["checkout-service"]

    # Extract author
    author = "Senior SRE"
    author_match = re.search(r"(?:author|owner|by|engineer|incident lead)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)", text, re.IGNORECASE)
    if author_match:
        author = author_match.group(1)

    today = datetime.now().strftime("%Y-%m-%d")

    if is_incident:
        inc_id = f"INC-{int(datetime.now().timestamp()) % 1000:03d}"
        return {
            "doc_type": "POSTMORTEM",
            "id": f"PM-{inc_id}",
            "title": text.split("\n")[0][:60] if text else "Incident Resolution",
            "author_name": author,
            "author_team": "platform",
            "date": today,
            "target_services": services,
            "severity": "SEV-1",
            "constraints": [
                {
                    "id": f"C-{inc_id}",
                    "description": f"MUST follow post-mortem guidelines for {services[0]} to avoid recurrence.",
                    "type": "MANDATORY",
                    "severity": "MUST",
                    "forbidden_keywords": ["unbounded", "raw_query"]
                }
            ],
            "incident_meta": {
                "duration_minutes": 45,
                "root_cause": "System bottleneck during peak load",
                "recurring_pattern": "Unbounded Query Spike"
            }
        }
    else:
        adr_id = f"ADR-{int(datetime.now().timestamp()) % 1000:03d}"
        return {
            "doc_type": "ADR",
            "id": adr_id,
            "title": text.split("\n")[0][:60] if text else "Architectural Decision",
            "author_name": author,
            "author_team": "checkout",
            "date": today,
            "target_services": services,
            "severity": "MUST",
            "constraints": [
                {
                    "id": f"C-{adr_id}",
                    "description": f"All modifications to {services[0]} must comply with {adr_id}.",
                    "type": "RESTRICTED",
                    "severity": "MUST",
                    "forbidden_keywords": ["legacy"]
                }
            ],
            "incident_meta": {}
        }


def ingest_unstructured_text(text: str, source_label: str = "manual_entry") -> Dict[str, Any]:
    """
    Parse raw unstructured text, extract entities, and ingest into FalkorDB live.
    """
    g = get_graph()
    parsed = _parse_with_gemini(text)
    
    doc_type = parsed.get("doc_type", "ADR").upper()
    doc_id = parsed.get("id", f"DOC-{int(datetime.now().timestamp()) % 1000}")
    title = parsed.get("title", "Ingested Engineering Document")
    author_name = parsed.get("author_name", "Staff Engineer")
    author_team = parsed.get("author_team", "checkout")
    doc_date = parsed.get("date", datetime.now().strftime("%Y-%m-%d"))
    target_services = parsed.get("target_services", ["checkout-service"])
    constraints = parsed.get("constraints", [])
    
    created_nodes = []
    created_edges = []
    
    # 1. Ensure author Person node exists
    author_id = author_name.lower().replace(" ", ".")
    author_email = f"{author_id}@company.internal"
    
    g.query(
        """
        MERGE (p:Person {name: $name})
        ON CREATE SET p.email = $email, p.role = 'Staff Engineer', p.team = $team, p.isActive = true
        """,
        {"name": author_name, "email": author_email, "team": author_team}
    )
    created_nodes.append(f"Person: {author_name}")
    
    # 2. Ingest document based on type
    if doc_type in ["POSTMORTEM", "INCIDENT"]:
        inc_id = f"INC-{doc_id.replace('PM-', '')}"
        pm_id = f"PM-{inc_id}"
        inc_meta = parsed.get("incident_meta", {})
        duration = inc_meta.get("duration_minutes", 60)
        pattern_name = inc_meta.get("recurring_pattern", "Resource Contention")
        
        # Create PostMortem node
        g.query(
            """
            MERGE (pm:PostMortem {id: $id})
            SET pm.title = $title,
                pm.severity = $severity,
                pm.date = $date,
                pm.duration_minutes = $duration
            """,
            {"id": pm_id, "title": title, "severity": "SEV-1", "date": doc_date, "duration": duration}
        )
        created_nodes.append(f"PostMortem: {pm_id}")
        
        # Link Author to PostMortem
        g.query(
            """
            MATCH (p:Person {name: $author})
            MATCH (pm:PostMortem {id: $pm_id})
            MERGE (p)-[:WROTE]->(pm)
            """,
            {"author": author_name, "pm_id": pm_id}
        )
        created_edges.append(f"{author_name} -WROTE-> {pm_id}")
        
        # Create Incident node
        g.query(
            """
            MERGE (inc:Incident {id: $id})
            SET inc.title = $title,
                inc.severity = $severity,
                inc.date = $date,
                inc.duration_minutes = $duration
            """,
            {"id": inc_id, "title": f"Incident: {title}", "severity": "SEV-1", "date": doc_date, "duration": duration}
        )
        created_nodes.append(f"Incident: {inc_id}")
        
        # Link Incident to PostMortem
        g.query(
            """
            MATCH (inc:Incident {id: $inc_id})
            MATCH (pm:PostMortem {id: $pm_id})
            MERGE (inc)-[:DOCUMENTED_IN]->(pm)
            """,
            {"inc_id": inc_id, "pm_id": pm_id}
        )
        created_edges.append(f"{inc_id} -DOCUMENTED_IN-> {pm_id}")
        
        # Link Incident to Services
        for svc_name in target_services:
            g.query(
                """
                MATCH (inc:Incident {id: $inc_id})
                MERGE (svc:Service {name: $svc_name})
                MERGE (inc)-[:AFFECTED]->(svc)
                """,
                {"inc_id": inc_id, "svc_name": svc_name}
            )
            created_edges.append(f"{inc_id} -AFFECTED-> {svc_name}")
            
        # Create & Link Pattern
        if pattern_name:
            g.query(
                """
                MERGE (pat:Pattern {description: $pat_desc})
                ON CREATE SET pat.id = $pat_id, pat.occurrenceCount = 1
                ON MATCH SET pat.occurrenceCount = pat.occurrenceCount + 1
                WITH pat
                MATCH (inc:Incident {id: $inc_id})
                MERGE (inc)-[:INSTANCE_OF]->(pat)
                """,
                {"pat_desc": pattern_name, "pat_id": f"PAT-{int(datetime.now().timestamp()) % 100}", "inc_id": inc_id}
            )
            created_edges.append(f"{inc_id} -INSTANCE_OF-> {pattern_name}")
            
    else:  # ADR or General Constraint
        # Create ADR node
        g.query(
            """
            MERGE (adr:ADR {id: $id})
            SET adr.title = $title,
                adr.status = 'ACCEPTED',
                adr.date = $date
            """,
            {"id": doc_id, "title": title, "date": doc_date}
        )
        created_nodes.append(f"ADR: {doc_id}")
        
        # Link Author to ADR
        g.query(
            """
            MATCH (p:Person {name: $author})
            MATCH (adr:ADR {id: $adr_id})
            MERGE (p)-[:AUTHORED]->(adr)
            """,
            {"author": author_name, "adr_id": doc_id}
        )
        created_edges.append(f"{author_name} -AUTHORED-> {doc_id}")
        
        # Link ADR to Services
        for svc_name in target_services:
            g.query(
                """
                MATCH (adr:ADR {id: $adr_id})
                MERGE (svc:Service {name: $svc_name})
                MERGE (adr)-[:CONSTRAINS]->(svc)
                """,
                {"adr_id": doc_id, "svc_name": svc_name}
            )
            created_edges.append(f"{doc_id} -CONSTRAINS-> {svc_name}")
            
    # 3. Create and Link Constraints
    for c in constraints:
        c_id = c.get("id") or f"C-{int(datetime.now().timestamp()) % 1000}"
        c_desc = c.get("description", "Architectural rule")
        c_type = c.get("type", "RESTRICTED")
        c_sev = c.get("severity", "MUST")
        
        # Create Constraint Node
        g.query(
            """
            MERGE (c:Constraint {id: $id})
            SET c.description = $desc,
                c.type = $type,
                c.severity = $sev,
                c.isActive = true,
                c.source = $source
            """,
            {"id": c_id, "desc": c_desc, "type": c_type, "sev": c_sev, "source": doc_id}
        )
        created_nodes.append(f"Constraint: {c_id}")
        
        # Link Source Doc -> Constraint
        if doc_type in ["POSTMORTEM", "INCIDENT"]:
            g.query(
                """
                MATCH (pm:PostMortem {id: $pm_id})
                MATCH (c:Constraint {id: $c_id})
                MERGE (pm)-[:PRODUCED]->(c)
                """,
                {"pm_id": f"PM-{doc_id.replace('PM-', '')}", "c_id": c_id}
            )
            created_edges.append(f"PM-{doc_id} -PRODUCED-> {c_id}")
        else:
            g.query(
                """
                MATCH (adr:ADR {id: $adr_id})
                MATCH (c:Constraint {id: $c_id})
                MERGE (adr)-[:DEFINES]->(c)
                """,
                {"adr_id": doc_id, "c_id": c_id}
            )
            created_edges.append(f"{doc_id} -DEFINES-> {c_id}")
            
        # Link Constraint -> Services
        for svc_name in target_services:
            g.query(
                """
                MATCH (c:Constraint {id: $c_id})
                MERGE (svc:Service {name: $svc_name})
                MERGE (c)-[:APPLIES_TO]->(svc)
                """,
                {"c_id": c_id, "svc_name": svc_name}
            )
            created_edges.append(f"{c_id} -APPLIES_TO-> {svc_name}")

    # Persist state if in-memory
    if hasattr(g, "save_state"):
        g.save_state()

    return {
        "status": "SUCCESS",
        "doc_type": doc_type,
        "doc_id": doc_id,
        "title": title,
        "author": author_name,
        "services": target_services,
        "constraints_created": len(constraints),
        "nodes_added": created_nodes,
        "relationships_added": created_edges,
        "message": f"Successfully ingested {doc_type} '{doc_id}' into FalkorDB and linked {len(created_edges)} relationships."
    }
