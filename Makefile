# Hayward — dev workflow. Uses a local virtualenv (.venv) so it works on
# PEP 668 "externally managed" systems (Debian/Ubuntu) without touching the
# system Python.

.PHONY: install run test config proxy clean

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
	$(PY) -m hayward.app

test: install
	PYTHONPATH=. $(PY) -m pytest tests/ -q

# Regenerate the litellm proxy config from the catalog.
config: install
	$(PY) scripts/render_litellm_config.py > litellm/config.yaml

# Run the real litellm proxy (production backend). Requires litellm[proxy].
proxy: install
	$(PIP) install "litellm[proxy]" >/dev/null
	$(VENV)/bin/litellm --config litellm/config.yaml

clean:
	rm -f hayward-state.json demo-state.json *.tmp
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf $(VENV)
