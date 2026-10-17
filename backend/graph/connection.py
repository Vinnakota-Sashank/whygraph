"""
FalkorDB connection manager for WhyGraph.

Connects to a live FalkorDB instance (local Docker or FalkorDB Cloud) if available,
and automatically falls back to the high-fidelity in-memory FalkorDB graph engine
for zero-friction development and demo execution when no database daemon is running.
"""

from backend.config import config
from backend.graph.in_memory_graph import InMemoryFalkorGraph


class GraphConnection:
    """Manages FalkorDB connection and provides the graph instance."""

    _instance = None
    _db = None
    _graph = None
    is_in_memory = False

    @classmethod
    def get_instance(cls) -> "GraphConnection":
        """Singleton pattern — one connection per app lifecycle."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._connect()
            cls._instance._ensure_seeded()
        return cls._instance

    def _ensure_seeded(self):
        """Auto-seed graph if in-memory and empty without circular recursion."""
        if self.is_in_memory and hasattr(self._graph, "nodes") and len(self._graph.nodes) == 0:
            from backend.graph.schema import setup_indexes
            from backend.ingest.org_loader import load_org_data
            from backend.ingest.service_loader import load_service_data
            from backend.ingest.adr_parser import load_adrs
            from backend.ingest.postmortem_parser import load_postmortems

            setup_indexes()
            load_org_data()
            load_service_data()
            load_adrs()
            load_postmortems()
            self.save_state()

    def save_state(self):
        """Persist graph state if in-memory engine is active."""
        if hasattr(self._graph, "save_state"):
            self._graph.save_state()

    def _connect(self):
        """Establish connection to FalkorDB or activate in-memory fallback."""
        try:
            from falkordb import FalkorDB

            kwargs = {
                "host": config.FALKORDB_HOST,
                "port": config.FALKORDB_PORT,
            }
            if config.FALKORDB_PASSWORD:
                kwargs["password"] = config.FALKORDB_PASSWORD

            self._db = FalkorDB(**kwargs)
            # Test connectivity
            self._db.connection.ping()
            self._graph = self._db.select_graph(config.FALKORDB_GRAPH_NAME)
            self.is_in_memory = False
            print(f"  ✅ Connected to live FalkorDB at {config.FALKORDB_HOST}:{config.FALKORDB_PORT}")
            print(f"     Graph: '{config.FALKORDB_GRAPH_NAME}'")
        except Exception as e:
            print(f"  ⚡ Live FalkorDB not detected at {config.FALKORDB_HOST}:{config.FALKORDB_PORT} ({e.__class__.__name__})")
            print("  ⚡ Running in Zero-Setup High-Fidelity In-Memory FalkorDB Mode.")
            print("  💡 Tip: To connect to live FalkorDB, run Docker or set FalkorDB Cloud credentials in .env")
            self._graph = InMemoryFalkorGraph(config.FALKORDB_GRAPH_NAME)
            self.is_in_memory = True

    @property
    def graph(self):
        """Return the graph instance."""
        if self._graph is None:
            self._connect()
        return self._graph

    def query(self, cypher: str, params: dict = None):
        """Execute a Cypher query and return the result."""
        if params:
            return self.graph.query(cypher, params)
        return self.graph.query(cypher)

    def flush(self):
        """Delete all nodes and relationships — use for reset/testing."""
        try:
            if hasattr(self.graph, "delete"):
                self.graph.delete()
            else:
                self.query("MATCH (n) DETACH DELETE n")
            print("  🗑️  Graph flushed")
        except Exception:
            pass


def get_graph() -> GraphConnection:
    """Convenience function to get the graph connection singleton."""
    return GraphConnection.get_instance()
