"""Re-indexe les documents de l'app dans Qdrant (collection "chunks").

Utile quand :
- la collection "chunks" a ete videe (reset, changement de modele
  d'embeddings, eval lancee avec init(reset=True) sur la mauvaise collection) ;
- le modele d'embeddings a change -> les vecteurs sont perimes.

Le fichier source est relu depuis data/users/<user_id>/<doc_id>/<filename>.
Les documents dont le fichier source a disparu sont ignores (le vecteur ne
peut pas etre reconstruit).

Usage :
    uv run python scripts/reindex_documents.py            # re-indexe tout
    uv run python scripts/reindex_documents.py --reset    # vide d'abord "chunks"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import torch

torch.set_num_threads(os.cpu_count() or 4)

sys.path.insert(0, "src")

from sqlmodel import select

from linguadocs.api.database import AsyncSessionLocal
from linguadocs.api.models import Document
from linguadocs.ingest.indexer import index_document
from linguadocs.retrieval.retrieval import client
from linguadocs.settings import settings

COL = "chunks"


def log(msg: str = "") -> None:
    print(msg, flush=True)


async def main(reset: bool) -> None:
    if reset and client.collection_exists(COL):
        log(f"Suppression de la collection '{COL}'...")
        client.delete_collection(COL)

    async with AsyncSessionLocal() as session:
        docs = (await session.exec(select(Document))).all()

    todo = []
    for d in docs:
        if d.status != "indexed":
            continue
        path = Path(settings.data_dir) / str(d.user_id) / str(d.id) / str(d.filename)
        if not path.exists():
            log(f"  IGNORE (fichier absent) : {d.filename}")
            continue
        todo.append((d, path))

    log(f"{len(todo)} document(s) a re-indexer")
    for i, (d, path) in enumerate(todo, 1):
        log(f"  [{i}/{len(todo)}] {d.filename} ({d.user_id})")
        try:
            await index_document(d.id, d.user_id, path, session=None)
        except Exception as e:
            log(f"    ERREUR : {e}")

    try:
        info = client.get_collection(COL)
        log(f"Collection '{COL}' : {getattr(info, 'points_count', 0)} vecteurs")
    except Exception as e:
        log(f"Verification impossible : {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-indexe les documents de l'app dans Qdrant")
    ap.add_argument("--reset", action="store_true", help="vider la collection avant de re-indexer")
    args = ap.parse_args()
    asyncio.run(main(args.reset))
