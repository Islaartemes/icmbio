from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Configuracao:
    url_icmbio: str
    pasta_raw: Path
    pasta_temporaria: Path
    tempo_limite_http: int
    host_banco: str
    porta_banco: int
    nome_banco: str
    usuario_banco: str
    senha_banco: str

    def parametros_conexao(self) -> dict[str, object]:
        return {
            "host": self.host_banco,
            "port": self.porta_banco,
            "dbname": self.nome_banco,
            "user": self.usuario_banco,
            "password": self.senha_banco,
            "connect_timeout": 10,
        }


def _variavel_obrigatoria(nome: str) -> str:
    valor = os.getenv(nome, "").strip()
    if not valor:
        raise ValueError(f"Variavel obrigatoria nao informada: {nome}")
    return valor


def _caminho_do_projeto(valor: str) -> Path:
    caminho = Path(valor)
    if caminho.is_absolute():
        return caminho
    return RAIZ_PROJETO / caminho


def carregar_configuracao() -> Configuracao:
    load_dotenv(RAIZ_PROJETO / ".env")

    return Configuracao(
        url_icmbio=_variavel_obrigatoria("ICMBIO_XLSX_URL"),
        pasta_raw=_caminho_do_projeto(os.getenv("ICMBIO_RAW_DIR", "data/raw")),
        pasta_temporaria=_caminho_do_projeto(
            os.getenv("ICMBIO_TEMP_DIR", "data/tmp")
        ),
        tempo_limite_http=int(os.getenv("HTTP_TIMEOUT_SECONDS", "120")),
        host_banco=os.getenv("POSTGRES_HOST", "localhost"),
        porta_banco=int(os.getenv("POSTGRES_PORT", "5432")),
        nome_banco=_variavel_obrigatoria("POSTGRES_DB"),
        usuario_banco=_variavel_obrigatoria("POSTGRES_USER"),
        senha_banco=_variavel_obrigatoria("POSTGRES_PASSWORD"),
    )