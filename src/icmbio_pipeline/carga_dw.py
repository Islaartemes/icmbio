import logging
from dataclasses import dataclass
from uuid import UUID

from pg8000.dbapi import Connection

from icmbio_pipeline.banco import (
    buscar_ultima_carga_stg,
    conectar,
    finalizar_carga_dw,
)
from icmbio_pipeline.configuracao import carregar_configuracao


LOG = logging.getLogger(__name__)


@dataclass
class ResultadoCargaDW:
    linhas_fato: int
    registros_novos: int
    registros_alterados: int
    registros_ausentes: int


def carregar_dim_tempo(cursor, id_carga: UUID) -> None:
    comando = """
        INSERT INTO dw.dim_tempo (
            tempo_sk, data_completa, dia, mes,
            nome_mes, trimestre, ano
        )
        SELECT DISTINCT
            TO_CHAR(data_embargo, 'YYYYMMDD')::INTEGER,
            data_embargo,
            EXTRACT(DAY FROM data_embargo)::SMALLINT,
            EXTRACT(MONTH FROM data_embargo)::SMALLINT,
            CASE EXTRACT(MONTH FROM data_embargo)::INTEGER
                WHEN 1 THEN 'Janeiro'
                WHEN 2 THEN 'Fevereiro'
                WHEN 3 THEN 'Marco'
                WHEN 4 THEN 'Abril'
                WHEN 5 THEN 'Maio'
                WHEN 6 THEN 'Junho'
                WHEN 7 THEN 'Julho'
                WHEN 8 THEN 'Agosto'
                WHEN 9 THEN 'Setembro'
                WHEN 10 THEN 'Outubro'
                WHEN 11 THEN 'Novembro'
                WHEN 12 THEN 'Dezembro'
            END,
            EXTRACT(QUARTER FROM data_embargo)::SMALLINT,
            EXTRACT(YEAR FROM data_embargo)::SMALLINT
        FROM stg.embargo_icmbio
        WHERE id_carga = %s
          AND data_embargo IS NOT NULL
        ON CONFLICT (tempo_sk) DO NOTHING
    """

    cursor.execute(comando, (id_carga,))


def carregar_dim_localidade(cursor, id_carga: UUID) -> None:
    comando = """
        INSERT INTO dw.dim_localidade (municipio, uf)
        SELECT DISTINCT municipio, uf
        FROM stg.embargo_icmbio
        WHERE id_carga = %s
        ON CONFLICT (municipio, uf) DO NOTHING
    """

    cursor.execute(comando, (id_carga,))


def carregar_dim_unidade(cursor, id_carga: UUID) -> None:
    comando = """
        INSERT INTO dw.dim_unidade_conservacao (
            codigo_cnuc, nome_unidade
        )
        SELECT codigo_cnuc, MAX(nome_unidade)
        FROM stg.embargo_icmbio
        WHERE id_carga = %s
        GROUP BY codigo_cnuc
        ON CONFLICT (codigo_cnuc) DO UPDATE
        SET nome_unidade = EXCLUDED.nome_unidade
    """

    cursor.execute(comando, (id_carga,))


def carregar_dim_infracao(cursor, id_carga: UUID) -> None:
    comando = """
        INSERT INTO dw.dim_infracao (
            tipo_infracao, artigo_1, artigo_2
        )
        SELECT DISTINCT tipo_infracao, artigo_1, artigo_2
        FROM stg.embargo_icmbio
        WHERE id_carga = %s
        ON CONFLICT (tipo_infracao, artigo_1, artigo_2)
        DO NOTHING
    """

    cursor.execute(comando, (id_carga,))


def carregar_dim_origem(cursor, id_carga: UUID) -> None:
    comando = """
        INSERT INTO dw.dim_origem (origem, serie)
        SELECT DISTINCT origem, serie
        FROM stg.embargo_icmbio
        WHERE id_carga = %s
        ON CONFLICT (origem, serie) DO NOTHING
    """

    cursor.execute(comando, (id_carga,))


def calcular_metricas(
    cursor,
    id_carga: UUID,
) -> ResultadoCargaDW:
    consulta = """
        SELECT
            COUNT(*),
            COUNT(*) FILTER (
                WHERE f.embargo_id_fonte IS NULL
            ),
            COUNT(*) FILTER (
                WHERE f.embargo_id_fonte IS NOT NULL
                  AND (
                      f.hash_registro <> s.hash_registro
                      OR f.presente_na_fonte = FALSE
                  )
            )
        FROM stg.embargo_icmbio AS s
        LEFT JOIN dw.fato_embargo AS f
            ON f.embargo_id_fonte = s.embargo_id_fonte
        WHERE s.id_carga = %s
    """

    cursor.execute(consulta, (id_carga,))
    linhas_fato, novos, alterados = cursor.fetchone()

    consulta_ausentes = """
        SELECT COUNT(*)
        FROM dw.fato_embargo AS f
        WHERE f.presente_na_fonte = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM stg.embargo_icmbio AS s
              WHERE s.id_carga = %s
                AND s.embargo_id_fonte = f.embargo_id_fonte
          )
    """

    cursor.execute(consulta_ausentes, (id_carga,))
    ausentes = cursor.fetchone()[0]

    return ResultadoCargaDW(
        linhas_fato=linhas_fato,
        registros_novos=novos,
        registros_alterados=alterados,
        registros_ausentes=ausentes,
    )


def carregar_fato(cursor, id_carga: UUID) -> None:
    comando = """
        INSERT INTO dw.fato_embargo (
            embargo_id_fonte,
            numero_embargo,
            numero_auto_infracao,
            numero_processo,
            tempo_sk,
            localidade_sk,
            unidade_sk,
            infracao_sk,
            origem_sk,
            quantidade_embargo,
            area_original,
            area_ha,
            area_valida,
            hash_registro,
            presente_na_fonte,
            primeira_carga_id,
            ultima_carga_id,
            data_carga
        )
        SELECT
            s.embargo_id_fonte,
            s.numero_embargo,
            s.numero_auto_infracao,
            s.numero_processo,
            COALESCE(t.tempo_sk, 0),
            l.localidade_sk,
            u.unidade_sk,
            i.infracao_sk,
            o.origem_sk,
            1,
            s.area_original,
            s.area_ha,
            s.area_valida,
            s.hash_registro,
            TRUE,
            s.id_carga,
            s.id_carga,
            CURRENT_TIMESTAMP
        FROM stg.embargo_icmbio AS s
        LEFT JOIN dw.dim_tempo AS t
            ON t.data_completa = s.data_embargo
        JOIN dw.dim_localidade AS l
            ON l.municipio = s.municipio
           AND l.uf = s.uf
        JOIN dw.dim_unidade_conservacao AS u
            ON u.codigo_cnuc = s.codigo_cnuc
        JOIN dw.dim_infracao AS i
            ON i.tipo_infracao = s.tipo_infracao
           AND i.artigo_1 = s.artigo_1
           AND i.artigo_2 = s.artigo_2
        JOIN dw.dim_origem AS o
            ON o.origem = s.origem
           AND o.serie = s.serie
        WHERE s.id_carga = %s
        ON CONFLICT (embargo_id_fonte) DO UPDATE
        SET numero_embargo = EXCLUDED.numero_embargo,
            numero_auto_infracao = EXCLUDED.numero_auto_infracao,
            numero_processo = EXCLUDED.numero_processo,
            tempo_sk = EXCLUDED.tempo_sk,
            localidade_sk = EXCLUDED.localidade_sk,
            unidade_sk = EXCLUDED.unidade_sk,
            infracao_sk = EXCLUDED.infracao_sk,
            origem_sk = EXCLUDED.origem_sk,
            area_original = EXCLUDED.area_original,
            area_ha = EXCLUDED.area_ha,
            area_valida = EXCLUDED.area_valida,
            hash_registro = EXCLUDED.hash_registro,
            presente_na_fonte = TRUE,
            ultima_carga_id = EXCLUDED.ultima_carga_id,
            data_carga = CURRENT_TIMESTAMP
    """

    cursor.execute(comando, (id_carga,))


def marcar_registros_ausentes(
    cursor,
    id_carga: UUID,
) -> None:
    comando = """
        UPDATE dw.fato_embargo AS f
        SET presente_na_fonte = FALSE,
            ultima_carga_id = %s,
            data_carga = CURRENT_TIMESTAMP
        WHERE f.presente_na_fonte = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM stg.embargo_icmbio AS s
              WHERE s.id_carga = %s
                AND s.embargo_id_fonte = f.embargo_id_fonte
          )
    """

    cursor.execute(comando, (id_carga, id_carga))


def carregar_dw(
    conexao: Connection,
    id_carga: UUID,
) -> ResultadoCargaDW:
    cursor = conexao.cursor()

    try:
        carregar_dim_tempo(cursor, id_carga)
        carregar_dim_localidade(cursor, id_carga)
        carregar_dim_unidade(cursor, id_carga)
        carregar_dim_infracao(cursor, id_carga)
        carregar_dim_origem(cursor, id_carga)

        resultado = calcular_metricas(cursor, id_carga)

        carregar_fato(cursor, id_carga)
        marcar_registros_ausentes(cursor, id_carga)

        return resultado
    finally:
        cursor.close()


def executar_carga_dw() -> ResultadoCargaDW:
    configuracao = carregar_configuracao()
    conexao = conectar(configuracao)

    try:
        id_carga = buscar_ultima_carga_stg(conexao)

        if id_carga is None:
            raise RuntimeError(
                "Nao existe uma carga STG pendente"
            )

        LOG.info(
            "Carregando dimensoes e fato para a carga %s",
            id_carga,
        )

        resultado = carregar_dw(conexao, id_carga)

        finalizar_carga_dw(
            conexao=conexao,
            id_carga=id_carga,
            linhas_fato=resultado.linhas_fato,
            registros_novos=resultado.registros_novos,
            registros_alterados=resultado.registros_alterados,
            registros_ausentes=resultado.registros_ausentes,
        )

        conexao.commit()

        LOG.info(
            "DW carregado: %s linhas, "
            "%s novas, %s alteradas e %s ausentes",
            resultado.linhas_fato,
            resultado.registros_novos,
            resultado.registros_alterados,
            resultado.registros_ausentes,
        )

        return resultado

    except Exception:
        conexao.rollback()
        raise

    finally:
        conexao.close()


def principal() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    executar_carga_dw()
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())