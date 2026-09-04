"""Knowledge graph, ``SPEC.md`` 3.11, implements ``PRD.md`` FR-10.

NOT IMPLEMENTED. Scheduled for Phase 4 (``SPEC.md`` Section 7). This package
exists so the module boundary is fixed before code is written; it contains no
logic, stubbed or otherwise.

When built: Neo4j, deliberately kept separate from the relational schema.
Multi-hop relationship queries at depth are a poor fit for SQL joins, and
forcing them into the relational tables would misrepresent how this module is
actually queried. Depends on ``PRD.md`` FR-4 and FR-7 being stable first.

Owner: Abhinav (``WORK_DIVISION.md``).
"""
