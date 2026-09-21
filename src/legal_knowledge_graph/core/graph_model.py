"""
Dựng đồ thị TRONG BỘ NHỚ từ các file JSON đã gán tay (đã qua validate.py).

Không import neo4j ở đây — thuần cấu trúc dữ liệu Python, test/soi được độc
lập với kết nối DB thật. Việc ghi GraphModel này vào Neo4j nằm ở
graph_loader.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config, normalize
from .validate import validate_dir


def _load_seed(path: Path, key: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get(key, [])


class GraphModel:
    def __init__(self) -> None:
        self.topics: dict[str, dict] = {}
        self.target_groups: dict[str, dict] = {}
        self.orgs: dict[str, dict] = {}
        self.persons: dict[str, dict] = {}
        self.documents: dict[str, dict] = {}
        self.normative_contents: list[dict] = []
        self.articles: list[dict] = []
        self.issued_by: list[dict] = []
        self.has_topic: list[dict] = []
        self.applies_to: list[dict] = []
        self.signed_by: list[dict] = []
        self.mentions: list[dict] = []
        self.promulgates: list[dict] = []
        self.citations: list[dict] = []
        self._org_name_index: dict[str, str] = {}  # slug(name) -> orgId

    # ---- organization ----
    def register_org(self, name: str, org_type: str | None, parent_name: str | None,
                      id_override: str | None) -> str:
        key = normalize.slug(name)
        org_id = id_override or self._org_name_index.get(key) or normalize.org_id(name)
        parent_id = None
        if parent_name:
            parent_key = normalize.slug(parent_name)
            parent_id = self._org_name_index.get(parent_key) or normalize.org_id(parent_name)
            if parent_key not in self._org_name_index:
                # Cha chưa từng thấy -> đăng ký placeholder, orgType điền sau nếu gặp lại.
                self.register_org(parent_name, None, None, None)

        existing = self.orgs.get(org_id)
        if existing is None:
            self.orgs[org_id] = {
                "orgId": org_id,
                "name": name,
                "orgType": org_type,
                "parentOrg": parent_id,
            }
        else:
            if org_type and not existing.get("orgType"):
                existing["orgType"] = org_type
            if parent_id and not existing.get("parentOrg"):
                existing["parentOrg"] = parent_id
        self._org_name_index[key] = org_id
        return org_id

    def resolve_level(self, org_id: str, document_type: str) -> tuple[int | None, str]:
        org_type = self.orgs.get(org_id, {}).get("orgType")
        level, note = normalize.authority_level(document_type, org_type)
        if level is not None:
            return level, note

        # Mượn bậc của tổ chức cha gần nhất có org-type suy được level
        # (đơn vị trực thuộc / phòng ban không có bậc riêng — §3 Ontology).
        visited: set[str] = set()
        current = self.orgs.get(org_id, {}).get("parentOrg")
        while current and current not in visited:
            visited.add(current)
            parent_type = self.orgs.get(current, {}).get("orgType")
            if parent_type in normalize.LEVEL_BY_ORG_TYPE:
                return normalize.LEVEL_BY_ORG_TYPE[parent_type], "suy-rong: theo-don-vi-cha"
            current = self.orgs.get(current, {}).get("parentOrg")
        return None, "khong-suy-duoc"

    # ---- topic ----
    def register_topic(self, name: str) -> str:
        tid = normalize.topic_id(name)
        self.topics.setdefault(tid, {"topicId": tid, "name": name})
        return tid

    # ---- target group ----
    def register_target_group(self, name: str) -> str:
        gid = normalize.target_group_id(name)
        self.target_groups.setdefault(gid, {"targetGroupId": gid, "name": name})
        return gid

    # ---- person ----
    def register_person(self, full_name: str, academic_title: str | None,
                         positions: list[str], id_override: str | None) -> str:
        pid = id_override or normalize.person_id(full_name)
        existing = self.persons.get(pid)
        if existing is None:
            self.persons[pid] = {
                "personId": pid,
                "fullName": full_name,
                "academicTitle": academic_title,
                "positions": list(dict.fromkeys(positions)),
            }
        else:
            if academic_title and not existing.get("academicTitle"):
                existing["academicTitle"] = academic_title
            for p in positions:
                if p not in existing["positions"]:
                    existing["positions"].append(p)
        return pid

    def load_seeds(self) -> None:
        for row in _load_seed(config.TOPICS_SEED_PATH, "topics"):
            self.register_topic(row["name"])
        for row in _load_seed(config.TARGET_GROUPS_SEED_PATH, "target_groups"):
            self.register_target_group(row["name"])
        for row in _load_seed(config.ORGANIZATIONS_SEED_PATH, "organizations"):
            self.orgs[row["orgId"]] = {
                "orgId": row["orgId"],
                "name": row["name"],
                "orgType": row.get("orgType"),
                "parentOrg": row.get("parentOrg"),
            }
            self._org_name_index[normalize.slug(row["name"])] = row["orgId"]

    def add_document_file(self, data: dict) -> None:
        doc = data["document"]
        doc_key = doc.get("idOverride") or normalize.normalize_document_number(doc["documentNumber"])

        org = data["organization"]
        org_id = self.register_org(
            org["name"], org.get("orgType"), org.get("parentOrg"), org.get("idOverride")
        )
        level, level_note = self.resolve_level(org_id, doc["documentType"])

        self.documents[doc_key] = {
            "normalizedNumber": doc_key,
            "documentNumber": doc["documentNumber"],
            "title": doc["title"],
            "documentType": doc["documentType"],
            "status": doc.get("status"),
            "issueDate": normalize.vn_date_to_iso(doc.get("issueDate")),
            "effectiveDate": normalize.vn_date_to_iso(doc.get("effectiveDate")),
            "expiryDate": normalize.vn_date_to_iso(doc.get("expiryDate")),
            "fileUrl": doc.get("fileUrl"),
            "summary": doc.get("summary"),
            "authorityLevel": level,
            "levelNote": level_note,
            "isStub": False,
        }
        self.issued_by.append({"doc": doc_key, "org": org_id})

        for topic_name in doc.get("topics") or []:
            tid = self.register_topic(topic_name)
            self.has_topic.append({"doc": doc_key, "topic": tid})

        for group_name in doc.get("targetGroups") or []:
            gid = self.register_target_group(group_name)
            self.applies_to.append({"doc": doc_key, "group": gid})

        for signer in data.get("signers") or []:
            pid = self.register_person(
                signer["fullName"], signer.get("academicTitle"),
                signer["position"], signer.get("idOverride"),
            )
            self.signed_by.append({"doc": doc_key, "person": pid})

        for mention_name in data.get("mentions") or []:
            mid = self.register_org(mention_name, None, None, None)
            self.mentions.append({"doc": doc_key, "org": mid})

        for idx, content in enumerate(data.get("normativeContents") or [], start=1):
            content_id = content.get("idOverride") or normalize.content_id(doc_key, idx)
            self.normative_contents.append({
                "contentId": content_id,
                "contentType": content["contentType"],
                "title": content["title"],
                "status": content.get("status") or self.documents[doc_key]["status"],
            })
            self.promulgates.append({"doc": doc_key, "content": content_id})
            for art in content["articles"]:
                self._add_article(art, parent_id=content_id, parent_label="NormativeContent")

        for art in data.get("articles") or []:
            self._add_article(art, parent_id=doc_key, parent_label="Document")

        for citation in data.get("citations") or []:
            self.citations.append({
                "source": doc_key,
                "target_raw": citation["targetDocumentNumber"],
                "target": normalize.normalize_document_number(citation["targetDocumentNumber"]),
                "type": citation["relationType"],
                "targetArticle": citation.get("targetArticle"),
                "context": citation.get("context"),
            })

    def _add_article(self, art: dict, parent_id: str, parent_label: str) -> None:
        article_id = normalize.article_id(parent_id, art["number"])
        self.articles.append({
            "articleId": article_id,
            "number": art["number"],
            "heading": art.get("heading"),
            "text": art["text"],
            "isImplementationClause": bool(art.get("isImplementationClause", False)),
            "parentId": parent_id,
            "parentLabel": parent_label,
        })


def collect(data_dir: Path) -> GraphModel:
    """Validate toàn bộ file trong data_dir rồi dựng GraphModel từ dữ liệu đã sạch.

    build.py không bao giờ nạp dữ liệu chưa qua validate.py — raise SystemExit
    ngay nếu có file lỗi, thay vì âm thầm bỏ qua.
    """

    results = validate_dir(data_dir)
    bad = [r for r in results if not r.ok]
    if bad:
        for r in bad:
            print(f"  LOI  {r.path.name}")
            for msg in r.errors:
                print(f"         - {msg}")
        raise SystemExit(
            f"{len(bad)}/{len(results)} file KHÔNG hợp lệ — sửa xong rồi chạy lại "
            "(build không bao giờ nạp dữ liệu chưa qua validate.py)."
        )

    model = GraphModel()
    model.load_seeds()
    for r in results:
        model.add_document_file(r.data)
    return model
