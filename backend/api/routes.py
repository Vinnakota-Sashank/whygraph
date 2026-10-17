"""
FastAPI Routes for WhyGraph.

Endpoints:
- POST /api/chat: Natural language Q&A over the engineering decision graph
- POST /api/check-violation: PR & code change architectural constraint checker
- GET  /api/experts/{service_name}: Multi-signal dynamic expertise rankings
- GET  /api/services: List all cataloged services
- GET  /api/constraints: List all active organizational constraints
- GET  /api/incidents: List recorded incidents and post-mortems
- GET  /api/graph/stats: Graph metrics (nodes, edges, breakdown)
- POST /api/ingest: Run or re-run graph ingestion pipeline
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.graph.connection import get_graph
from backend.graph import queries
from backend.graph.schema import setup_indexes
from backend.agent.chat import chat
from backend.agent.violation_checker import check_violations
from backend.agent.expertise_finder import find_experts
from backend.ingest.org_loader import load_org_data
from backend.ingest.service_loader import load_service_data
from backend.ingest.adr_parser import load_adrs
from backend.ingest.postmortem_parser import load_postmortems
from backend.ingest.unstructured_loader import ingest_unstructured_text
from backend.config import config

router = APIRouter(prefix="/api")


# ── Request / Response Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., example="Why do we use Redis instead of Memcached in checkout-service?")


class ChatResponse(BaseModel):
    reply: str


class ViolationCheckRequest(BaseModel):
    changed_services: List[str] = Field(..., example=["checkout-service"])
    new_dependencies: Optional[List[str]] = Field(default=None, example=["pymemcache"])
    changed_files: Optional[List[str]] = Field(default=None, example=["services/checkout/cache.py"])


class UnstructuredIngestRequest(BaseModel):
    text: str = Field(..., example="INCIDENT POST-MORTEM INC-105: Kafka Consumer Hang in analytics-service...")
    source_label: Optional[str] = Field(default="manual_entry")


class AIGuardrailRequest(BaseModel):
    prompt: str = Field(..., example="Write a caching utility for checkout-service to store cart items.")
    target_service: str = Field(default="checkout-service")


class SlackAlertRequest(BaseModel):
    service_name: str = Field(default="checkout-service")
    violation_data: dict = Field(...)


# ── Chat Endpoint ─────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    """Ask natural language questions about decisions, architecture, constraints, or expertise."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        reply = chat(payload.message)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")


# ── Violation Check Endpoint ──────────────────────────────────────────────────

@router.post("/check-violation")
async def check_violation_endpoint(payload: ViolationCheckRequest):
    """
    Simulate or verify a Pull Request / commit against all active architectural constraints.
    Returns detected violations, graph lineage back to ADRs/PostMortems, and recommended experts.
    """
    if not payload.changed_services:
        raise HTTPException(status_code=400, detail="At least one changed service must be specified.")
    try:
        result = check_violations(
            changed_services=payload.changed_services,
            new_dependencies=payload.new_dependencies,
            changed_files=payload.changed_files,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Violation check error: {str(e)}")


# ── Expertise Endpoint ────────────────────────────────────────────────────────

@router.get("/experts/{service_name}")
async def get_experts_endpoint(service_name: str, limit: int = 5):
    """Get ranked domain experts for a service based on commits, reviews, incidents, and docs."""
    try:
        result = find_experts(service_name=service_name, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Expertise query error: {str(e)}")


# ── Services Endpoint ─────────────────────────────────────────────────────────

@router.get("/services")
async def list_services():
    """List all registered services, their teams, and dependency relationships."""
    try:
        g = get_graph()
        result = g.query(queries.GET_FULL_SERVICE_MAP)
        services = []
        for row in result.result_set:
            services.append({
                "service": row[0],
                "team": row[1],
                "dependencies": row[2] if row[2] else [],
                "active_constraints_count": row[3],
            })
        return {"services": services}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing services: {str(e)}")


# ── Constraints Endpoint ──────────────────────────────────────────────────────

@router.get("/constraints")
async def list_constraints():
    """List all active organizational constraints with their sources (ADR/Incident)."""
    try:
        g = get_graph()
        cypher = """
            MATCH (c:Constraint {isActive: true})
            OPTIONAL MATCH (c)-[:APPLIES_TO]->(svc:Service)
            OPTIONAL MATCH (c)<-[:DEFINES]-(adr:ADR)
            OPTIONAL MATCH (c)<-[:PRODUCED]-(pm:PostMortem)
            RETURN c.id AS id,
                   c.description AS description,
                   c.type AS type,
                   c.severity AS severity,
                   c.source AS source,
                   collect(DISTINCT svc.name) AS applies_to,
                   adr.id AS adr_id,
                   adr.title AS adr_title,
                   pm.id AS postmortem_id,
                   pm.title AS postmortem_title
            ORDER BY c.severity DESC, c.id ASC
        """
        result = g.query(cypher)
        constraints = []
        for row in result.result_set:
            constraints.append({
                "id": row[0],
                "description": row[1],
                "type": row[2],
                "severity": row[3],
                "source": row[4],
                "applies_to": row[5],
                "adr_id": row[6],
                "adr_title": row[7],
                "postmortem_id": row[8],
                "postmortem_title": row[9],
            })
        return {"constraints": constraints}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying constraints: {str(e)}")


# ── Incidents Endpoint ────────────────────────────────────────────────────────

@router.get("/incidents")
async def list_incidents():
    """List all documented incidents, affected services, and associated post-mortems."""
    try:
        g = get_graph()
        cypher = """
            MATCH (inc:Incident)
            OPTIONAL MATCH (inc)-[:AFFECTED]->(svc:Service)
            OPTIONAL MATCH (inc)-[:DOCUMENTED_IN]->(pm:PostMortem)
            OPTIONAL MATCH (inc)-[:INSTANCE_OF]->(pat:Pattern)
            RETURN inc.id AS incident_id,
                   inc.title AS title,
                   inc.severity AS severity,
                   inc.date AS date,
                   inc.duration_minutes AS duration_minutes,
                   collect(DISTINCT svc.name) AS affected_services,
                   pm.id AS postmortem_id,
                   pat.description AS pattern
            ORDER BY inc.date DESC
        """
        result = g.query(cypher)
        incidents = []
        for row in result.result_set:
            incidents.append({
                "id": row[0],
                "title": row[1],
                "severity": row[2],
                "date": row[3],
                "duration_minutes": row[4],
                "affected_services": row[5],
                "postmortem_id": row[6],
                "pattern": row[7],
            })
        return {"incidents": incidents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying incidents: {str(e)}")


# ── Graph Overview / Stats Endpoint ───────────────────────────────────────────

@router.get("/graph/stats")
async def get_graph_stats():
    """Retrieve node counts, relationship counts, and health overview of the graph."""
    try:
        g = get_graph()
        node_result = g.query(queries.COUNT_NODES)
        rel_result = g.query(queries.COUNT_RELATIONSHIPS)

        nodes = {row[0]: row[1] for row in node_result.result_set if row[0] is not None}
        relationships = {row[0]: row[1] for row in rel_result.result_set if row[0] is not None}

        total_nodes = sum(nodes.values())
        total_rels = sum(relationships.values())

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "nodes_by_label": nodes,
            "relationships_by_type": relationships,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving graph stats: {str(e)}")


# ── Ingestion Trigger Endpoint ────────────────────────────────────────────────

@router.post("/ingest")
async def run_ingestion():
    """One-click graph rebuild: sets up schema indexes and populates all sample data."""
    try:
        setup_indexes()
        load_org_data()
        load_service_data()
        load_adrs()
        load_postmortems()
        return {"status": "SUCCESS", "message": "Graph successfully ingested."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


# ── Graph Visualization Topology Endpoint ─────────────────────────────────────

@router.get("/graph/visualization")
async def get_graph_visualization():
    """
    Retrieve full graph topology formatted for live interactive Canvas rendering.
    Assigns visual colors, sizes, icons, and edge relationships.
    """
    try:
        g = get_graph()
        node_query = """
            MATCH (n)
            RETURN id(n) AS uid,
                   labels(n)[0] AS label,
                   coalesce(n.id, n.name, labels(n)[0]) AS name,
                   coalesce(n.title, n.description, n.role, '') AS subtitle,
                   properties(n) AS props
            LIMIT 150
        """
        node_res = g.query(node_query)

        palette = {
            "Service": {"color": "#06b6d4", "size": 22, "icon": "⚙️", "group": "services"},
            "Constraint": {"color": "#f59e0b", "size": 16, "icon": "🛡️", "group": "constraints"},
            "ADR": {"color": "#8b5cf6", "size": 20, "icon": "📋", "group": "adrs"},
            "PostMortem": {"color": "#f97316", "size": 18, "icon": "📑", "group": "postmortems"},
            "Incident": {"color": "#ef4444", "size": 20, "icon": "💥", "group": "incidents"},
            "Person": {"color": "#10b981", "size": 16, "icon": "👤", "group": "people"},
            "Team": {"color": "#6366f1", "size": 22, "icon": "👥", "group": "teams"},
            "Pattern": {"color": "#ec4899", "size": 18, "icon": "🔁", "group": "patterns"},
            "CodeModule": {"color": "#64748b", "size": 12, "icon": "📁", "group": "code"}
        }

        nodes = []
        node_id_map = {}
        for row in node_res.result_set:
            uid = row[0]
            label = row[1] or "Unknown"
            name = str(row[2])
            subtitle = str(row[3])[:45] if row[3] else ""
            style = palette.get(label, {"color": "#94a3b8", "size": 14, "icon": "⚪", "group": "other"})

            node_obj = {
                "id": str(uid),
                "key": name,
                "label": name,
                "type": label,
                "subtitle": subtitle,
                "color": style["color"],
                "radius": style["size"],
                "icon": style["icon"],
                "group": style["group"],
                "properties": {k: str(v) for k, v in row[4].items()} if isinstance(row[4], dict) else {}
            }
            nodes.append(node_obj)
            node_id_map[uid] = str(uid)

        edge_query = """
            MATCH (s)-[r]->(t)
            RETURN id(s) AS source_uid,
                   id(t) AS target_uid,
                   type(r) AS rel_type,
                   coalesce(s.name, s.id) AS source_name,
                   coalesce(t.name, t.id) AS target_name
            LIMIT 250
        """
        edge_res = g.query(edge_query)
        edges = []
        for row in edge_res.result_set:
            s_uid = row[0]
            t_uid = row[1]
            if s_uid in node_id_map and t_uid in node_id_map:
                edges.append({
                    "id": f"{s_uid}-{row[2]}-{t_uid}",
                    "source": str(s_uid),
                    "target": str(t_uid),
                    "label": row[2],
                    "source_name": str(row[3]),
                    "target_name": str(row[4]),
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph visualization query failed: {str(e)}")


# ── Living Knowledge Ingestion Endpoint ───────────────────────────────────────

@router.post("/ingest/unstructured")
async def ingest_unstructured_endpoint(payload: UnstructuredIngestRequest):
    """
    Ingest unstructured text (Incident post-mortem, ADR, Slack discussion, RFC).
    Uses Gemini to extract entities and constraints, then writes directly into FalkorDB Cloud.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    try:
        result = ingest_unstructured_text(payload.text, payload.source_label or "manual_entry")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unstructured ingestion error: {str(e)}")


# ── AI Coding Agent Guardrail Simulator Endpoint ──────────────────────────────

@router.post("/ai-guardrail/simulate")
async def simulate_ai_guardrail(payload: AIGuardrailRequest):
    """
    Simulate code generation with and without WhyGraph MCP constraint guardrails.
    Demonstrates how WhyGraph intercepts AI coding agents (Cursor/Copilot) to prevent architectural regressions.
    """
    g = get_graph()
    service = payload.target_service
    prompt = payload.prompt.lower()

    res = g.query(queries.FIND_CONSTRAINTS_FOR_SERVICE, {"serviceName": service})
    constraints = [row[1] for row in res.result_set]

    if "cache" in prompt or "memcached" in prompt or "redis" in prompt:
        unguarded_code = (
            "# Generated by Cursor / Copilot (UNGUARDED)\n"
            "import pymemcache.client.base\n\n"
            "class CartCache:\n"
            "    def __init__(self):\n"
            "        # Directly connects to local Memcached\n"
            "        self.client = pymemcache.client.base.Client(('127.0.0.1', 11211))\n\n"
            "    def set_cart(self, user_id: str, items: list):\n"
            "        self.client.set(user_id, items)\n\n"
            "    def get_cart(self, user_id: str):\n"
            "        return self.client.get(user_id)\n"
        )
        guarded_code = (
            "# Generated by Cursor + WhyGraph MCP Guardrail (FalkorDB)\n"
            "import os\n"
            "import json\n"
            "import redis\n\n"
            "# WhyGraph Guard: Enforcing ADR-001 (Shared Redis Cluster & Connection Pooling)\n"
            "REDIS_POOL = redis.ConnectionPool(\n"
            "    host=os.getenv('REDIS_HOST', 'redis-cluster.internal'),\n"
            "    port=6379,\n"
            "    max_connections=20,  # ADR-001: Pool max 20 connections\n"
            "    decode_responses=True\n"
            ")\n\n"
            "class CartCache:\n"
            "    def __init__(self):\n"
            "        self.client = redis.Redis(connection_pool=REDIS_POOL)\n\n"
            "    def set_cart(self, user_id: str, items: list):\n"
            "        # ADR-001: Mandated namespace 'checkout:cart:{id}' & explicit 3600s TTL\n"
            "        key = f'checkout:cart:{user_id}'\n"
            "        self.client.setex(key, 3600, json.dumps(items))\n\n"
            "    def get_cart(self, user_id: str):\n"
            "        key = f'checkout:cart:{user_id}'\n"
            "        data = self.client.get(key)\n"
            "        return json.loads(data) if data else None\n"
        )
        return {
            "prompt": payload.prompt,
            "target_service": service,
            "unguarded": {
                "code": unguarded_code,
                "status": "DANGEROUS",
                "violations": [
                    "Memcached is NOT permitted in any service (ADR-001)",
                    "No key namespacing convention applied (ADR-001)",
                    "No TTL set on cache key (ADR-001)",
                    "No connection pool configured (ADR-001)"
                ],
                "incident_risk": "💥 INC-089 (SEV-1 outage): Memory exhaustion caused 135 minutes of checkout failure."
            },
            "guarded": {
                "code": guarded_code,
                "status": "COMPLIANT",
                "rules_injected": [
                    "ADR-001: MUST use shared Redis cluster with connection pool (5-20 connections)",
                    "ADR-001: Cache key format '{service}:{entity}:{id}'",
                    "ADR-001: Mandatory explicit TTL expiration on all keys"
                ],
                "verified_by": "WhyGraph MCP Server (Sub-millisecond Cypher query)"
            }
        }
    else:
        return {
            "prompt": payload.prompt,
            "target_service": service,
            "unguarded": {
                "code": "# AI code generated without company architectural context\n# Unverified against documented ADRs and outage history.",
                "status": "UNVERIFIED",
                "violations": ["Unverified against company constraints"],
                "incident_risk": "Potential architectural drift or recurring failure"
            },
            "guarded": {
                "code": f"# AI code guarded with {len(constraints)} active constraints from WhyGraph FalkorDB graph.",
                "status": "COMPLIANT",
                "rules_injected": constraints[:3] if constraints else ["No active constraints on service."],
                "verified_by": "WhyGraph MCP Server"
            }
        }


# ── Slack Alert Webhook Simulator Endpoint ────────────────────────────────────

@router.post("/slack/simulate-alert")
async def simulate_slack_alert(payload: SlackAlertRequest):
    """
    Generate interactive Slack Block Kit webhook payload for PR architectural violations.
    Used for enterprise Slack, Teams, and Discord alerting.
    """
    violations = payload.violation_data.get("violations", [])
    service = payload.service_name
    first_viol = violations[0] if violations else {}
    rule = first_viol.get("description", "Architectural constraint violated")
    evidence = first_viol.get("evidence", {})
    experts = payload.violation_data.get("recommended_experts", [])
    top_expert = experts[0] if experts else {"name": "Architecture Team", "score": 90}

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 WhyGraph Alert: Architectural Constraint Violated",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Pull Request #142* proposes changes to *`{service}`* that violate documented engineering standards."
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n`{first_viol.get('severity', 'MUST')}`"},
                {"type": "mrkdwn", "text": f"*Source:*\n{first_viol.get('source_type', 'ADR')}: {first_viol.get('source_id', 'ADR-001')}"},
                {"type": "mrkdwn", "text": f"*Violated Rule:*\n{rule}"},
                {"type": "mrkdwn", "text": f"*Historical Proof:*\n💥 {evidence.get('incident_id', 'INC-089')}: {evidence.get('postmortem_title', 'SEV-1 Outage')}"}
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"👤 *Required Reviewer:* *{top_expert.get('name')}* (Domain Score: *{top_expert.get('score')}/100*)"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Expert Review"},
                    "style": "primary",
                    "value": "request_review"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View WhyGraph Lineage"},
                    "value": "view_graph"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Exception"},
                    "style": "danger",
                    "value": "request_exception"
                }
            ]
        }
    ]

    return {
        "channel": f"#eng-{service.replace('-service', '')}-alerts",
        "blocks": blocks,
        "raw_markdown": f"🚨 *WhyGraph Alert:* PR #142 on `{service}` violated rule: *{rule}*. Historical outage: *{evidence.get('incident_id', 'INC-089')}*. Tagging @{top_expert.get('name')}."
    }


# ── Enterprise Compliance Audit Report Endpoint ───────────────────────────────

@router.get("/compliance/report")
async def get_compliance_report():
    """
    Generate an Executive Architectural Compliance & Bus-Factor Risk Audit.
    Audits services, active ADR constraints, incident mitigations, and key-person risk.
    """
    try:
        g = get_graph()
        svc_res = g.query("""
            MATCH (s:Service)
            OPTIONAL MATCH (c:Constraint {isActive: true})-[:APPLIES_TO]->(s)
            OPTIONAL MATCH (inc:Incident)-[:AFFECTED]->(s)
            OPTIONAL MATCH (p:Person)-[e:EXPERT_IN]->(s)
            RETURN s.name AS service,
                   count(DISTINCT c) AS constraint_count,
                   count(DISTINCT inc) AS incident_count,
                   count(DISTINCT p) AS expert_count,
                   max(e.score) AS top_expert_score
            ORDER BY s.name ASC
        """)

        audit_rows = []
        high_risk_services = []
        for row in svc_res.result_set:
            svc_name = row[0]
            c_cnt = row[1]
            inc_cnt = row[2]
            exp_cnt = row[3]
            top_score = row[4] or 0

            bus_factor = exp_cnt
            risk_level = "LOW"
            risk_reason = "Well documented with strong team redundancy."
            if bus_factor <= 1:
                risk_level = "HIGH"
                risk_reason = "Single Point of Failure (Bus Factor = 1). Knowledge concentrated in one person."
                high_risk_services.append(svc_name)
            elif c_cnt == 0:
                risk_level = "MEDIUM"
                risk_reason = "No active architectural constraints cataloged in graph."

            audit_rows.append({
                "service": svc_name,
                "active_constraints": c_cnt,
                "historical_incidents": inc_cnt,
                "experts_count": exp_cnt,
                "bus_factor": bus_factor,
                "top_expert_score": top_score,
                "risk_level": risk_level,
                "risk_reason": risk_reason
            })

        total_svcs = len(audit_rows)
        compliant_svcs = len([r for r in audit_rows if r["risk_level"] != "HIGH"])
        overall_health = round((compliant_svcs / total_svcs * 100) if total_svcs else 100, 1)

        return {
            "organization": "Enterprise Engineering Org",
            "audit_date": "2026-10-17",
            "overall_health_score": overall_health,
            "total_services_audited": total_svcs,
            "high_risk_services": high_risk_services,
            "services": audit_rows,
            "summary": f"WhyGraph Architectural Audit: {compliant_svcs}/{total_svcs} services meet corporate redundancy and constraint governance standards. {len(high_risk_services)} services have key-personnel bus-factor risk."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance report generation error: {str(e)}")

