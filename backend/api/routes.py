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
