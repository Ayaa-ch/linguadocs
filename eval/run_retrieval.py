import collections
import json
import random
import sys

sys.path.insert(0, "src")
from linguadocs.retrieval.dense import init, index, search


def bootstrap_ci(values: list[float], n: int = 1000) -> tuple[float, float]:
    means = sorted(
        sum(random.choices(values, k=len(values))) / len(values)
        for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def index_corpus(path: str = "eval/datasets/un_corpus.jsonl",
                 user_id: str = "alice", batch: int = 64) -> None:
    print("Indexation du corpus...")
    init(reset=True)
    items = [json.loads(l) for l in open(path, encoding="utf-8")]
    for j in range(0, len(items), batch):
        index(user_id, items[j:j + batch])
        print(f"  {min(j + batch, len(items))}/{len(items)} chunks indexés")
    print("✅ Indexation terminée")


def evaluate(path: str = "eval/datasets/un_pairs.jsonl",
             k: int = 5) -> list[dict]:
    per = collections.defaultdict(lambda: {"hit": [], "rr": []})
    lines = [json.loads(l) for l in open(path, encoding="utf-8")]
    for q in lines:
        hits = search(q["user_id"], q["query"], k)
        keys = [h.payload["chunk_key"] for h in hits]
        rel  = set(q["relevant"])
        rank = next((i for i, key in enumerate(keys, 1) if key in rel), None)
        d    = per[(q["lang"], q["target_lang"])]
        d["hit"].append(1.0 if rank else 0.0)
        d["rr"].append(1 / rank if rank else 0.0)

    rows = []
    for (qlang, tlang), d in sorted(per.items()):
        n      = len(d["hit"])
        lo, hi = bootstrap_ci(d["hit"])
        rows.append({
            "query_lang"  : qlang,
            "target_lang" : tlang,
            "n"           : n,
            f"recall@{k}" : round(sum(d["hit"]) / n, 3),
            "ci95"        : f"[{lo:.3f}, {hi:.3f}]",
            "mrr"         : round(sum(d["rr"]) / n, 3),
        })
    return rows


if __name__ == "__main__":
    index_corpus()
    print("\n--- Résultats recall@5 ---")
    print(f"{'Query':>6} → {'Target':>6} | {'n':>4} | {'recall@5':>8} | {'ci95':>15} | {'mrr':>6}")
    print("-" * 60)
    for r in evaluate():
        print(f"{r['query_lang']:>6} → {r['target_lang']:>6} | "
              f"{r['n']:>4} | {r['recall@5']:>8} | "
              f"{r['ci95']:>15} | {r['mrr']:>6}")