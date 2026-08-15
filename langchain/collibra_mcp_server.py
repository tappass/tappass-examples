"""Collibra-flavoured metadata MCP server (mock).

Simulates the ~5 highest-value operations a Collibra (or Atlan / data.world)
MCP integration would expose to an LLM agent. The implementations are stubs
that return realistic-looking strings — the point is the *surface*, because
TapPass governs by tool name + argument shape, not by the catalog's actual
state.

This file is meant to be launched as a subprocess over stdio by the
LangChain MCP adapter; it isn't imported directly by the agent.

Tools exposed (matched 1:1 to the recommended OPA rule set):

| Tool                    | Mutating? | Critical arg(s) typically constrained |
|-------------------------|-----------|---------------------------------------|
| list_tables             | no        | (read-only, no constraint needed)     |
| create_table            | yes       | `schema` (allowlist)                  |
| create_column           | yes       | `schema` (allowlist)                  |
| attach_classification   | yes       | `classification` (must be in taxonomy) |
| delete_asset            | yes       | typically `blocked_tools` outright    |
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("collibra-metadata")


@mcp.tool()
def list_tables(schema: str) -> str:
    """List tables in a Collibra schema (read-only)."""
    fixtures = {
        "marketing": ["campaigns", "leads", "events"],
        "sales": ["accounts", "opportunities", "quotes"],
        "finance": ["invoices", "ledger", "payments"],
        "hr": ["employees", "payroll"],
    }
    tables = fixtures.get(schema, [])
    if not tables:
        return f"No tables found in schema '{schema}'."
    return f"Tables in '{schema}': " + ", ".join(tables)


@mcp.tool()
def create_table(schema: str, name: str, description: str = "") -> str:
    """Register a new table under a schema in the Collibra catalog."""
    return (
        f"OK: registered table '{schema}.{name}'"
        + (f" — {description}" if description else "")
    )


@mcp.tool()
def create_column(schema: str, table: str, name: str, data_type: str) -> str:
    """Add a column to an existing table."""
    return f"OK: added column '{name}' ({data_type}) to '{schema}.{table}'"


@mcp.tool()
def attach_classification(asset_id: str, classification: str) -> str:
    """Attach a data-classification tag (PII / Confidential / Public / …) to an asset."""
    return f"OK: tagged '{asset_id}' as {classification}"


@mcp.tool()
def delete_asset(asset_id: str) -> str:
    """Soft-delete an asset from the catalog (destructive)."""
    return f"OK: deleted asset '{asset_id}'"


if __name__ == "__main__":
    mcp.run(transport="stdio")
