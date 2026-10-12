from __future__ import annotations

from datetime import datetime
from uuid import UUID

import psycopg
from psycopg import Connection

from icmbio_pipeline.configuracao import Configuracao


def conectar(configuracao: Configuracao) -> Connection:
    return psycopg.connect(**configuracao.parametros_conexao())


def buscar_ultimo_hash(conexao: Connection) -> str | None:
    consulta = """
        SELECT hash_sha256
        FROM controle.carga
        WHERE status IN (
            'SEM_ALTERACAO',
            'ARQUIVO_BAIXADO',
            'RAW_CARREGADA',
            'STG_CARREGADA',
            'CONCLUIDA'
        )
        ORDER BY data_inicio DESC
        LIMIT 1
    """

    with conexao.cursor() as cursor:
        cursor.execute(consulta)
        registro = cursor.fetchone()

    if registro is None:
        return None
    return registro[0].strip()


def registrar_carga(
    conexao: Connection,
    id_carga: UUID,
    arquivo_origem: str,
    hash_arquivo: str,
    status: str,
    data_fim: datetime | None = None,
) -> None:
    comando = """
        INSERT INTO controle.carga (
            id_carga,
            data_inicio,
            data_fim,
            arquivo_origem,
            hash_sha256,
            status
        )
        VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s)
    """

    with conexao.cursor() as cursor:
        cursor.execute(
            comando,
            (id_carga, data_fim, arquivo_origem, hash_arquivo, status),
        )