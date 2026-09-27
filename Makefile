# Common tasks. Personal data stays in raw/ and data/ (gitignored).
APP ?= DEMO0000001

.PHONY: install test lint fmt demo run build
install: ; uv sync --all-extras
test:    ; uv run pytest -q
lint:    ; uv run ruff check src tests && uv run ruff format --check src tests
fmt:     ; uv run ruff format src tests && uv run ruff check --fix src tests
demo:    ; BACKHOME_HOME=examples uv run backhome run DEMO0000001 --no-pdf
run:     ; uv run backhome run $(APP)
build:   ; uv build
