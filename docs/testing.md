# Testing
Backend: `pytest` (forecast horizon/non-negativity, short history, zero demand, anomaly detection, restock and budget limits, MILP vs greedy, upload dedupe, saved analyses, API flow). The AI path is tested only through the offline fallback; a real model needs scripts/check_ollama.py.
Frontend: `cd frontend && npm install && npm run build`.
Manual: load demo, run each page, change budget, upload the templates, open an old analysis, download the report.
