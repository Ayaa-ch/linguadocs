# Benchmarks — i7 8e gen, CPU seul, 16 Go RAM
Date : jour 3

## LLM (Ollama)
| Modèle      | tokens/s court | tokens/s long | Total long | Décision         |
|-------------|---------------|---------------|------------|------------------|
| qwen2.5:7b  | 3.3           | 2.0           | 207s       | ❌ trop lent     |
| qwen3:4b    | 5.4           | 2.8           | 736s       | ✅ retenu        |

**Décision : qwen3:4b**
- 2x plus rapide que qwen2.5:7b sur prompt court
- Le total de 736s s'explique par le "thinking" de Qwen3
  (mode de raisonnement interne) — on le désactivera dans le code

## Embeddings
| Modèle     | Chargement | Chunks/s | Décision                        |
|------------|------------|----------|---------------------------------|
| e5-small   | 12.9s      | 6.0      | ✅ dev + production             |
| bge-m3     | 10.9s      | 0.6      | ⚠️ expériences finales seulement|

**Décision : e5-small pour tout le développement**
- bge-m3 = 10x plus lent, 1000 chunks = 28 min d'indexation
- bge-m3 réservé à E3 (résultats finaux)

## Whisper
| Taille | Durée audio | Temps CPU | RTF  | Langue détectée | Décision       |
|--------|-------------|-----------|------|-----------------|----------------|
| small  | 24.6s       | 19.6s     | 0.79 | en (p=0.94)     | ✅ retenu      |

**Décision : small int8**
- RTF = 0.79 : traitement plus rapide que l'audio réel ✅
- Confiance 0.94 sur audio anglais clair ✅
- Tester base et tiny sur audio arabe et français (palier B)

## RAM maximale observée
| Composant  | RAM estimée |
|------------|-------------|
| qwen3:4b   | à mesurer   |
| e5-small   | à mesurer   |
| Qdrant     | à mesurer   |
| Total      | à mesurer   |