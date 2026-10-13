from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pg8000.dbapi import Connection

from icmbio_pipeline.banco import (
    buscar_ultima_carga_para_stg,
    conectar,
    finalizar_carga_stg,
)
from icmbio_pipeline.configuracao import carregar_configuracao


LOG = logging.getLogger(__name__)
TAMANHO_LOTE = 500


def _limpar_texto(valor: str | None) -> str | None:
    if valor is None:
        return None

    texto = " ".join(valor.strip().split())
    return texto or None


def _texto_obrigatorio(
    valor: str | None,
    padrao: str = "NAO_INFORMADO",
) -> str:
    texto = _limpar_texto(valor)
    return texto.upper() if texto else padrao


def _texto_opcional(valor: str | None) -> str | None:
    texto = _limpar_texto(valor)
    return texto.upper() if texto else None


def _converter_data(valor: str | None) -> date | None:
    texto = _limpar_texto(valor)

    if texto is None:
        return None

    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


def _sem_acentos(valor: str) -> str:
    texto_normalizado = unicodedata.normalize("NFKD", valor)
    return "".join(
        caractere
        for caractere in texto_normalizado
        if not unicodedata.combining(caractere)
    )


def _converter_decimal(valor: str) -> Decimal | None:
    texto = valor.replace(" ", "")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None

    if numero < 0:
        return None
    return numero


def converter_area(valor: str | None) -> tuple[str | None, Decimal | None, bool]:
    area_original = _limpar_texto(valor)

    if area_original is None:
        return None, None, False

    texto = _sem_acentos(area_original.lower())

    termos_invalidos = (
        "nao informada",
        "nao informado",
        "nao especificada",
        "nao especificado",
    )

    if any(termo in texto for termo in termos_invalidos):
        return area_original, None, False

    numero_isolado = re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", texto)

    if numero_isolado:
        area_ha = _converter_decimal(numero_isolado.group(0))
        return area_original, area_ha, area_ha is not None

    numero_com_hectare = re.search(
        r"([0-9][0-9.,]*)\s*(?:ha|hectare|hectares)\b",
        texto,
    )

    if numero_com_hectare:
        area_ha = _converter_decimal(numero_com_hectare.group(1))
        return area_original, area_ha, area_ha is not None

    numero_com_metro_quadrado = re.search(
        r"([0-9][0-9.,]*)\s*(?:m2|m\^2|metros? quadrados?)\b",
        texto,
    )

    if numero_com_metro_quadrado:
        area_m2 = _converter_decimal(numero_com_metro_quadrado.group(1))

        if area_m2 is not None:
            area_ha = area_m2 / Decimal("10000")
            return area_original, area_ha, True

    return area_original, None, False


def _calcular_hash(valores: tuple[object, ...]) -> str:
    partes = []

    for valor in valores:
        if valor is None:
            partes.append("")
        elif isinstance(valor, date):
            partes.append(valor.isoformat())
        elif isinstance(valor, Decimal):
            partes.append(format(valor, "f"))
        elif isinstance(valor, bool):
            partes.append("1" if valor else "0")
        else:
            partes.append(str(valor))

    conteudo = "\x1f".join(partes)
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def _transformar_registro(registro: tuple[object, ...]) -> tuple[object, ...]:
    (
        vw_num_emb,
        numero_emb,
        numero_ai,
        processo,
        data_embargo,
        municipio,
        uf,
        cnuc,
        nome_uc,
        tipo_infra,
        artigo_1,
        artigo_2,
        origem,
        serie,
        area,
    ) = registro

    embargo_id_fonte = int(str(vw_num_emb).strip())
    numero_embargo = _texto_obrigatorio(str(numero_emb))
    numero_auto_infracao = _texto_opcional(numero_ai)
    numero_processo = _texto_opcional(processo)
    data_convertida = _converter_data(data_embargo)
    municipio_tratado = _texto_obrigatorio(municipio)
    uf_tratada = _texto_obrigatorio(uf, padrao="NAO_INFORMADA")
    codigo_cnuc = _texto_obrigatorio(cnuc)
    nome_unidade = _texto_obrigatorio(nome_uc)
    tipo_infracao = _texto_obrigatorio(tipo_infra)
    artigo_1_tratado = _texto_obrigatorio(artigo_1)
    artigo_2_tratado = _texto_obrigatorio(artigo_2)
    origem_tratada = _texto_obrigatorio(origem)
    serie_tratada = _texto_obrigatorio(serie, padrao="NAO_INFORMADA")
    area_original, area_ha, area_valida = converter_area(area)

    valores_tratados = (
        embargo_id_fonte,
        numero_embargo,
        numero_auto_infracao,
        numero_processo,
        data_convertida,
        municipio_tratado,
        uf_tratada,
        codigo_cnuc,
        nome_unidade,
        tipo_infracao,
        artigo_1_tratado,
        artigo_2_tratado,
        origem_tratada,
        serie_tratada,
        area_original,
        area_ha,
        area_valida,
    )

    hash_registro = _calcular_hash(valores_tratados)
    return (*valores_tratados, hash_registro)


def carregar_stg(conexao: Connection, id_carga: UUID) -> int:
    consulta = """
        SELECT
            vw_num_emb,
            numero_emb,
            numero_ai,
            processo,
            data,
            municipio,
            uf,
            cnuc,
            nome_uc,
            tipo_infra,
            artigo_1,
            artigo_2,
            origem,
            serie,
            area
        FROM raw.embargo_icmbio
        WHERE id_carga = %s
        ORDER BY linha_origem
    """

    comando_insert = """
        INSERT INTO stg.embargo_icmbio (
            id_carga,
            embargo_id_fonte,
            numero_embargo,
            numero_auto_infracao,
            numero_processo,
            data_embargo,
            municipio,
            uf,
            codigo_cnuc,
            nome_unidade,
            tipo_infracao,
            artigo_1,
            artigo_2,
            origem,
            serie,
            area_original,
            area_ha,
            area_valida,
            hash_registro
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
    """

    cursor = conexao.cursor()

    try:
        cursor.execute(consulta, (id_carga,))
        registros_raw = cursor.fetchall()

        if not registros_raw:
            raise RuntimeError(
                f"Nenhum registro RAW encontrado para a carga {id_carga}"
            )

        cursor.execute("TRUNCATE TABLE stg.embargo_icmbio")

        quantidade_linhas = 0
        lote: list[tuple[object, ...]] = []

        for registro in registros_raw:
            registro_tratado = _transformar_registro(registro)
            lote.append((id_carga, *registro_tratado))

            if len(lote) == TAMANHO_LOTE:
                cursor.executemany(comando_insert, lote)
                quantidade_linhas += len(lote)
                lote.clear()

        if lote:
            cursor.executemany(comando_insert, lote)
            quantidade_linhas += len(lote)

        return quantidade_linhas
    finally:
        cursor.close()


def executar_carga_stg() -> int:
    configuracao = carregar_configuracao()
    conexao = conectar(configuracao)

    try:
        id_carga = buscar_ultima_carga_para_stg(conexao)

        if id_carga is None:
            raise RuntimeError("Nao existe uma carga RAW pendente")

        LOG.info("Transformando a carga %s para a camada STG", id_carga)
        quantidade_linhas = carregar_stg(conexao, id_carga)
        finalizar_carga_stg(
            conexao=conexao,
            id_carga=id_carga,
            quantidade_linhas=quantidade_linhas,
        )
        conexao.commit()
        LOG.info("%s linhas carregadas na STG", quantidade_linhas)
        return quantidade_linhas
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def principal() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    executar_carga_stg()
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
