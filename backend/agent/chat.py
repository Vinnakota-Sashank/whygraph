"""
Chat Agent — Natural language Q&A over the WhyGraph knowledge graph.

Uses LLM to interpret user questions and queries FalkorDB for cited answers.
Falls back to direct Cypher queries when LLM is not available.
"""

import os
from backend.graph.connection import get_graph
from backend.graph import queries
from backend.agent.violation_checker import check_violations
from backend.agent.expertise_finder import find_experts
from backend.config import config


def _call_llm(prompt: str):
    """Invoke the configured LLM with multi-model fallback."""
    if config.LLM_PROVIDER == "google" and config.GOOGLE_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=config.GOOGLE_API_KEY)
        # Try models in order of verified quota availability
        candidate_models = [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-3.8-flash"
        ]
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                # Continue to next candidate model if 429 or 404
                continue

    elif config.LLM_PROVIDER == "openai" and config.OPENAI_API_KEY:
        try:
            import httpx
            headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            }
            res = httpx.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=20.0)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  ⚠️  OpenAI call error: {e}")

    return None


def _get_graph_context() -> str:
    """Build a summary of the graph schema for LLM context."""
    return """
You are WhyGraph, an engineering decision memory agent. You answer questions about:
- WHY technical decisions were made (traced to ADRs and post-mortems)
- WHO knows about specific services (dynamic expertise scoring)
- WHAT constraints exist and whether they're being violated
- WHAT incidents have occurred and what patterns recur

The FalkorDB graph contains these node types:
- Person (name, email, role, team, isActive)
- Team (name, lead, domain)
- Service (name, repo, language, description)
- CodeModule (name, filePath) — PART_OF -> Service
- ADR (id, title, status, date) — CONSTRAINS -> Service
- PostMortem (id, title, severity, date, duration_minutes)
- Incident (id, title, severity, date) — AFFECTED -> Service, DOCUMENTED_IN -> PostMortem
- Constraint (id, description, type, severity, isActive, source) — APPLIES_TO -> Service
- Pattern (id, description, occurrenceCount) — INVOLVES -> Service

Key relationships:
- Person -MEMBER_OF-> Team
- Person -EXPERT_IN-> Service (with score, commits, reviews, incidents_resolved)
- Person -AUTHORED-> ADR
- Person -WROTE-> PostMortem
- Team -RESPONSIBLE_FOR-> Service
- Service -DEPENDS_ON-> Service
- ADR -DEFINES-> Constraint
- PostMortem -PRODUCED-> Constraint
- Incident -INSTANCE_OF-> Pattern

ALWAYS cite your sources (ADR IDs, PostMortem IDs, Person names).
NEVER make up information — if the graph doesn't have it, say so.
"""


def _handle_greeting() -> str:
    """Return friendly, cited introduction to WhyGraph without consuming LLM quota."""
    return """## 👋 Hello! I am WhyGraph

I am your organization's **Engineering Decision Memory Agent**, connected directly to your live **FalkorDB** knowledge graph.

I can help you with:
- 📋 **Decision Lineage**: Trace *why* technical architectures were chosen (e.g. *"Why do we use Redis instead of Memcached?"*)
- 👤 **Dynamic Domain Expertise**: Find out who actually understands a service right now based on commits, reviews, and incident fixes (e.g. *"Who knows about checkout-service?"*)
- 🚨 **PR Violation Checks**: Verify proposed changes before merging (e.g. *"Would adding pymemcache to checkout-service violate any rules?"*)
- 💥 **Outage & Incident History**: Review historical post-mortems and recurrence patterns (e.g. *"Tell me about Incident INC-089"*)

What would you like to explore?"""


def _classify_intent(question: str) -> str:
    """Simple intent classification based on keywords."""
    import re
    q_lower = question.lower().strip()
    clean_q = re.sub(r"[^\w\s]", "", q_lower).strip()

    # Greeting / hello
    if clean_q in ["hello", "hi", "hey", "greetings", "help", "who are you", "what can you do", "yo"]:
        return "greeting"

    # Violation check intent
    if any(kw in q_lower for kw in ["violat", "break", "pr ", "pull request", "change", "add "]):
        if any(kw in q_lower for kw in ["check", "would", "if i", "can i", "safe"]):
            return "violation_check"

    # Expertise intent
    if any(kw in q_lower for kw in ["who knows", "expert", "who should", "who can help", "who owns", "talk to"]):
        return "expertise"

    # Decision lineage intent
    if any(kw in q_lower for kw in ["why do we", "why did we", "why is", "decision", "adr", "reason"]):
        return "decision_lineage"

    # Incident/pattern intent
    if any(kw in q_lower for kw in ["incident", "outage", "postmortem", "post-mortem", "pattern", "recur"]):
        return "incidents"

    # Constraint listing
    if any(kw in q_lower for kw in ["constraint", "rule", "not allowed", "prohibited", "must not"]):
        return "constraints"

    # General service info
    if any(kw in q_lower for kw in ["service", "what does", "about", "overview"]):
        return "service_info"

    return "general"


def _extract_service_name(question: str) -> str:
    """Dynamically extract service name from question by matching against all actual services in FalkorDB."""
    q_lower = question.lower()
    try:
        g = get_graph()
        res = g.query("MATCH (s:Service) RETURN s.name")
        all_services = [row[0] for row in res.result_set] if res.result_set else []
    except Exception:
        all_services = []

    if not all_services:
        all_services = [
            "checkout-service", "payment-service", "user-service",
            "inventory-service", "order-service", "analytics-service",
        ]

    # Check exact service name or base name
    for svc in all_services:
        base = svc.replace("-service", "").replace("_service", "")
        if svc.lower() in q_lower or (len(base) >= 3 and base.lower() in q_lower):
            return svc

    return None


def _handle_decision_lineage(service_name: str) -> str:
    """Query and format decision lineage for a service."""
    g = get_graph()
    result = g.query(queries.FIND_DECISION_LINEAGE, {"serviceName": service_name})

    if not result.result_set:
        return f"No documented decisions found for **{service_name}** in the graph."

    lines = [f"## Decision History for `{service_name}`\n"]

    for row in result.result_set:
        constraint = row[0]
        source_type = row[3]
        source_id = row[4]
        source_title = row[5]
        date = row[6]
        author = row[7]
        pm_title = row[8]
        incident = row[9]

        lines.append(f"### 📋 {source_type}: {source_id} — {source_title}")
        if date:
            lines.append(f"**Date**: {date}")
        if author:
            lines.append(f"**Author**: {author}")
        lines.append(f"**Constraint**: {constraint}")
        lines.append(f"**Severity**: {row[2]}")

        if pm_title:
            lines.append(f"\n⚠️ **Validated by incident**: {pm_title} ({incident})")

        lines.append("")

    return "\n".join(lines)


def _handle_constraints(service_name: str) -> str:
    """Query and format all active constraints for a service."""
    g = get_graph()
    result = g.query(queries.FIND_CONSTRAINTS_FOR_SERVICE, {"serviceName": service_name})

    if not result.result_set:
        return f"No active constraints found for **{service_name}**."

    lines = [f"## Active Constraints for `{service_name}`\n"]
    lines.append("| # | Constraint | Severity | Source | Author |")
    lines.append("|---|---|---|---|---|")

    for i, row in enumerate(result.result_set):
        lines.append(
            f"| {i+1} | {row[1]} | **{row[3]}** | {row[4]}:{row[5]} | {row[7] or 'Unknown'} |"
        )

    return "\n".join(lines)


def _handle_expertise(service_name: str) -> str:
    """Format expertise results for display."""
    result = find_experts(service_name)

    if not result["experts"]:
        return f"No expertise data found for **{service_name}**."

    lines = [f"## Top Experts for `{service_name}`\n"]
    lines.append("| Rank | Name | Team | Role | Score | Commits | Reviews | Incidents |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for exp in result["experts"]:
        lines.append(
            f"| {exp['rank']} | **{exp['name']}** | {exp['team']} | {exp['role']} "
            f"| {exp['score']}/100 | {exp['signals']['commits']} "
            f"| {exp['signals']['reviews']} | {exp['signals']['incidents_resolved']} |"
        )

    # Add incident context
    for exp in result["experts"]:
        if exp.get("related_incidents"):
            lines.append(f"\n> 💡 **{exp['name']}** also authored post-mortems for: "
                        + ", ".join(f"{inc['id']} ({inc['severity']})" for inc in exp["related_incidents"]))

    return "\n".join(lines)


def _handle_incidents(service_name: str) -> str:
    """Query and format incident history for a service."""
    g = get_graph()
    result = g.query(queries.FIND_INCIDENTS_FOR_SERVICE, {"serviceName": service_name})

    if not result.result_set:
        return f"No incidents found for **{service_name}**."

    lines = [f"## Incident History for `{service_name}`\n"]

    for row in result.result_set:
        lines.append(f"### 🚨 {row[0]} — {row[1]}")
        lines.append(f"- **Severity**: {row[2]}")
        lines.append(f"- **Date**: {row[3]}")
        lines.append(f"- **Duration**: {row[4]} minutes")
        if row[5]:
            lines.append(f"- **Post-Mortem**: {row[5]}")
        if row[6]:
            lines.append(f"- **Recurring Pattern**: {row[6]}")
        lines.append("")

    return "\n".join(lines)


def _handle_general_with_llm(question: str):
    """Use LLM with graph context to answer a general question."""
    g = get_graph()

    # Gather relevant context from graph
    context_parts = []

    # Get all services
    svc_result = g.query(queries.GET_FULL_SERVICE_MAP)
    if svc_result.result_set:
        context_parts.append("**Services:**")
        for row in svc_result.result_set:
            context_parts.append(f"- {row[0]} (team: {row[1]}, deps: {row[2]}, constraints: {row[3]})")

    # Get all active constraints
    constraint_result = g.query(
        "MATCH (c:Constraint {isActive: true})-[:APPLIES_TO]->(s:Service) "
        "OPTIONAL MATCH (c)<-[:DEFINES]-(src) "
        "RETURN c.description, c.severity, s.name, labels(src)[0], src.id"
    )
    if constraint_result.result_set:
        context_parts.append("\n**Active Constraints:**")
        for row in constraint_result.result_set:
            context_parts.append(f"- [{row[1]}] {row[0]} (applies to: {row[2]}, source: {row[3]}:{row[4]})")

    # Get patterns
    pattern_result = g.query(queries.FIND_RECURRING_PATTERNS)
    if pattern_result.result_set:
        context_parts.append("\n**Recurring Patterns:**")
        for row in pattern_result.result_set:
            context_parts.append(f"- {row[1]} ({row[2]} occurrences, services: {row[3]})")

    graph_context = "\n".join(context_parts)

    prompt = f"""{_get_graph_context()}

Here is the current state of the organization's FalkorDB knowledge graph:

{graph_context}

User question: {question}

Instructions:
1. If the question relates to the company's architecture, services, ADRs, post-mortems, or people, cite specific graph entities (ADR IDs, PostMortem IDs, Person names, and Service names).
2. If the user asks a general software engineering, system design, or architectural question, explain it clearly and professionally using modern engineering best practices, relating it back to how WhyGraph governs systems.
3. Be helpful, concise, and format your response in clear GitHub-flavored markdown.
"""

    return _call_llm(prompt)


def chat(question: str) -> str:
    """
    Main chat entry point. Classifies intent and routes to appropriate handler.

    Args:
        question: Natural language question from the user

    Returns:
        Markdown-formatted answer with citations
    """
    intent = _classify_intent(question)
    service_name = _extract_service_name(question)

    # Route greeting directly
    if intent == "greeting":
        return _handle_greeting()

    # Route based on intent
    if intent == "expertise" and service_name:
        return _handle_expertise(service_name)

    elif intent == "decision_lineage" and service_name:
        return _handle_decision_lineage(service_name)

    elif intent == "constraints" and service_name:
        return _handle_constraints(service_name)

    elif intent == "incidents" and service_name:
        return _handle_incidents(service_name)

    elif intent == "violation_check":
        # Extract potential service and dependency info
        if service_name:
            # Try to extract a dependency name
            q_lower = question.lower()
            potential_deps = []
            dep_keywords = ["memcached", "pymemcache", "mongodb", "pymongo", "dynamodb", "mysql"]
            for dep in dep_keywords:
                if dep in q_lower:
                    potential_deps.append(dep)

            result = check_violations(
                changed_services=[service_name],
                new_dependencies=potential_deps if potential_deps else None,
            )

            if result["violations"]:
                lines = ["## ⚠️ CONSTRAINT VIOLATION DETECTED\n"]
                for v in result["violations"]:
                    lines.append(f"### 🚫 {v['description'][:80]}")
                    lines.append(f"- **Severity**: {v['severity']}")
                    lines.append(f"- **Source**: {v['source_type']}:{v['source_id']} — {v['source_title']}")
                    lines.append(f"- **Authored by**: {v['author_name']}")
                    lines.append(f"- **Trigger**: {v['trigger_reason']}")
                    lines.append(f"- **Graph Path**: `{v['traversal_path']}`")
                    if v.get("evidence"):
                        ev = v["evidence"]
                        lines.append(f"\n> 🔴 **Incident Evidence**: {ev['postmortem_title']} "
                                    f"({ev['incident_id']}, {ev['incident_severity']})")
                    lines.append("")

                if result["recommended_experts"]:
                    lines.append("### 👤 Recommended Experts to Consult")
                    for exp in result["recommended_experts"][:3]:
                        lines.append(f"- **{exp['name']}** ({exp['team']}, {exp['role']}) — Score: {exp['score']}/100")

                return "\n".join(lines)
            else:
                return f"✅ No constraint violations found for changes to **{service_name}**. {result['constraints_checked']} constraints checked."
        else:
            return "Please specify which service you're changing. Example: 'Would adding memcached to checkout-service violate any rules?'"

    # General question — try LLM, fall back to intelligent architecture overview
    llm_answer = _handle_general_with_llm(question)
    if llm_answer and llm_answer.strip():
        return llm_answer
    else:
        g = get_graph()
        svc_result = g.query("MATCH (s:Service) RETURN s.name, s.language, s.description ORDER BY s.name")
        c_result = g.query("MATCH (c:Constraint {isActive: true}) RETURN c.description, c.severity LIMIT 4")

        lines = [
            "## WhyGraph Architectural Knowledge Base\n",
            "Here is the system architecture recorded in FalkorDB:\n",
            "### ⚙️ Monitored Microservices:"
        ]
        for row in svc_result.result_set:
            lines.append(f"- **`{row[0]}`** ({row[1]}): {row[2]}")

        lines.append("\n### 🛡️ Governing Constraints:")
        for row in c_result.result_set:
            lines.append(f"- `[{row[1]}]` {row[0]}")

        lines.append("\n### 💡 Suggested Questions to Ask:")
        lines.append("- *'Why do we use Redis instead of Memcached in checkout-service?'*")
        lines.append("- *'Why must communication with payment-service be asynchronous?'*")
        lines.append("- *'Who knows about checkout-service?'*")
        return "\n".join(lines)
