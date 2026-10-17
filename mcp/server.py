"""
WhyGraph — Model Context Protocol (MCP) Server

Exposes the FalkorDB Engineering Decision Memory directly to AI agents:
- Cursor IDE
- Claude Desktop
- GitHub Copilot
- Windsurf

Prevents AI coding agents from generating code that violates company architecture
or repeats past SEV-1 outage patterns.
"""

import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.violation_checker import check_violations
from backend.agent.expertise_finder import find_experts
from backend.agent.chat import chat
from backend.graph.connection import get_graph
from backend.graph import queries

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("WhyGraph-Company-Brain")

    @mcp.tool()
    def check_architectural_violations(
        service_name: str,
        new_dependencies: list[str] = [],
        changed_files: list[str] = []
    ) -> str:
        """
        Check if proposed code changes or package additions violate active team ADRs or cause past outage regressions.
        Call this tool BEFORE generating new imports, caching layers, database connectors, or inter-service calls.
        """
        result = check_violations(
            changed_services=[service_name],
            new_dependencies=new_dependencies if new_dependencies else None,
            changed_files=changed_files if changed_files else None,
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_service_experts(service_name: str) -> str:
        """
        Find the top domain engineers who actually know a service based on live commit, review, and incident resolution signals.
        Use this to know who to tag for architectural review.
        """
        result = find_experts(service_name=service_name)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def query_decision_memory(question: str) -> str:
        """
        Ask WhyGraph why an architectural choice was made (e.g. 'Why Redis instead of Memcached in checkout?').
        Returns answers with explicit ADR and post-mortem citations.
        """
        return chat(question)

    if __name__ == "__main__":
        mcp.run()

except ImportError:
    # Fallback if mcp library is running in another environment
    def main():
        print("WhyGraph MCP Server requires 'mcp' package: pip install mcp")

    if __name__ == "__main__":
        main()
