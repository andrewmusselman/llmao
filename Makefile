# llmao — dev workflow. Uses a local virtualenv (.venv) so it works on
# PEP 668 "externally managed" systems (Debian/Ubuntu) without touching the
# system Python.

.PHONY: install run test config proxy build clean

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

# Interpreter used to create the venv; needs Python >= 3.10 (asfquart; the
# Docker image runs 3.12). Auto-detects the newest suitable python3 on PATH,
# without imposing an upper version bound.
# Override on machines where it lives elsewhere:
#   make install PYTHON=/path/to/python3.12
PYTHON ?= $(shell IFS=:; for d in $$PATH; do \
	[ -n "$$d" ] || d=.; \
	for p in "$$d"/python3 "$$d"/python3.*; do \
		[ -x "$$p" ] || continue; \
		"$$p" -c 'import sys; v=sys.version_info; print(f"{v.major:03}{v.minor:03}{v.micro:03} {sys.executable}")' 2>/dev/null; \
	done; \
done | sort -rn | sed -n '1s/^[0-9]* //p')

# Validate on every invocation, but rebuild only when the interpreter or
# requirements changed, or when the existing environment is invalid.
install:
	@test -n "$(PYTHON)" || { \
		echo "error: no Python interpreter found; Python >= 3.10 is required."; \
		echo "       rerun as: make $(MAKECMDGOALS) PYTHON=/path/to/python3.12"; \
		exit 1; }
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { \
		echo "error: $(PYTHON) is $$($(PYTHON) -V 2>&1); Python >= 3.10 is required."; \
		exit 1; }
	@signature="$$($(PYTHON) -c 'import sys; print(sys.executable); print(".".join(map(str, sys.version_info[:3])))')"; \
	current="$$(cat $(VENV)/.interpreter 2>/dev/null || true)"; \
	if [ ! -x $(PY) ] || ! $(PY) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || \
	   [ "$$signature" != "$$current" ] || [ requirements.txt -nt $(VENV)/.installed ] || \
	   [ requirements-dev.txt -nt $(VENV)/.installed ]; then \
		$(PYTHON) -m venv --clear $(VENV) && \
		$(PIP) install --upgrade pip && \
		$(PIP) install -r requirements-dev.txt && \
		printf '%s\n' "$$signature" > $(VENV)/.interpreter && \
		touch $(VENV)/.installed; \
	fi

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
