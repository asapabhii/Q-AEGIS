"""Write and read paths for the data model.

Every function here takes an explicit :class:`~sqlalchemy.orm.Session` and does
not commit. Transaction boundaries belong to the caller, which is what lets a
classification row and the audit entry proving it happened be written as one
atomic unit rather than two writes that can half-succeed.

There is no update function for ``classification_metadata``, ``risk_scores``,
``trust_scores``, ``crypto_profiles``, or ``audit_log``, and none should be
added. Those tables are append-only, enforced by database triggers; an update
helper here would be a function whose only possible outcome is a raised
exception.
"""
