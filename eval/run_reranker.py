import collections
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
from linguadocs.retrieval.retrieval import rerank, search


def evaluate_reranker(path: str = "eval/datasets/un_pairs.jsonl", k: int = 5, top_n_list=[5, 10, 20]):
    # charge corpus
    lines = [json.loads(l) for l in open(path, encoding="utf-8")]
    # pour chaque top_n, on fait search k=top_n puis rerank top 5
    results = []
    for top_n in top_n_list:
        per = collections.defaultdict(lambda: {"hit": [], "rr": [], "lat": []})
        for q in lines:
            # retrieve top_n
            t0 = time.perf_counter()
            hits = search(q["user_id"], q["query"], k=top_n)
            # rerank
            t1 = time.perf_counter()
            reranked = rerank(q["query"], hits, top_n=5)
            t2 = time.perf_counter()
            lat = int((t2 - t1) * 1000)
            keys = []
            for h in reranked:
                pl = getattr(h, "payload", {}) or {}
                keys.append(pl.get("chunk_key"))
            rel = set(q["relevant"])
            rank = next((i for i, key in enumerate(keys, 1) if key in rel), None)
            d = per[(q["lang"], q["target_lang"])]
            d["hit"].append(1.0 if rank else 0.0)
            d["rr"].append(1 / rank if rank else 0.0)
            d["lat"].append(lat)

        for (qlang, tlang), d in sorted(per.items()):
            n = len(d["hit"])
            recall = round(sum(d["hit"]) / n, 3) if n else 0
            mrr = round(sum(d["rr"]) / n, 3) if n else 0
            avg_lat = round(sum(d["lat"]) / len(d["lat"]), 1) if d["lat"] else 0
            results.append(
                {
                    "top_n": top_n,
                    "query_lang": qlang,
                    "target_lang": tlang,
                    "n": n,
                    f"recall@{k}": recall,
                    "mrr": mrr,
                    "rerank_lat_ms": avg_lat,
                }
            )
    # aussi sans reranker (top 5 direct)
    per = collections.defaultdict(lambda: {"hit": [], "rr": []})
    for q in lines:
        hits = search(q["user_id"], q["query"], k=5)
        keys = [getattr(h, "payload", {}).get("chunk_key") for h in hits]
        rel = set(q["relevant"])
        rank = next((i for i, key in enumerate(keys, 1) if key in rel), None)
        d = per[(q["lang"], q["target_lang"])]
        d["hit"].append(1.0 if rank else 0.0)
        d["rr"].append(1 / rank if rank else 0.0)
    for (qlang, tlang), d in sorted(per.items()):
        n = len(d["hit"])
        recall = round(sum(d["hit"]) / n, 3) if n else 0
        mrr = round(sum(d["rr"]) / n, 3) if n else 0
        results.append({"top_n": 5, "query_lang": qlang, "target_lang": tlang, "n": n, f"recall@{k}": recall, "mrr": mrr, "rerank_lat_ms": 0, "mode": "sans_reranker"})

    return results


def main():
    print("Evaluation reranker...")
    rows = evaluate_reranker()
    for r in rows:
        print(r)
    out = Path("docs/results/E5_reranker.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fieldnames = ["top_n", "query_lang", "target_lang", "n", "recall@5", "mrr", "rerank_lat_ms"]
        # ajouter mode si présent
        has_mode = any("mode" in r for r in rows)
        if has_mode:
            fieldnames.append("mode")
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fieldnames})
        print(f"Saved to {out}")


if __name__ == "__main__":
    main()
