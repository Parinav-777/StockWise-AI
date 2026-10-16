# Troubleshooting
- Page says cannot reach backend: start `uvicorn backend.main:app --port 8000`.
- AI offline banner: install Ollama and `ollama pull qwen2.5:0.5b`; everything else still works.
- 409 on upload: that exact file was imported before.
- Reset data: Data Management > Load / reset demo data.
