from __future__ import annotations

import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

import requests


class ErroArquivoFonte(RuntimeError):
    pass


@dataclass(frozen=True)
class ArquivoBaixado:
    caminho_temporario: Path
    hash_sha256: str
    tamanho_bytes: int


def _validar_xlsx(caminho: Path) -> None:
    if caminho.stat().st_size == 0:
        raise ErroArquivoFonte("O arquivo baixado esta vazio")

    if not zipfile.is_zipfile(caminho):
        raise ErroArquivoFonte("A resposta recebida nao e um arquivo XLSX")

    with zipfile.ZipFile(caminho) as arquivo_zip:
        arquivos_internos = set(arquivo_zip.namelist())
        arquivos_obrigatorios = {"[Content_Types].xml", "xl/workbook.xml"}

        if not arquivos_obrigatorios.issubset(arquivos_internos):
            raise ErroArquivoFonte("O arquivo nao possui a estrutura de um XLSX")

        arquivo_corrompido = arquivo_zip.testzip()
        if arquivo_corrompido:
            raise ErroArquivoFonte(f"O XLSX esta corrompido: {arquivo_corrompido}")


def baixar_xlsx(
    url: str,
    pasta_temporaria: Path,
    tempo_limite: int,
) -> ArquivoBaixado:
    pasta_temporaria.mkdir(parents=True, exist_ok=True)
    caminho_temporario = pasta_temporaria / f"{uuid4()}.xlsx.part"
    calculador_hash = hashlib.sha256()
    tamanho_bytes = 0

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(10, tempo_limite),
            headers={"User-Agent": "icmbio-pipeline/0.1"},
        ) as resposta:
            resposta.raise_for_status()

            with caminho_temporario.open("wb") as arquivo:
                for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                    if not bloco:
                        continue
                    arquivo.write(bloco)
                    calculador_hash.update(bloco)
                    tamanho_bytes += len(bloco)

        _validar_xlsx(caminho_temporario)

        return ArquivoBaixado(
            caminho_temporario=caminho_temporario,
            hash_sha256=calculador_hash.hexdigest(),
            tamanho_bytes=tamanho_bytes,
        )
    except Exception:
        caminho_temporario.unlink(missing_ok=True)
        raise


def arquivar_arquivo(
    arquivo_baixado: ArquivoBaixado,
    pasta_raw: Path,
    data_referencia: date | None = None,
) -> Path:
    data_referencia = data_referencia or date.today()
    pasta_destino = pasta_raw / data_referencia.isoformat()
    pasta_destino.mkdir(parents=True, exist_ok=True)

    nome_arquivo = f"embargos_icmbio_{arquivo_baixado.hash_sha256[:12]}.xlsx"
    caminho_destino = pasta_destino / nome_arquivo

    if caminho_destino.exists():
        arquivo_baixado.caminho_temporario.unlink(missing_ok=True)
        return caminho_destino

    shutil.move(str(arquivo_baixado.caminho_temporario), caminho_destino)
    return caminho_destino
