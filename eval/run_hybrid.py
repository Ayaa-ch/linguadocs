import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from linguadocs.retrieval.retrieval import init, index, search, search_hybrid, search_sparse


def index_corpus(path: str = "eval/datasets/un_corpus.jsonl", user_id: str = "alice", batch: int = 64) -> None:
    print("Indexation du corpus...")
    init(reset=True)
    items = [json.loads(l) for l in open(path, encoding="utf-8")]
    for j in range(0, len(items), batch):
        index(user_id, items[j:j + batch])
        print(f"  {min(j + batch, len(items))}/{len(items)} chunks indexes")
    print("Indexation terminee")

# pour pouvoir comparer, on réutilise la même logique que run_retrieval
def evaluate_mode(search_fn, path: str = "eval/datasets/un_pairs.jsonl", k: int = 5, limit: int | None = None):
    per = collections.defaultdict(lambda: {"hit": [], "rr": []})
    lines = [json.loads(l) for l in open(path, encoding="utf-8")]
    if limit:
        lines = lines[:limit]
    for q in lines:
        hits = search_fn(q["user_id"], q["query"], k)
        keys = []
        for h in hits:
            pl = getattr(h, "payload", {}) or {}
            keys.append(pl.get("chunk_key"))
        rel = set(q["relevant"])
        rank = next((i for i, key in enumerate(keys, 1) if key in rel), None)
        d = per[(q["lang"], q["target_lang"])]
        d["hit"].append(1.0 if rank else 0.0)
        d["rr"].append(1 / rank if rank else 0.0)

    rows = []
    for (qlang, tlang), d in sorted(per.items()):
        n = len(d["hit"])
        recall = round(sum(d["hit"]) / n, 3) if n else 0
        mrr = round(sum(d["rr"]) / n, 3) if n else 0
        rows.append({"query_lang": qlang, "target_lang": tlang, "n": n, f"recall@{k}": recall, "mrr": mrr})
    return rows


def main():
    # Si collection vide ou incomplète, re-indexer
    from qdrant_client import QdrantClient

    try:
        qc = QdrantClient(url="http://localhost:6333", check_compatibility=False)
        info = qc.get_collection("chunks")
        cnt = getattr(info, "points_count", 0) or 0
        # le corpus complet fait 1648 chunks, on re-indexe si < 1500
        if cnt < 1500:
            print(f"Collection incomplete ({cnt} vecteurs) -> re-indexation 1648")
            index_corpus()
        else:
            print(f"Collection OK: {cnt} vecteurs")
    except Exception as e:
        print(f"Check collection failed: {e} -> re-indexation")
        index_corpus()

    modes = {
        "dense": search,
        "sparse": search_sparse,
        "hybrid": search_hybrid,
    }
    all_rows = []
    for mode_name, fn in modes.items():
        print(f"\n=== {mode_name} (echantillon 200/4944 pour eviter 2h) ===")
        rows = evaluate_mode(fn, limit=200)
        for r in rows:
            print(f"{r['query_lang']:>6} -> {r['target_lang']:>6} | n={r['n']:>4} | recall@5={r['recall@5']} | mrr={r['mrr']}")
        for r in rows:
            r2 = dict(r)
            r2["mode"] = mode_name
            all_rows.append(r2)

    # sauvegarder
    out = Path("docs/results/E4_hybrid.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    if all_rows:
        fieldnames = ["mode", "query_lang", "target_lang", "n", "recall@5", "mrr"]
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in all_rows:
                w.writerow({k: r.get(k) for k in fieldnames})
        print(f"\nSaved to {out}")

if __name__ == "__main__":
    main()
