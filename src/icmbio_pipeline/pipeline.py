import logging
from datetime import datetime
from uuid import uuid4

from src.icmbio_pipeline.banco import buscar_ultimo_hash, conectar, registrar_carga
from src.icmbio_pipeline.configuracao import carregar_configuracao
from src.icmbio_pipeline.extracao import arquivar_arquivo, baixar_xlsx


LOG = logging.getLogger(__name__)


def executar_extracao() -> str:
    configuracao = carregar_configuracao()
    id_carga = uuid4()

    LOG.info("Baixando arquivo oficial do ICMBio")
    arquivo = baixar_xlsx(
        url=configuracao.url_icmbio,
        pasta_temporaria=configuracao.pasta_temporaria,
        tempo_limite=configuracao.tempo_limite_http,
    )

    try:
        with conectar(configuracao) as conexao:
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
                arquivo.caminho_temporario.unlink(missing_ok=True)
                LOG.info("O arquivo nao mudou desde a ultima carga")
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
            LOG.info("Arquivo novo salvo em %s", caminho_arquivado)
            return "ARQUIVO_BAIXADO"
    except Exception:
        arquivo.caminho_temporario.unlink(missing_ok=True)
        raise


def principal() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    status = executar_extracao()
    LOG.info("Etapa de extracao finalizada com status %s", status)
    return 0
