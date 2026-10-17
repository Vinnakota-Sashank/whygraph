"""Graph schema setup — creates indexes and initial structure in FalkorDB."""

from backend.graph.connection import get_graph


def setup_indexes():
    """Create indexes for fast lookups on commonly queried properties."""
    g = get_graph()

    index_commands = [
        # Person indexes
        "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.email)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.name)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.githubHandle)",

        # Team index
        "CREATE INDEX IF NOT EXISTS FOR (t:Team) ON (t.name)",

        # Service index
        "CREATE INDEX IF NOT EXISTS FOR (s:Service) ON (s.name)",

        # ADR indexes
        "CREATE INDEX IF NOT EXISTS FOR (a:ADR) ON (a.id)",
        "CREATE INDEX IF NOT EXISTS FOR (a:ADR) ON (a.status)",

        # PostMortem indexes
        "CREATE INDEX IF NOT EXISTS FOR (pm:PostMortem) ON (pm.id)",
        "CREATE INDEX IF NOT EXISTS FOR (pm:PostMortem) ON (pm.incident_id)",

        # Constraint indexes
        "CREATE INDEX IF NOT EXISTS FOR (c:Constraint) ON (c.id)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Constraint) ON (c.isActive)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Constraint) ON (c.type)",

        # Incident index
        "CREATE INDEX IF NOT EXISTS FOR (i:Incident) ON (i.id)",

        # Pattern index
        "CREATE INDEX IF NOT EXISTS FOR (pat:Pattern) ON (pat.id)",

        # CodeModule index
        "CREATE INDEX IF NOT EXISTS FOR (m:CodeModule) ON (m.name)",
    ]

    for cmd in index_commands:
        try:
            g.query(cmd)
        except Exception as e:
            # Some indexes may already exist or FalkorDB version may not support IF NOT EXISTS
            print(f"  ⚠️  Index warning (non-fatal): {e}")

    print("✅ Indexes created")


def setup_schema():
    """Initialize the graph schema (indexes only — FalkorDB is schema-optional)."""
    print("\n📐 Setting up WhyGraph schema...")
    setup_indexes()
    print("📐 Schema setup complete\n")
