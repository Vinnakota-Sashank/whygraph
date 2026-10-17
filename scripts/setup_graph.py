"""
WhyGraph — Setup Graph Script
Builds the complete engineering decision graph in FalkorDB from scratch.
"""

import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from backend.graph.connection import get_graph
from backend.graph.schema import setup_indexes
from backend.ingest.org_loader import load_org_data
from backend.ingest.service_loader import load_service_data
from backend.ingest.adr_parser import load_adrs
from backend.ingest.postmortem_parser import load_postmortems
from backend.graph import queries


def run_setup(reset: bool = True):
    print("=" * 65)
    print("  🏗️  WhyGraph — FalkorDB Knowledge Graph Initialization")
    print("=" * 65)

    g = get_graph()

    if reset:
        print("\n[1/6] 🧹 Resetting existing graph...")
        try:
            g.query("MATCH (n) DETACH DELETE n")
            print("  ✅ Previous graph data cleared.")
        except Exception as e:
            print(f"  ⚠️  Note on reset: {e}")

    print("\n[2/6] 📐 Setting up schema indexes...")
    try:
        setup_indexes()
        print("  ✅ Schema indexes created.")
    except Exception as e:
        print(f"  ⚠️  Schema indexes setup note: {e}")

    print("\n[3/6] 👥 Loading organization data (people, teams, expertise)...")
    load_org_data()

    print("\n[4/6] 🧩 Loading microservice topology and code modules...")
    load_service_data()

    print("\n[5/6] 📜 Loading Architectural Decision Records (ADRs) & Constraints...")
    load_adrs()

    print("\n[6/6] 💥 Loading Post-Mortems, Incidents, & Recurring Patterns...")
    load_postmortems()

    # Save state to disk for cross-process persistence
    g.save_state()

    print("\n" + "=" * 65)
    print("  📊 Knowledge Graph Statistics Summary")
    print("=" * 65)
    try:
        node_res = g.query(queries.COUNT_NODES)
        rel_res = g.query(queries.COUNT_RELATIONSHIPS)

        print("\n  🏷️  Nodes in Graph:")
        for r in node_res.result_set:
            if r[0]:
                print(f"    - {r[0]:<16}: {r[1]} nodes")

        print("\n  🔗 Relationships in Graph:")
        for r in rel_res.result_set:
            if r[0]:
                print(f"    - {r[0]:<18}: {r[1]} edges")

        print("\n  ✨ WhyGraph setup successfully finished! Ready for queries.")
    except Exception as e:
        print(f"  ⚠️  Could not fetch stats: {e}")


if __name__ == "__main__":
    run_setup(reset=True)
