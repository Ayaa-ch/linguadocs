import sys
import time
from sentence_transformers import SentenceTransformer

NAME = sys.argv[1] if len(sys.argv) > 1 else "intfloat/multilingual-e5-small"
texts = ["passage: " + "Le Conseil a adopté la résolution après un long débat. " * 20] * 100

t0 = time.time()
model = SentenceTransformer(NAME)
load = time.time() - t0
t0 = time.time()
model.encode(texts, batch_size=16, normalize_embeddings=True)
dt = time.time() - t0
print(f"{NAME}: chargement {load:.1f}s ; {len(texts) / dt:.1f} chunks/s")