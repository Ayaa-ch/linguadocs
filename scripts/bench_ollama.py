import httpx
import sys

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b"
PROMPTS = {
    "court": "Explique en deux phrases ce qu'est un corpus parallèle.",
    "long": "Voici un contexte. " + "Le Conseil a adopté une résolution. " * 150
            + "\nRésume ce contexte en une phrase.",
}
for name, prompt in PROMPTS.items():
    r = httpx.post("http://localhost:11434/api/generate",
                   json={"model": MODEL, "prompt": prompt, "stream": False},
                   timeout=900).json()
    gen_s = r.get("eval_duration", 1) / 1e9
    prompt_s = r.get("prompt_eval_duration", 0) / 1e9
    print(f"{name}: prompt {r.get('prompt_eval_count')} tokens en {prompt_s:.1f}s ; "
          f"génération {r.get('eval_count', 0) / gen_s:.1f} tokens/s ; "
          f"total {r.get('total_duration', 0) / 1e9:.1f}s")