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


def evaluate_refusal(path: str = "eval/datasets/un_pairs_hors_domaine.jsonl", k: int = 5, threshold: float = 0.30) -> dict:
    try:
        from linguadocs.settings import settings
        threshold = settings.refusal_threshold
    except Exception:
        pass
    lines = [json.loads(l) for l in open(path, encoding="utf-8")]
    refus_corrects = 0
    faux_refus = 0
    total = len(lines)
    for q in lines:
        hits = search(q["user_id"], q["query"], k)
        best = max((getattr(h, "score", 0) or 0) for h in hits) if hits else 0
        should_refuse = q.get("should_refuse", True)
        is_refused = best < threshold or not hits
        if should_refuse and is_refused:
            refus_corrects += 1
        elif not should_refuse and is_refused:
            faux_refus += 1
    return {"refus_corrects": refus_corrects, "faux_refus": faux_refus, "total": total, "seuil": threshold}


if __name__ == "__main__":
    index_corpus()
    print("\n--- Résultats recall@5 ---")
    print(f"{'Query':>6} → {'Target':>6} | {'n':>4} | {'recall@5':>8} | {'ci95':>15} | {'mrr':>6}")
    print("-" * 60)
    for r in evaluate():
        print(f"{r['query_lang']:>6} → {r['target_lang']:>6} | "
              f"{r['n']:>4} | {r['recall@5']:>8} | "
              f"{r['ci95']:>15} | {r['mrr']:>6}")
    print("\n--- Évaluation refus hors-domaine ---")
    try:
        res = evaluate_refusal()
        print(f"Seuil: {res['seuil']} | Refus corrects: {res['refus_corrects']}/{res['total']} | Faux refus: {res['faux_refus']}")
    except Exception as e:
        print(f"evaluate_refusal error: {e}")