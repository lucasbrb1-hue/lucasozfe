"""Configurações locais do usuário (ex: chave de API da Anthropic).

A chave é salva em um arquivo de configuração no diretório do próprio
usuário (fora do código-fonte/repositório), em texto simples - adequada
para uso em computador pessoal/de confiança. Cada usuário do software tem
sua própria chave, salva apenas na sua máquina; não commite nem compartilhe
esse arquivo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR_NAME = "spt_estacas"
CONFIG_FILENAME = "config.json"


def get_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_DIR_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR_NAME


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILENAME


def _load_raw() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict) -> None:
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    path = get_config_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # chmod não é suportado/necessário em todas as plataformas (ex: Windows)


def load_api_key() -> str | None:
    return _load_raw().get("anthropic_api_key") or None


def save_api_key(api_key: str) -> None:
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("Chave de API não pode ser vazia.")
    data = _load_raw()
    data["anthropic_api_key"] = api_key
    _save_raw(data)


def clear_api_key() -> None:
    data = _load_raw()
    data.pop("anthropic_api_key", None)
    _save_raw(data)


def resolve_api_key() -> str | None:
    """Chave efetiva a ser usada: a variável de ambiente ANTHROPIC_API_KEY
    tem prioridade (uso avançado/CI); caso não esteja definida, usa a chave
    salva pelo usuário na aba de Configurações."""

    return os.environ.get("ANTHROPIC_API_KEY") or load_api_key()
