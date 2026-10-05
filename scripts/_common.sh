# Shared helpers for scripts/dev*.sh. Sourced, not run. Works with macOS /bin/bash 3.2.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC2034  # used by the scripts that source this file
API_PORT_DEFAULT=8010
# shellcheck disable=SC2034
WEB_PORT_DEFAULT=3010

# An IDE started from the Dock may have a short PATH; add the usual Homebrew dirs.
for _d in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin"; do
  case ":$PATH:" in *":$_d:"*) ;; *) [ -d "$_d" ] && PATH="$PATH:$_d" ;; esac
done
unset _d
export PATH

say() { printf '%s\n' "$*"; }
die() { printf 'xəta: %s\n' "$*" >&2; exit 1; }

port_busy() {
  command -v lsof >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

# .env at the repo root is read by the worker itself. Created from the example
# once (the example has names only, no secrets).
ensure_root_env() {
  if [ ! -f "$ROOT/.env" ] && [ -f "$ROOT/.env.example" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    say "ilk dəfə: .env yaradıldı (.env.example-dan). Açarları lazım olsa ora yazın."
  fi
}

# Python 3.12 venv in <dir>/.venv with the dependencies from <dir>/pyproject.toml.
# $2 = optional extra ("dev"). Uses uv when installed, otherwise python3.12 + pip.
ensure_venv() {
  local dir="$1" extra="${2:-}"
  if [ -x "$dir/.venv/bin/python" ]; then
    return 0
  fi
  say "ilk dəfə: $dir/.venv qurulur (Python 3.12)..."
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 "$dir/.venv" || die "uv venv alınmadı: $dir"
    if [ -n "$extra" ]; then
      uv pip install --python "$dir/.venv/bin/python" -r "$dir/pyproject.toml" --extra "$extra" \
        || die "asılılıqlar quraşdırılmadı: $dir"
    else
      uv pip install --python "$dir/.venv/bin/python" -r "$dir/pyproject.toml" \
        || die "asılılıqlar quraşdırılmadı: $dir"
    fi
    return 0
  fi
  local py
  py="$(command -v python3.12 || true)"
  [ -n "$py" ] || die "Python 3.12 tapılmadı. 'brew install uv' və ya python3.12 quraşdırın."
  "$py" -m venv "$dir/.venv" || die "venv alınmadı: $dir"
  local deps
  deps="$("$dir/.venv/bin/python" - "$dir/pyproject.toml" "$extra" <<'PY'
import sys, tomllib
data = tomllib.load(open(sys.argv[1], "rb"))["project"]
deps = list(data.get("dependencies", []))
if sys.argv[2]:
    deps += data.get("optional-dependencies", {}).get(sys.argv[2], [])
print("\n".join(deps))
PY
)" || die "pyproject.toml oxunmadı: $dir"
  "$dir/.venv/bin/python" -m pip install --upgrade pip >/dev/null
  # One requirement per line; xargs keeps specifiers like "httpx>=0.28,<1" intact.
  printf '%s\n' "$deps" | tr '\n' '\0' | xargs -0 "$dir/.venv/bin/python" -m pip install \
    || die "asılılıqlar quraşdırılmadı: $dir"
}

ensure_node_modules() {
  if [ -d "$ROOT/frontend/node_modules" ]; then
    return 0
  fi
  command -v npm >/dev/null 2>&1 || die "npm tapılmadı. Node.js quraşdırın."
  say "ilk dəfə: frontend/node_modules qurulur (npm)..."
  if [ -f "$ROOT/frontend/package-lock.json" ]; then
    (cd "$ROOT/frontend" && npm ci) || die "npm ci alınmadı"
  else
    (cd "$ROOT/frontend" && npm install) || die "npm install alınmadı"
  fi
}
