"""
Validate file JSON gán tay theo schema/document.schema.json + vài kiểm tra
chéo mà JSON Schema tự nó không diễn đạt được (khớp danh mục topic/org, số
Điều không trùng trong cùng một cha, không tự trích dẫn chính mình).

Dùng độc lập: `python run.py validate [--dir DIR]`
Dùng lại trong graph_model.py: `load_and_validate(path)` — build không bao
giờ nạp một file chưa qua được bước này.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from . import config, normalize


@dataclass
class ValidationResult:
    path: Path
    data: dict | None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.data is not None and not self.errors


def _load_schema() -> dict:
    with open(config.SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_seed_names(path: Path, key: str) -> set[str]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    items = raw.get("topics") or raw.get("organizations") or []
    return {normalize.slug(item[key]) for item in items}


def _seed_topic_names() -> set[str]:
    return _load_seed_names(config.TOPICS_SEED_PATH, "name")


def _seed_org_names() -> set[str]:
    return _load_seed_names(config.ORGANIZATIONS_SEED_PATH, "name")


def _cross_field_errors(data: dict) -> list[str]:
    errors: list[str] = []

    doc = data.get("document", {})
    document_number = doc.get("documentNumber", "")
    doc_key = data["document"].get("idOverride") or normalize.normalize_document_number(document_number)

    topic_seed = _seed_topic_names()
    for topic in doc.get("topics") or []:
        if normalize.slug(topic) not in topic_seed:
            errors.append(
                f"document.topics: '{topic}' không khớp mục nào trong reference/topics_seed.json"
            )

    org = data.get("organization", {})
    org_name = org.get("name", "")
    if org_name and normalize.slug(org_name) not in _seed_org_names() and not org.get("orgType"):
        errors.append(
            f"organization: '{org_name}' không có trong reference/organizations_seed.json "
            "nên phải điền orgType thủ công"
        )

    for i, citation in enumerate(data.get("citations") or []):
        target = citation.get("targetDocumentNumber", "")
        if target and normalize.normalize_document_number(target) == doc_key:
            errors.append(f"citations[{i}]: tự trích dẫn chính mình ('{target}')")

    def _check_unique_articles(articles: list[dict], where: str) -> None:
        seen: dict[str, int] = {}
        for i, art in enumerate(articles):
            num = art.get("number", "")
            if num in seen:
                errors.append(
                    f"{where}: số Điều '{num}' bị lặp (vị trí {seen[num]} và {i})"
                )
            else:
                seen[num] = i

    _check_unique_articles(data.get("articles") or [], "articles[] (Document)")
    for ci, content in enumerate(data.get("normativeContents") or []):
        _check_unique_articles(
            content.get("articles") or [], f"normativeContents[{ci}].articles[]"
        )

    return errors


def load_and_validate(path: Path, validator: jsonschema.Validator | None = None) -> ValidationResult:
    if validator is None:
        validator = jsonschema.Draft202012Validator(_load_schema())

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return ValidationResult(path=path, data=None, errors=[f"JSON không hợp lệ: {exc}"])

    schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if schema_errors:
        messages = [
            f"{'.'.join(str(p) for p in e.path) or '(gốc)'}: {e.message}" for e in schema_errors
        ]
        return ValidationResult(path=path, data=None, errors=messages)

    cross_errors = _cross_field_errors(data)
    if cross_errors:
        return ValidationResult(path=path, data=None, errors=cross_errors)

    return ValidationResult(path=path, data=data, errors=[])


def validate_dir(data_dir: Path) -> list[ValidationResult]:
    validator = jsonschema.Draft202012Validator(_load_schema())
    files = sorted(data_dir.glob("*.json"))
    return [load_and_validate(p, validator) for p in files]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate file JSON gán tay")
    parser.add_argument("--dir", type=Path, default=config.DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    results = validate_dir(args.dir)
    if not results:
        print(f"Không tìm thấy file .json nào trong {args.dir}")
        return 1

    n_ok = 0
    for r in results:
        if r.ok:
            n_ok += 1
            print(f"  OK    {r.path.name}")
        else:
            print(f"  LOI   {r.path.name}")
            for msg in r.errors:
                print(f"          - {msg}")

    print(f"\n{n_ok}/{len(results)} file hợp lệ.")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
