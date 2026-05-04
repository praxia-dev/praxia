"""Resource-level access policies (ACL) for enterprise IT departments.

While RBAC (`praxia.auth.rbac`) controls *what actions* a role can take,
PolicyManager controls *which resources* (connector paths, memory namespaces,
prompts, skills) a user or role can read/write.

Designed for the typical enterprise IS-department workflow:

    - Lock down which connector folders are accessible (allow_paths)
    - Block specific paths (deny_paths) — deny wins over allow
    - Restrict which kintone apps / Salesforce sObjects can be queried
    - Restrict which shared-memory blocks can be written
    - All policy decisions are recorded in the audit log

Policies are evaluated in order; first matching policy wins. Default-deny
when `default_decision="deny"`, default-allow otherwise.
"""
from __future__ import annotations

import fnmatch
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Effect = Literal["allow", "deny"]


@dataclass
class ResourcePolicy:
    """A single ACL rule.

    Attributes:
        id: stable UUID
        effect: "allow" or "deny"
        resource_type: "connector" | "memory" | "prompt" | "skill" | "block" | "*"
        resource_pattern: glob-style pattern to match the resource identifier
                          (e.g. "box:/Praxia/*", "kintone:42", "memory:user/alice")
        actions: list of permitted/denied actions ("read", "write", "list", "*")
        principals: list of user_ids or `role:<name>` entries this applies to
                    (use "*" to apply to all)
        description: human-readable description
    """

    id: str
    effect: Effect
    resource_type: str
    resource_pattern: str
    actions: list[str] = field(default_factory=lambda: ["*"])
    principals: list[str] = field(default_factory=lambda: ["*"])
    description: str = ""
    created_at: float = field(default_factory=time.time)
    created_by: str = "admin"


@dataclass
class PolicyDecision:
    allowed: bool
    matched_policy_id: str | None
    reason: str


class PolicyManager:
    """Enterprise resource access policy engine.

    Storage: a single JSONL file at <storage_dir>/policies.jsonl. Append-only
    semantics; deletion rewrites the file (audited).

    Args:
        storage_dir: where policies.jsonl lives (typically .praxia/auth)
        default_decision: "allow" or "deny" when no policy matches
        audit_log: optional AuditLog instance for recording policy decisions
    """

    def __init__(
        self,
        *,
        storage_dir: Path | str = ".praxia/auth",
        default_decision: Effect = "allow",
        audit_log=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "policies.jsonl"
        self.default_decision = default_decision
        self.audit = audit_log

    # --- CRUD --------------------------------------------------------------

    def add(
        self,
        *,
        effect: Effect,
        resource_type: str,
        resource_pattern: str,
        actions: list[str] | None = None,
        principals: list[str] | None = None,
        description: str = "",
        created_by: str = "admin",
    ) -> ResourcePolicy:
        policy = ResourcePolicy(
            id=str(uuid.uuid4()),
            effect=effect,
            resource_type=resource_type,
            resource_pattern=resource_pattern,
            actions=actions or ["*"],
            principals=principals or ["*"],
            description=description,
            created_by=created_by,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(policy), ensure_ascii=False) + "\n")
        if self.audit:
            self.audit.record(
                actor_id=created_by,
                actor_role="admin",
                action="policy.add",
                resource=f"{resource_type}:{resource_pattern}",
                metadata={"effect": effect, "actions": ",".join(policy.actions)},
            )
        return policy

    def list(self) -> list[ResourcePolicy]:
        if not self.path.exists():
            return []
        out: list[ResourcePolicy] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(ResourcePolicy(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return out

    def remove(self, policy_id: str, *, removed_by: str = "admin") -> bool:
        before = self.list()
        after = [p for p in before if p.id != policy_id]
        if len(after) == len(before):
            return False
        with self.path.open("w", encoding="utf-8") as f:
            for p in after:
                f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
        if self.audit:
            self.audit.record(
                actor_id=removed_by,
                actor_role="admin",
                action="policy.remove",
                resource=f"policy:{policy_id}",
            )
        return True

    # --- Evaluation --------------------------------------------------------

    def evaluate(
        self,
        *,
        user_id: str,
        role: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> PolicyDecision:
        """Decide whether `user_id` (with `role`) can perform `action` on `resource_id`.

        Evaluates policies in order; the **first match wins**. Conventionally,
        place specific deny rules first.
        """
        principals_to_check = {user_id, f"role:{role}", "*"}

        for policy in self.list():
            # Resource type must match (or be wildcard)
            if policy.resource_type not in (resource_type, "*"):
                continue
            # Resource pattern must match
            if not fnmatch.fnmatch(resource_id, policy.resource_pattern):
                continue
            # Action must be in the policy's allowed/denied list
            if action not in policy.actions and "*" not in policy.actions:
                continue
            # Principal must match
            if not any(p in principals_to_check for p in policy.principals):
                continue
            decision = PolicyDecision(
                allowed=(policy.effect == "allow"),
                matched_policy_id=policy.id,
                reason=f"matched policy {policy.id} ({policy.effect}: {policy.description or 'no description'})",
            )
            self._audit_decision(user_id, role, resource_type, resource_id, action, decision)
            return decision

        # No policy matched → default
        decision = PolicyDecision(
            allowed=(self.default_decision == "allow"),
            matched_policy_id=None,
            reason=f"no policy matched; default-{self.default_decision}",
        )
        self._audit_decision(user_id, role, resource_type, resource_id, action, decision)
        return decision

    def require(
        self,
        *,
        user_id: str,
        role: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> None:
        """Raise PermissionError if the access is denied."""
        decision = self.evaluate(
            user_id=user_id,
            role=role,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )
        if not decision.allowed:
            raise PermissionError(
                f"Access denied: {action} {resource_type}:{resource_id} for {user_id}/{role}. "
                f"{decision.reason}"
            )

    def _audit_decision(
        self,
        user_id: str,
        role: str,
        resource_type: str,
        resource_id: str,
        action: str,
        decision: PolicyDecision,
    ) -> None:
        if not self.audit:
            return
        self.audit.record(
            actor_id=user_id,
            actor_role=role,
            action=f"policy.eval.{action}",
            resource=f"{resource_type}:{resource_id}",
            outcome="success" if decision.allowed else "denied",
            metadata={"policy_id": decision.matched_policy_id or "none"},
        )
