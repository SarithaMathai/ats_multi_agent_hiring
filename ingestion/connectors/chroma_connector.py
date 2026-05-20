"""
Embed unstructured text fields and upsert them into ChromaDB collections.

Uses sentence-transformers directly (Day 5 will wrap this in the Embedder class).
Collections must already exist — call initialise_all_collections() before this.
"""

import json

from sentence_transformers import SentenceTransformer

from configs.settings import settings
from vector_store.chroma.collection_manager import get_collection

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("  Loading embedding model (first run downloads ~90MB)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _embed(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(texts, show_progress_bar=False).tolist()


# ── ats_candidates ─────────────────────────────────────────────────────────────

def embed_candidates(candidate_rows: list[dict]) -> int:
    col = get_collection(settings.chroma.collection_candidates)
    ids, docs, metas, embs = [], [], [], []

    for row in candidate_rows:
        text = (
            f"{row['name']} is a {row['experience_years']}-year "
            f"{row['position']} candidate sourced via {row['source_channel']}. "
            f"Skills: {row.get('skills', '')}. "
            f"Background: {row.get('background', '')}."
        )
        ids.append(row["id"])
        docs.append(text)
        metas.append({
            "candidate_id":    row["id"],
            "source_channel":  row["source_channel"],
            "position":        row["position"],
            "experience_years": float(row["experience_years"]),
            "overall_status":  row["overall_status"],
        })

    embs = _embed(docs)
    col.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
    return len(ids)


# ── ats_resumes (3 chunks per candidate) ──────────────────────────────────────

def embed_resumes(candidate_rows: list[dict]) -> int:
    col = get_collection(settings.chroma.collection_resumes)
    ids, docs, metas, embs_input = [], [], [], []

    for row in candidate_rows:
        cid  = row["id"]
        pos  = row["position"]
        meta_base = {"candidate_id": cid, "position": pos}

        chunks = [
            (f"{cid}_chunk_0", f"Education and background: {row.get('background', '')}",
             {**meta_base, "chunk_type": "education"}),
            (f"{cid}_chunk_1",
             f"Professional experience as {pos}: {row.get('background', '')} "
             f"with {row['experience_years']} years in the field.",
             {**meta_base, "chunk_type": "experience"}),
            (f"{cid}_chunk_2",
             f"Technical skills: {row.get('skills', '')}",
             {**meta_base, "chunk_type": "skills"}),
        ]
        for chunk_id, text, meta in chunks:
            ids.append(chunk_id)
            docs.append(text)
            metas.append(meta)
            embs_input.append(text)

    embs = _embed(docs)
    col.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
    return len(ids)


# ── ats_feedback ───────────────────────────────────────────────────────────────

def embed_feedback(stage_rows: list[dict]) -> int:
    col = get_collection(settings.chroma.collection_feedback)
    ids, docs, metas = [], [], []

    for row in stage_rows:
        feedback = (row.get("feedback") or "").strip()
        if not feedback:
            continue
        text = (
            f"Stage: {row['stage_name']} | Outcome: {row.get('outcome', 'unknown')} | "
            f"Duration: {row.get('duration_hours', '?')} hours\n"
            f"Feedback: {feedback}"
        )
        ids.append(row["id"])
        docs.append(text)
        metas.append({
            "stage_id":       row["id"],
            "candidate_id":   row["candidate_id"],
            "stage_name":     row["stage_name"],
            "outcome":        row.get("outcome") or "unknown",
            "duration_hours": float(row["duration_hours"]) if row.get("duration_hours") else 0.0,
            "interviewer_id": row.get("interviewer_id") or "none",
        })

    if not ids:
        return 0
    embs = _embed(docs)
    col.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
    return len(ids)


# ── ats_interventions ──────────────────────────────────────────────────────────

def embed_interventions(interventions: list[dict]) -> int:
    col = get_collection(settings.chroma.collection_interventions)
    ids, docs, metas = [], [], []

    for item in interventions:
        steps_text = "\n".join(
            f"{i+1}. {s}" for i, s in enumerate(item.get("steps", []))
        )
        text = (
            f"Issue: {item['issue_text']}\n"
            f"Context: {item.get('role', 'all')} hiring pipeline\n"
            f"Intervention: {item['outcome_text']}\n"
            f"Steps:\n{steps_text}"
        )
        ids.append(item["intervention_id"])
        docs.append(text)
        metas.append({
            "intervention_id":       item["intervention_id"],
            "issue_type":            item["issue_type"],
            "role":                  item.get("role", "all"),
            "observed_impact_pct":   float(item.get("observed_impact_pct", 0)),
            "implementation_weeks":  int(item.get("implementation_weeks", 4)),
            "outcome":               item["outcome_text"][:200],
            "practice_steps":        json.dumps(item.get("steps", [])),
        })

    embs = _embed(docs)
    col.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
    return len(ids)
