import logging
from datetime import datetime
from uuid import uuid4

from icmbio_pipeline.banco import (
    buscar_ultimo_hash,
    conectar,
    finalizar_carga_dw,
    finalizar_carga_raw,
    finalizar_carga_stg,
    registrar_carga,
)
from icmbio_pipeline.carga_dw import carregar_dw
from icmbio_pipeline.carga_raw import carregar_raw
from icmbio_pipeline.carga_stg import carregar_stg
from icmbio_pipeline.configuracao import carregar_configuracao
from icmbio_pipeline.extracao import (
    arquivar_arquivo,
    baixar_xlsx,
)


LOG = logging.getLogger(__name__)


def executar_pipeline() -> str:
    configuracao = carregar_configuracao()
    id_carga = uuid4()
    conexao = None

    LOG.info("Baixando arquivo oficial do ICMBio")

    arquivo = baixar_xlsx(
        url=configuracao.url_icmbio,
        pasta_temporaria=configuracao.pasta_temporaria,
        tempo_limite=configuracao.tempo_limite_http,
    )

    try:
        conexao = conectar(configuracao)
        ultimo_hash = buscar_ultimo_hash(conexao)

        if ultimo_hash == arquivo.hash_sha256:
            registrar_carga(
                conexao=conexao,
                id_carga=id_carga,
                arquivo_origem=configuracao.url_icmbio,
                hash_arquivo=arquivo.hash_sha256,
                status="SEM_ALTERACAO",
                data_fim=datetime.now().astimezone(),
            )

            conexao.commit()
            arquivo.caminho_temporario.unlink(
                missing_ok=True
            )

            LOG.info(
                "O arquivo nao mudou desde a ultima carga"
            )

            return "SEM_ALTERACAO"

        caminho_arquivado = arquivar_arquivo(
            arquivo_baixado=arquivo,
            pasta_raw=configuracao.pasta_raw,
        )

        registrar_carga(
            conexao=conexao,
            id_carga=id_carga,
            arquivo_origem=configuracao.url_icmbio,
            hash_arquivo=arquivo.hash_sha256,
            status="ARQUIVO_BAIXADO",
        )

        LOG.info(
            "Carregando arquivo na tabela raw.embargo_icmbio"
        )

        quantidade_linhas = carregar_raw(
            conexao=conexao,
            caminho_arquivo=caminho_arquivado,
            id_carga=id_carga,
            arquivo_origem=configuracao.url_icmbio,
        )

        finalizar_carga_raw(
            conexao=conexao,
            id_carga=id_carga,
            quantidade_linhas=quantidade_linhas,
        )

        LOG.info(
            "Transformando a carga para "
            "a tabela stg.embargo_icmbio"
        )

        quantidade_linhas_stg = carregar_stg(
            conexao=conexao,
            id_carga=id_carga,
        )

        finalizar_carga_stg(
            conexao=conexao,
            id_carga=id_carga,
            quantidade_linhas=quantidade_linhas_stg,
        )

        LOG.info(
            "Carregando dimensoes e tabela fato do DW"
        )

        resultado_dw = carregar_dw(
            conexao=conexao,
            id_carga=id_carga,
        )

        finalizar_carga_dw(
            conexao=conexao,
            id_carga=id_carga,
            linhas_fato=resultado_dw.linhas_fato,
            registros_novos=(
                resultado_dw.registros_novos
            ),
            registros_alterados=(
                resultado_dw.registros_alterados
            ),
            registros_ausentes=(
                resultado_dw.registros_ausentes
            ),
        )

        conexao.commit()

        LOG.info(
            "%s linhas na RAW, %s na STG e "
            "%s processadas no DW a partir de %s",
            quantidade_linhas,
            quantidade_linhas_stg,
            resultado_dw.linhas_fato,
            caminho_arquivado,
        )

        return "CONCLUIDA"

    except Exception:
        if conexao is not None:
            conexao.rollback()

        arquivo.caminho_temporario.unlink(
            missing_ok=True
        )

        raise

    finally:
        if conexao is not None:
            conexao.close()


def principal() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )

    status = executar_pipeline()

    LOG.info(
        "Pipeline finalizado com status %s",
        status,
    )

    return 0