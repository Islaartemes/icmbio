from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pg8000.dbapi import Connection, connect

from icmbio_pipeline.configuracao import Configuracao


def conectar(configuracao: Configuracao) -> Connection:
    return connect(
        host=configuracao.host_banco,
        port=configuracao.porta_banco,
        database=configuracao.nome_banco,
        user=configuracao.usuario_banco,
        password=configuracao.senha_banco,
        timeout=10,
    )


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

    cursor = conexao.cursor()

    try:
        cursor.execute(consulta)
        registro = cursor.fetchone()
    finally:
        cursor.close()

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

    cursor = conexao.cursor()

    try:
        cursor.execute(
            comando,
            (
                id_carga,
                data_fim,
                arquivo_origem,
                hash_arquivo,
                status,
            ),
        )
    finally:
        cursor.close()