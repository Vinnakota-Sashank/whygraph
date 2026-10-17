# WhyGraph — The Engineering Decision Memory Agent

> **Track 3: Company Brain** — Graph Hacks by WeMakeDevs × FalkorDB  
> *"The engineering decision memory that stops your team — and your AI agents — from repeating the same costly mistakes."*

---

## 💡 The Problem

Every engineering organization suffers from **organizational amnesia**:

1. **Decisions are buried**: Architectural Decision Records (ADRs) and post-mortems sit in Confluence, Notion, and Google Docs. Nobody reads them when writing code.
2. **Passive search fails**: Tools like Glean or Confluence Search wait for humans to ask questions. But **developers don't know what they don't know** — they don't search *"is Memcached forbidden in checkout?"* before adding a cache layer.
3. **AI agents hallucinate anti-patterns**: Copilot, Cursor, and Devin generate code blindly based on popular GitHub patterns, frequently reintroducing architectures that caused SEV-1 outages six months ago.
4. **CODEOWNERS is broken**: Static files point to people who left the company two years ago or who only manage repo permissions, not the engineers who actually resolve incidents and understand the system.

---

## 🚀 The Solution: WhyGraph

**WhyGraph** models the engineering decisions, active constraints, historical post-mortems, service dependencies, and dynamic contributor signals inside a high-speed **FalkorDB** graph database.

Instead of just answering questions passively, WhyGraph acts as an **active architectural radar**:

- 🚨 **Proactive PR & Agent Guardrail**: Scans proposed code changes against the active constraint graph. If someone attempts to add an unapproved dependency or architecture, WhyGraph flags the violation **and cites the exact ADR and post-mortem outage** where this was tried and failed.
- 🎯 **Dynamic Expertise Ranking**: Calculates who *actually* understands a service right now using multi-signal scoring (commits, PR reviews, incident resolutions, ADR authorship) instead of stale CODEOWNERS files.
- 🧠 **Decision Lineage Q&A**: Answers natural language questions like *"Why do we use Redis instead of Memcached?"* or *"Why can't checkout call payments synchronously?"* with verifiable graph-backed citations.

---

## 📊 Graph Model (Powered by FalkorDB)

WhyGraph leverages FalkorDB's sub-millisecond OpenCypher traversal engine to link organizational context across boundaries:

```mermaid
graph TD
    Person([Person: Sarah Chen]) -->|MEMBER_OF| Team([Team: Platform])
    Person -->|AUTHORED| ADR([ADR-001: Use Redis])
    Person -->|EXPERT_IN {score: 92}| SvcCheckout([Service: checkout-service])
    
    ADR -->|DEFINES| Con([Constraint: No Memcached])
    Con -->|APPLIES_TO| SvcCheckout
    
    DevPR([Simulated PR]) -->|TARGETS| SvcCheckout
    DevPR -.->|VIOLATES| Con
    
    PM([PostMortem: PM-001]) -->|PRODUCED| Con
    PM -->|DOCUMENTS| Inc([Incident: INC-089 SEV-1 Outage])
    Inc -->|AFFECTED| SvcCheckout
    Inc -->|INSTANCE_OF| Pat([Pattern: Connection Pool Exhaustion])
```

### Node Types
- `Person`: Engineers with contact info, team affiliation, and multi-signal metrics.
- `Team`: Engineering teams responsible for specific microservice domains.
- `Service`: Microservices cataloged with language, repository, and dependencies.
- `ADR`: Architectural Decision Records documenting technical mandates.
- `Constraint`: Active, enforceable architectural rules (type: Architectural, Performance, Security).
- `Incident` & `PostMortem`: Documented outages, duration, root causes, and lessons learned.
- `Pattern`: Recurring failure modes identified across multiple incident post-mortems.

---

## ⚡ Why FalkorDB is Compulsory (Not a Sidepiece)

WhyGraph cannot be built with a relational or vector database alone:

1. **Multi-Hop Traversal in < 1ms**: Detecting a violation requires traversing `PR → Service → Constraint → ADR → PostMortem → Incident`. FalkorDB executes this 5-hop query in sub-millisecond time.
2. **Dynamic Traversal over Static Embeddings**: Vector search finds semantically similar words; FalkorDB finds topological relationships (e.g., *"Service A depends on B, which has a constraint produced by an incident in C"*).
3. **Graph Algorithms for Expertise**: Multi-signal scoring blends edges of different types (`COMMITTED_TO`, `REVIEWED`, `RESOLVED_INCIDENT`) with dynamic weights to rank true domain specialists.

---

## 🌟 Core Capabilities Demonstrated

### 1. PR Architectural Radar (The Killer Feature)
- Run a simulated PR adding `pymemcache` to `checkout-service`.
- WhyGraph traverses the graph and returns:
  - ⚠️ **VIOLATION**: *"Memcached is NOT permitted in any service"*
  - **Source**: ADR-001 (Authored by Sarah Chen)
  - **Historical Outage Evidence**: INC-089 SEV-1 Outage (135 min downtime caused by Memcached connection saturation)
  - **Assigned Reviewers**: Top experts David Kumar (Score: 87) & Sarah Chen (Score: 72)

### 2. Dynamic Expertise Ranking
- Replaces obsolete `CODEOWNERS` files with live, multi-signal scores:
  - Commits: 1.0 pt
  - PR Reviews: 0.5 pt
  - Incident Resolutions: 10.0 pts (deep operational awareness)
  - ADRs/Docs Authored: 3.0 pts

### 3. Decision Lineage Q&A
- Query: *"Why do we use Redis instead of Memcached?"*
- Response cites ADR-001 reasons (data structures, persistence, pub/sub) and links to the post-mortem outage proof.

---

## 🛠️ Tech Stack

- **Graph Database**: FalkorDB (OpenCypher, Redis graph protocol)
- **Backend**: Python 3.10+, FastAPI, Pydantic, Uvicorn
- **AI & Reasoning**: LangChain + Google Gemini API (`gemini-2.0-flash`) with fallback deterministic rule evaluation
- **Frontend**: Vanilla HTML5, CSS3 Glassmorphism dark mode, Vanilla JavaScript (zero framework bloat)

---

## 🚀 Quick Start Guide

### 1. Run FalkorDB
```bash
docker run -p 6379:6379 -it --rm falkordb/falkordb:latest
```

### 2. Install Dependencies
```bash
cd whygraph
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Optional: Add your `GOOGLE_API_KEY` for natural language LLM generation. If omitted, WhyGraph operates with full deterministic Cypher graph reasoning!)*

### 4. Initialize & Populate the Knowledge Graph
```bash
python scripts/setup_graph.py
```
This loads the sample organizational hierarchy, microservice topologies, ADRs, post-mortems, and builds the schema indexes in FalkorDB.

### 5. Run the Interactive Web Application
```bash
uvicorn backend.main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to experience the UI.

### 6. Run the CLI Demo Simulation
```bash
python scripts/demo_violation.py
```

### 7. Run as a GitHub Actions CI Check
WhyGraph integrates directly into GitHub Actions to block breaking PRs automatically:
```bash
python scripts/github_action_check.py --service checkout-service --deps pymemcache --files services/checkout/cache.py
```

### 8. Run as an MCP Server (Cursor IDE & Claude Desktop)
Let AI coding agents query company post-mortems and constraints before generating code:
```bash
python mcp/server.py
```
Add to your `cursor.json` or Claude Desktop configuration:
```json
{
  "mcpServers": {
    "whygraph": {
      "command": "python",
      "args": ["c:/path/to/whygraph/mcp/server.py"]
    }
  }
}
```

---

## 📁 Repository Structure

```
whygraph/
├── README.md                    # Hackathon documentation
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment config template
│
├── data/                        # Demo knowledge assets
│   ├── adrs/                    # Markdown ADR documents with YAML frontmatter
│   ├── postmortems/             # Post-mortem incident documents
│   ├── org.json                 # People, teams, and multi-signal metrics
│   └── services.json            # Microservice topology and dependencies
│
├── backend/
│   ├── main.py                  # FastAPI app & static file mounting
│   ├── config.py                # Environment and path configurations
│   ├── graph/
│   │   ├── connection.py        # FalkorDB connection singleton
│   │   ├── schema.py            # Node index initialization
│   │   └── queries.py           # Centralized Cypher query catalog
│   ├── ingest/
│   │   ├── adr_parser.py        # ADR markdown → graph nodes & constraints
│   │   ├── postmortem_parser.py # Outage markdown → Incidents & patterns
│   │   ├── org_loader.py        # People & expertise signals loader
│   │   └── service_loader.py    # Service topology & module loader
│   ├── agent/
│   │   ├── violation_checker.py # Graph traversal PR constraint engine
│   │   ├── expertise_finder.py  # Multi-signal expertise ranker
│   │   └── chat.py              # LLM + Graph Cypher Q&A agent
│   └── api/
│       └── routes.py            # REST endpoints
│
├── .github/
│   └── workflows/
│       └── whygraph-radar.yml   # GitHub Actions PR guardrail
│
├── mcp/
│   └── server.py                # Model Context Protocol server (Cursor / Claude)
│
├── frontend/
│   ├── index.html               # Glassmorphic single-page app
│   ├── style.css                # Modern dark-mode styling & animations
│   └── app.js                   # UI state, presets, and API integration
│
└── scripts/
    ├── setup_graph.py           # One-shot database builder & indexer
    ├── demo_violation.py        # Terminal demo of the 3 scenarios
    └── github_action_check.py   # CI/CD PR audit & comment generator
```

---

## 🏆 Hackathon Alignment: Track 3 (Company Brain)

| Hackathon Requirement | WhyGraph Implementation |
|---|---|
| **Knowledge from docs, tickets, chats in one graph** | Ingests ADRs, Post-Mortems, org charts, and service maps into a unified FalkorDB graph |
| **Who owns what, and who knows what** | Dynamic multi-signal expertise scoring replacing static `CODEOWNERS` |
| **Tracing decisions back to their source** | Sub-millisecond graph traversal from PR changes back to ADRs, authors, and outage incidents |
| **Keeping knowledge current** | Post-mortems automatically produce new active constraints to prevent repeat incidents |
| **Answers with clear sources** | Every recommendation and violation check explicitly cites ADR IDs, author names, and incident evidence |
