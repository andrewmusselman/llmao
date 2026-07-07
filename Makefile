# llmao — dev workflow. Uses a local virtualenv (.venv) so it works on
# PEP 668 "externally managed" systems (Debian/Ubuntu) without touching the
# system Python.

.PHONY: install run test config proxy build clean

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

# Create the venv and install deps into it.
install: $(VENV)/.installed

$(VENV)/.installed: requirements-dev.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	touch $(VENV)/.installed

# Run the gateway in dev mode (stub auth + mock LLM). No external services.
run: install
	$(PY) -m llmao.app

test: install
	PYTHONPATH=. $(PY) -m pytest tests/ -q

# Regenerate the litellm proxy config from the catalog.
config: install
	$(PY) scripts/render_litellm_config.py > litellm/config.yaml

# Run the real litellm proxy (production backend). Requires litellm[proxy].
proxy: install
	$(PIP) install "litellm[proxy]" >/dev/null
	$(VENV)/bin/litellm --config litellm/config.yaml

# Build the production Docker image (used by Puppet: `make build`).
# Regenerates the litellm config from the catalog first so the image ships
# a config.yaml that matches the catalog.
build: config
	docker build -t llmao:latest .

clean:
	rm -f llmao-state.json demo-state.json *.tmp
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf $(VENV)
