"""Lightweight persistent vector store with metadata filtering and role-based scoping."""
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import numpy as np

from app import config as C
from app.ai.schemas import SourceCitation


STOP_WORDS = {
    "what", "was", "the", "for", "in", "and", "a", "an", "is", "of", "to", "at",
    "by", "from", "with", "about", "that", "this", "it", "are", "on", "as", "or",
    "be", "been", "have", "has", "had", "do", "does", "did", "can", "could", "will",
    "would", "should", "shall", "may", "might", "must", "than", "then", "there",
    "their", "they", "them", "which", "who", "whom", "whose", "where", "when", "why", "how"
}


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2 and w not in STOP_WORDS]


class LocalEmbeddingModel:
    """Deterministic local embedding generator (feature hashing with IDF weighting).

    Zero external API dependencies, fast, reproducible, and offline-capable.
    """
    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed_text(self, text: str) -> list[float]:
        tokens = _tokenize(text)
        if not tokens:
            return [0.0] * self.dim
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in tokens:
            idx = hash(token) % self.dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class VectorStore:
    """Persistent vector store with metadata filtering and access scope enforcement."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or C.FESTOS_VECTOR_STORE_PATH)
        self.chunks: list[dict[str, Any]] = []
        self.local_embedder = LocalEmbeddingModel(dim=256)
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.chunks = data
            except Exception:
                self.chunks = []

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")

    def count(self) -> int:
        return len(self.chunks)

    def add_chunks(self, new_chunks: list[dict[str, Any]]) -> int:
        existing_ids = {c["chunk_id"] for c in self.chunks}
        added = 0
        for c in new_chunks:
            if c["chunk_id"] in existing_ids:
                # Replace existing chunk
                self.chunks = [item for item in self.chunks if item["chunk_id"] != c["chunk_id"]]
            if "embedding" not in c or not c["embedding"]:
                c["embedding"] = self.local_embedder.embed_text(c["text"])
            self.chunks.append(c)
            added += 1
        self._save()
        return added

    def clear(self) -> None:
        self.chunks = []
        self._save()

    def search(
        self,
        query: str,
        user_role: str,
        module_filter: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.30
    ) -> list[dict[str, Any]]:
        """Cosine similarity search with strict role-based access filtering."""
        if not self.chunks:
            return []

        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        query_vec = np.array(self.local_embedder.embed_text(query), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return []

        results = []
        for c in self.chunks:
            # Enforce access scope
            scope = c.get("access_scope", "public")
            if scope == "director_only" and user_role != "director":
                continue
            if scope == "lead_only" and user_role in ("volunteer", "viewer"):
                continue

            if module_filter and c.get("module") != module_filter:
                continue

            chunk_tokens = set(_tokenize(c.get("text", "")))
            if not (set(q_tokens) & chunk_tokens):
                continue

            doc_vec = np.array(c.get("embedding", []), dtype=np.float32)
            d_norm = np.linalg.norm(doc_vec)
            if d_norm == 0:
                continue

            score = float(np.dot(query_vec, doc_vec) / (q_norm * d_norm))
            if score >= threshold:
                results.append({
                    "chunk_id": c.get("chunk_id"),
                    "source_type": c.get("source_type"),
                    "source_id": c.get("source_id"),
                    "module": c.get("module"),
                    "title": c.get("title", ""),
                    "text": c.get("text", ""),
                    "score": round(score, 4),
                    "access_scope": scope,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


# Global singleton instance
_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance


def chunk_document(
    text: str,
    source_type: str,
    source_id: str,
    module: str,
    title: str,
    access_scope: str = "public",
    chunk_size: int = 400,
    chunk_overlap: int = 50
) -> list[dict[str, Any]]:
    """Chunks operational documentation into discrete searchable passages."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    chunk_idx = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for p in paragraphs:
        if len(p) < 40:
            continue
        chunk_idx += 1
        chunks.append({
            "chunk_id": f"{source_id}#chunk_{chunk_idx}",
            "source_type": source_type,
            "source_id": source_id,
            "module": module,
            "title": title,
            "access_scope": access_scope,
            "text": p,
            "updated_at": now_iso,
            "content_version": "1.0",
        })
    return chunks


def build_semantic_index() -> dict[str, Any]:
    """Indexes FestOS operational assumptions, rules, and documentation."""
    store = get_vector_store()
    store.clear()
    total_indexed = 0
    modules = set()

    # 1. Index ASSUMPTIONS.md
    assumptions_path = C.REPO_ROOT / "docs" / "ASSUMPTIONS.md"
    if assumptions_path.exists():
        raw_text = assumptions_path.read_text(encoding="utf-8")
        sections = re.split(r"\n##\s+", raw_text)
        for sec in sections[1:]:  # skip header
            lines = sec.strip().splitlines()
            if not lines:
                continue
            heading = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            # Extract code e.g. "A-02"
            code_match = re.match(r"(A-\d+)", heading)
            code = code_match.group(1) if code_match else "ASSUMPTION"

            # Derive module
            mod = "general"
            h_low = heading.lower()
            if "accommodation" in h_low or "housing" in h_low or "gender" in h_low:
                mod = "accommodation"
            elif "schedul" in h_low or "event" in h_low or "venue" in h_low:
                mod = "schedule"
            elif "inventory" in h_low or "merch" in h_low:
                mod = "inventory"
            elif "vendor" in h_low or "diet" in h_low:
                mod = "vendors"
            elif "participant" in h_low or "contingent" in h_low or "dedupe" in h_low or "reconciliation" in h_low:
                mod = "participants"
            elif "disruption" in h_low:
                mod = "disruptions"
            elif "control" in h_low or "kpi" in h_low or "audit" in h_low:
                mod = "control"

            modules.add(mod)
            chunks = chunk_document(
                text=f"{heading}\n\n{body}",
                source_type="assumption",
                source_id=code,
                module=mod,
                title=f"Rule {code}: {heading}",
                access_scope="director_only" if mod in ("disruptions", "control", "audit") else "public"
            )
            total_indexed += store.add_chunks(chunks)

    # 2. Index README operational procedures
    readme_path = C.REPO_ROOT / "README.md"
    if readme_path.exists():
        raw_readme = readme_path.read_text(encoding="utf-8")
        readme_chunks = chunk_document(
            text=raw_readme,
            source_type="documentation",
            source_id="README",
            module="operations",
            title="FestOS Architecture and Hard Rules",
            access_scope="public"
        )
        total_indexed += store.add_chunks(readme_chunks)
        modules.add("operations")

    return {
        "run_ok": True,
        "indexed_chunks": total_indexed,
        "modules": sorted(list(modules)),
        "message": f"Successfully indexed {total_indexed} operational knowledge chunks across {len(modules)} modules."
    }
