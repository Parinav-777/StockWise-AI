# Model and license
Candidate: Qwen2.5-0.5B-Instruct via Ollama (`qwen2.5:0.5b`), local inference, no data leaves the machine.
License: the Qwen team lists the 0.5B model as Apache-2.0 - CONFIRM on the official page (huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) before use; larger Qwen2.5 sizes have different licenses.
It is open-weight, not open-source in the full sense (training data and code are not fully released).
Hardware: roughly 1 GB RAM, CPU is enough. Known limits: small model, may phrase answers poorly; it is given only computed facts and its output is advisory. Real inference was NOT verified by the author: run scripts/check_ollama.py.
Data sent to the model: the question plus the short computed fact string only.
