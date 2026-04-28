from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def ensure_parent(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str | Path, data: Any) -> Path:
    path = ensure_parent(path)
    if hasattr(data, "model_dump"):
        data = data.model_dump(by_alias=True, exclude_none=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path)
    raise ValueError(f"Unsupported table format: {path}")


def write_table(path: str | Path, frame: pd.DataFrame) -> Path:
    path = ensure_parent(path)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame.to_parquet(path, index=False)
    elif suffix == ".csv":
        frame.to_csv(path, index=False)
    elif suffix in {".json", ".jsonl"}:
        frame.to_json(path, orient="records", force_ascii=False, indent=2)
    else:
        raise ValueError(f"Unsupported table format: {path}")
    return path


def normalize_records(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "sources", "news", "filings", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    return []


def collect_text(records: list[dict[str, Any]]) -> tuple[str, list[str]]:
    texts: list[str] = []
    source_ids: list[str] = []
    for record in records:
        for key in ("title", "summary", "text", "notes", "relevant_claims", "management_commentary"):
            value = record.get(key)
            if isinstance(value, list):
                texts.extend(str(item) for item in value)
            elif value:
                texts.append(str(value))
        source_id = record.get("source_id") or record.get("id")
        if source_id:
            source_ids.append(str(source_id))
    return "\n".join(texts), sorted(set(source_ids))


def validate_with_schema(data: Any, schema_path: str | Path) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:  # pragma: no cover - dependency issue
        return [f"jsonschema unavailable: {exc}"]

    schema = read_json(schema_path)
    validator = Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(data), key=str)]
