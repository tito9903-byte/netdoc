from __future__ import annotations

from typing import Any, Mapping

from app.services.device_model_builder_service import (
    DeviceModelBuilderService,
    FIELD_LABELS,
)
from app.services.device_type_service import (
    DeviceTypeServiceError,
    build_interface_names,
)


MAX_COMPONENTS_PER_BATCH = 256
MAX_SEQUENCES_PER_BATCH = 24


class ComponentSequenceService(DeviceModelBuilderService):
    """Crea varias secuencias de un mismo componente en una sola operación.

    Los campos comunes (tipo, descripción, PoE, color, etc.) se aplican a todas
    las secuencias, mientras cada línea define su propio patrón, inicio y cantidad.
    El payload completo se envía en una sola solicitud bulk a NetBox.
    """

    @classmethod
    def _sequence_values(
        cls,
        form: Mapping[str, Any],
    ) -> tuple[list[Any], list[Any], list[Any]]:
        patterns = cls._getlist(form, "sequence_pattern")
        starts = cls._getlist(form, "sequence_start")
        counts = cls._getlist(form, "sequence_count")

        # Compatibilidad con formularios y enlaces anteriores a las secuencias.
        if not patterns:
            patterns = cls._getlist(form, "name_pattern")
            starts = cls._getlist(form, "start")
            counts = cls._getlist(form, "count")

        return patterns, starts, counts

    @classmethod
    def _build_sequence_names(
        cls,
        form: Mapping[str, Any],
    ) -> list[tuple[int, str]]:
        patterns, starts, counts = cls._sequence_values(form)
        if not patterns:
            raise DeviceTypeServiceError("Agrega al menos una secuencia.", 400)
        if len(patterns) > MAX_SEQUENCES_PER_BATCH:
            raise DeviceTypeServiceError(
                f"Solo se permiten {MAX_SEQUENCES_PER_BATCH} secuencias por operación.",
                400,
            )
        if not (len(patterns) == len(starts) == len(counts)):
            raise DeviceTypeServiceError(
                "Las líneas de secuencia están incompletas. Revisa patrón, inicio y cantidad.",
                400,
            )

        generated: list[tuple[int, str]] = []
        for row_number, (raw_pattern, raw_start, raw_count) in enumerate(
            zip(patterns, starts, counts),
            start=1,
        ):
            pattern = str(raw_pattern or "").strip()
            if not pattern:
                raise DeviceTypeServiceError(
                    f"Escribe el patrón de la secuencia {row_number}.",
                    400,
                )
            try:
                start = int(str(raw_start if raw_start not in (None, "") else "1"))
                count = int(str(raw_count if raw_count not in (None, "") else "1"))
            except ValueError as exc:
                raise DeviceTypeServiceError(
                    f"El inicio y la cantidad de la secuencia {row_number} deben ser enteros.",
                    400,
                ) from exc

            if count == 1 and "{n" not in pattern:
                names = [pattern]
            else:
                names = build_interface_names(pattern, start=start, count=count)

            generated.extend(
                (start + offset, name)
                for offset, name in enumerate(names)
            )

        if len(generated) > MAX_COMPONENTS_PER_BATCH:
            raise DeviceTypeServiceError(
                f"El total de todas las secuencias no puede superar {MAX_COMPONENTS_PER_BATCH} registros.",
                400,
            )

        normalized_names: set[str] = set()
        duplicates: list[str] = []
        for _, name in generated:
            normalized = name.casefold()
            if normalized in normalized_names:
                duplicates.append(name)
            normalized_names.add(normalized)
        if duplicates:
            preview = ", ".join(duplicates[:5])
            raise DeviceTypeServiceError(
                f"Las secuencias generan nombres duplicados: {preview}.",
                400,
            )

        return generated

    async def create_components(
        self,
        kind: str,
        *,
        device_type_id: int,
        form: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        definition = self.definition(kind)
        generated = self._build_sequence_names(form)

        fields = await self.component_fields(
            definition.key,
            device_type_id=device_type_id,
        )
        common: dict[str, Any] = {}
        for field in fields:
            value = self._coerce_value(form, field)
            if value is None or value == []:
                if field.get("required") and field.get("input_type") != "checkbox":
                    raise DeviceTypeServiceError(
                        f"Completa el campo {field.get('label')}.",
                        400,
                    )
                continue
            common[str(field["name"])] = value

        payload: list[dict[str, Any]] = []
        for sequence_number, name in generated:
            item: dict[str, Any] = {
                "device_type": device_type_id,
                "name": name,
                **common,
            }
            for field_name in ("label", "description"):
                raw_value = item.get(field_name)
                if not isinstance(raw_value, str):
                    continue
                try:
                    item[field_name] = raw_value.format(
                        n=sequence_number,
                        name=name,
                    )
                except (KeyError, ValueError, IndexError) as exc:
                    raise DeviceTypeServiceError(
                        f"El patrón del campo {FIELD_LABELS.get(field_name, field_name)} no es válido.",
                        400,
                    ) from exc
            payload.append(item)

        result = await self.client.request(
            "POST",
            definition.endpoint,
            json_body=payload,
        )
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            return [result]
        raise DeviceTypeServiceError(
            "NetBox creó los componentes, pero devolvió un formato inesperado.",
            502,
        )
