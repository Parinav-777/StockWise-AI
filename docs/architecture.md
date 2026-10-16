# Architecture
React (Vite, Tailwind, Recharts) -> /api/v1 FastAPI -> engine.py (forecast, anomalies, restock, budget MILP) + store.py (SQLite: products, sales, imports, analyses) + Ollama (explanations only).
Numbers always come from engine.py; the language model only rewrites computed facts. Analyses are persisted and reloadable by ID.
