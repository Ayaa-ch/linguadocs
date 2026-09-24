"""
Prépare le corpus ONU pour l'évaluation.
Entrée  : fichiers alignés (une phrase par ligne, même numéro = même phrase)
Sortie  : eval/datasets/un_corpus.jsonl  (documents à indexer)
          eval/datasets/un_pairs.jsonl   (requêtes cross-lingues)
"""
import json
from itertools import permutations
from pathlib import Path

LANGS = {"ar": "ar", "en": "en", "fr": "fr", "es": "es"}
DATA_DIR = Path("eval/datasets/un")
OUT_DIR  = Path("eval/datasets")


def load_aligned(split: str = "devset", n: int = 500) -> list[dict]:
    """Charge les phrases alignées du corpus ONU."""
    files = {}
    for lang in LANGS:
        path = DATA_DIR / f"UNv1.0.{split}.{lang}"
        if not path.exists():
            print(f"⚠️  Fichier manquant : {path}")
            continue
        files[lang] = path.read_text(encoding="utf-8").splitlines()

    available = list(files.keys())
    min_len   = min(len(files[l]) for l in available)
    total     = min(n, min_len)

    pairs = []
    for i in range(total):
        pair = {"doc": f"{split}_{i}"}
        for lang in available:
            pair[lang] = files[lang][i].strip()
        pairs.append(pair)
    return pairs


def build(pairs: list[dict], langs=("fr", "en", "ar", "es"),
          user_id: str = "alice") -> None:
    """Construit corpus.jsonl et pairs.jsonl."""
    seen, kept = set(), []
    for i, p in enumerate(pairs):
        available = [l for l in langs if l in p and p[l]]
        texts = [p[l] for l in available]
        if min(len(t.split()) for t in texts) < 8:   # trop court
            continue
        if texts[0] in seen:                          # doublon
            continue
        seen.add(texts[0])
        kept.append((i, p, available))

    print(f"Phrases retenues : {len(kept)} / {len(pairs)}")

    with open(OUT_DIR / "un_corpus.jsonl", "w", encoding="utf-8") as fc, \
         open(OUT_DIR / "un_pairs.jsonl",  "w", encoding="utf-8") as fq:

        for i, p, available in kept:
            # un chunk par langue
            for lang in available:
                fc.write(json.dumps({
                    "chunk_key" : f"{p['doc']}#{i}:{lang}",
                    "text"      : p[lang],
                    "lang"      : lang,
                    "page"      : 0,
                }, ensure_ascii=False) + "\n")

            # requêtes cross-lingues (toutes les paires de langues)
            for qlang, tlang in permutations(available, 2):
                fq.write(json.dumps({
                    "user_id"     : user_id,
                    "lang"        : qlang,
                    "target_lang" : tlang,
                    "query"       : p[qlang],
                    "relevant"    : [f"{p['doc']}#{i}:{tlang}"],
                }, ensure_ascii=False) + "\n")

    print(f"✅ Corpus  : {OUT_DIR}/un_corpus.jsonl")
    print(f"✅ Requêtes: {OUT_DIR}/un_pairs.jsonl")


if __name__ == "__main__":
    pairs = load_aligned(split="devset", n=500)
    build(pairs, langs=("fr", "en", "ar", "es"))