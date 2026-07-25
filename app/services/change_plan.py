from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable


_ALLOWED_METHODS = {"POST", "PATCH"}
_SENSITIVE_FRAGMENTS = (
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
)


class ChangePlanError(ValueError):
    """Error de validación de un plan antes de tocar NetBox."""


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower()
    return any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS)


def redact_sensitive(value: Any) -> Any:
    """Devuelve una copia apta para UI, auditoría y logs."""

    if isinstance(value, dict):
        return {
            str(key): "[REDACTADO]" if _is_sensitive_key(key) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


@dataclass(frozen=True)
class ChangeStep:
    """Una operación NetBox ya resuelta y lista para prevalidación."""

    step_id: str
    action: str
    resource: str
    method: str
    endpoint: str
    payload: dict[str, Any] | list[dict[str, Any]]
    summary: str
    required_permission: str
    change_reason: str
    depends_on: tuple[str, ...] = ()
    expected_object_id: int | None = None

    def __post_init__(self) -> None:
        method = self.method.strip().upper()
        endpoint = self.endpoint.strip()

        if not self.step_id.strip():
            raise ChangePlanError("Cada paso debe tener un identificador.")
        if method not in _ALLOWED_METHODS:
            raise ChangePlanError(
                "NetDoc solo permite POST y PATCH dentro de planes automáticos."
            )
        if not endpoint.startswith("/api/") or not endpoint.endswith("/"):
            raise ChangePlanError(
                "El endpoint debe ser una ruta REST de NetBox terminada en '/'."
            )
        if not isinstance(self.payload, (dict, list)):
            raise ChangePlanError("El payload del paso debe ser JSON estructurado.")
        if not self.summary.strip():
            raise ChangePlanError("Cada paso necesita un resumen para el usuario.")
        if not self.required_permission.strip():
            raise ChangePlanError("Cada paso necesita un permiso de NetDoc.")
        if not self.change_reason.strip():
            raise ChangePlanError("Cada escritura necesita una razón de cambio.")

        object.__setattr__(self, "method", method)
        object.__setattr__(self, "endpoint", endpoint)

    def public_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "resource": self.resource,
            "method": self.method,
            "endpoint": self.endpoint,
            "payload": redact_sensitive(self.payload),
            "summary": self.summary,
            "required_permission": self.required_permission,
            "change_reason": self.change_reason,
            "depends_on": list(self.depends_on),
            "expected_object_id": self.expected_object_id,
        }


@dataclass(frozen=True)
class ChangePlan:
    """Contrato entre UI/IA y el futuro ejecutor seguro de NetBox."""

    intent: str
    requested_by: str
    steps: tuple[ChangeStep, ...]
    warnings: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.intent.strip():
            raise ChangePlanError("El plan debe describir la intención del usuario.")
        if not self.requested_by.strip():
            raise ChangePlanError("El plan debe identificar al usuario solicitante.")
        if not self.steps:
            raise ChangePlanError("El plan no contiene operaciones.")
        if len(self.steps) > 50:
            raise ChangePlanError("Un plan no puede superar 50 operaciones.")

        known_ids: set[str] = set()
        for step in self.steps:
            if step.step_id in known_ids:
                raise ChangePlanError(
                    f"El identificador de paso '{step.step_id}' está duplicado."
                )
            missing_dependencies = [
                dependency
                for dependency in step.depends_on
                if dependency not in known_ids
            ]
            if missing_dependencies:
                raise ChangePlanError(
                    "Las dependencias deben referirse a pasos anteriores: "
                    + ", ".join(missing_dependencies)
                )
            known_ids.add(step.step_id)

    @property
    def executable(self) -> bool:
        return not self.questions

    @property
    def fingerprint(self) -> str:
        canonical = {
            "intent": self.intent,
            "requested_by": self.requested_by,
            "steps": [step.public_dict() for step in self.steps],
            "warnings": list(self.warnings),
            "questions": list(self.questions),
            "metadata": redact_sensitive(self.metadata),
        }
        return sha256(_canonical_json(canonical).encode("utf-8")).hexdigest()

    @property
    def confirmation_phrase(self) -> str:
        return f"CONFIRMAR {self.fingerprint[:12].upper()}"

    def public_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.fingerprint,
            "intent": self.intent,
            "requested_by": self.requested_by,
            "steps": [step.public_dict() for step in self.steps],
            "warnings": list(self.warnings),
            "questions": list(self.questions),
            "metadata": redact_sensitive(self.metadata),
            "executable": self.executable,
            "confirmation_phrase": self.confirmation_phrase,
        }


def require_confirmation(plan: ChangePlan, supplied_phrase: str) -> None:
    """Impide ejecutar un plan diferente al que el usuario revisó."""

    if not plan.executable:
        raise ChangePlanError(
            "El plan todavía tiene preguntas pendientes y no puede ejecutarse."
        )
    if supplied_phrase.strip() != plan.confirmation_phrase:
        raise ChangePlanError(
            "La confirmación no coincide con el plan revisado."
        )


def required_permissions(plan: ChangePlan) -> set[str]:
    return {step.required_permission for step in plan.steps}


def iter_public_steps(plan: ChangePlan) -> Iterable[dict[str, Any]]:
    for step in plan.steps:
        yield step.public_dict()
