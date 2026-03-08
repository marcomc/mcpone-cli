SHELL := /bin/zsh
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PACKAGE := mcpone_cli
MARKDOWN_FILES := README.md CHANGELOG.md TODO.md docs/*.md
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
INSTALL_NAME ?= mcpone-cli
INSTALL_PATH ?= $(BINDIR)/$(INSTALL_NAME)

.DEFAULT_GOAL := help

.PHONY: help check-deps check-prereqs venv install install-dev install-link uninstall reinstall lint fmt test run clean

help: ## Show available targets
	@awk 'BEGIN { FS = ":.*##" } /^[a-zA-Z_-]+:.*##/ { printf "  %-16s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

check-deps: ## Verify required system prerequisites
	@echo "Checking prerequisites..."
	@command -v python3 >/dev/null 2>&1 \
		|| { echo "✗ python3 not found"; exit 1; }
	@python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" \
		|| { echo "✗ Python 3.11+ required (found $$(python3 --version 2>&1))"; exit 1; }
	@[[ -d "/Applications/McpOne.app" ]] \
		&& echo "✓ /Applications/McpOne.app" \
		|| { echo "✗ Official McpOne Desktop app not found in /Applications"; exit 1; }
	@mkdir -p "$(BINDIR)"
	@echo "✓ $(BINDIR)"
	@if print -r -- "$$PATH" | tr ':' '\n' | grep -Fx "$(BINDIR)" >/dev/null; then \
		echo "✓ $(BINDIR) is on PATH"; \
	else \
		echo "! $(BINDIR) is not on PATH"; \
		echo "  Add this to your shell profile:"; \
		echo "  export PATH=\"$(BINDIR):\$$PATH\""; \
	fi
	@if [[ -f "$(HOME)/Library/Containers/com.ryankolter9.McpOne/Data/Library/Application Support/McpOne/McpOne.sqlite" ]]; then \
		echo "✓ McpOne SQLite database found"; \
	else \
		echo "! McpOne SQLite database not found yet"; \
		echo "  Open McpOne once to let it create its app container and database."; \
	fi

check-prereqs: check-deps ## Alias for check-deps

venv: ## Create the virtual environment
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: check-deps venv ## Install runtime deps and link CLI into ~/.local/bin
	$(PIP) install -e .
	@$(MAKE) install-link

install-dev: check-deps venv ## Install dev deps and link CLI into ~/.local/bin
	$(PIP) install -e ".[dev]"
	@$(MAKE) install-link

install-link: ## Link the installed CLI into ~/.local/bin
	@mkdir -p "$(BINDIR)"
	@[[ -x "$(CURDIR)/$(VENV)/bin/$(INSTALL_NAME)" ]] \
		|| { echo "✗ $(CURDIR)/$(VENV)/bin/$(INSTALL_NAME) not found. Run 'make install' or 'make install-dev' first."; exit 1; }
	@ln -sf "$(CURDIR)/$(VENV)/bin/$(INSTALL_NAME)" "$(INSTALL_PATH)"
	@echo "Installed $(INSTALL_NAME) -> $(INSTALL_PATH)"

uninstall: ## Remove the linked CLI from ~/.local/bin
	@rm -f "$(INSTALL_PATH)"
	@echo "Removed $(INSTALL_PATH)"

reinstall: uninstall install ## Reinstall runtime CLI

lint: install-dev ## Lint Python and Markdown files
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests
	$(PY) -m pymarkdown -d MD013 scan $(MARKDOWN_FILES)

fmt: install-dev ## Auto-format Python files
	$(PY) -m ruff format src tests

test: install-dev ## Run the test suite
	$(PY) -m pytest -q

run: install ## Show CLI help
	"$(INSTALL_PATH)" --help

clean: ## Remove local build and virtualenv artifacts
	rm -rf $(VENV) .pytest_cache .ruff_cache build dist src/*.egg-info(N) *.egg-info(N)
