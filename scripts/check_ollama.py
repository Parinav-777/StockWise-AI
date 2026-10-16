"""Run on YOUR machine to verify real model inference: python scripts/check_ollama.py"""
import json, os, urllib.request
url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"); model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
req = urllib.request.Request(url, json.dumps({"model": model, "prompt": "Reply with one short sentence: stock of rice is 4 units, demand 2 per day.", "stream": False}).encode(), {"Content-Type": "application/json"})
try: print("OK:", json.loads(urllib.request.urlopen(req, timeout=60).read())["response"])
except Exception as e: print("FAILED:", e, "\nInstall Ollama, run `ollama pull " + model + "`, then retry.")
