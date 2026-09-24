import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = sorted(p for p in root.rglob("*") if p.is_file())
print(f"{len(files)} fichiers trouvés")
for p in files[:20]:
    print(p, p.stat().st_size)
print("\n--- Contenu des 3 premiers fichiers ---")
for p in files[:3]:
    print(f"\n=== {p} ===")
    print(p.read_text(encoding="utf-8", errors="replace")[:600])