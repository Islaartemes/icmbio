from pathlib import Path

import pandas as pd

from icmbio_pipeline.configuracao import carregar_configuracao


def localizar_arquivo_mais_recente(pasta_raw: Path) -> Path:
    arquivos = list(pasta_raw.rglob("*.xlsx"))

    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum arquivo XLSX encontrado em: {pasta_raw}"
        )

    return max(
        arquivos,
        key=lambda arquivo: arquivo.stat().st_mtime,
    )


def inspecionar_arquivo(caminho_arquivo: Path) -> None:
    with pd.ExcelFile(
        caminho_arquivo,
        engine="openpyxl",
    ) as arquivo_excel:
        print(f"Arquivo: {caminho_arquivo}")
        print(
            f"Planilhas encontradas: "
            f"{arquivo_excel.sheet_names}"
        )

        for nome_planilha in arquivo_excel.sheet_names:
            dados = pd.read_excel(
                arquivo_excel,
                sheet_name=nome_planilha,
            )

            print()
            print(f"Planilha: {nome_planilha}")
            print(f"Quantidade de linhas: {len(dados)}")
            print(
                f"Quantidade de colunas: "
                f"{len(dados.columns)}"
            )
            print()
            print("Colunas encontradas:")

            for numero, coluna in enumerate(
                dados.columns,
                start=1,
            ):
                tipo = dados[coluna].dtype
                valores_ausentes = int(
                    dados[coluna].isna().sum()
                )

                print(
                    f"{numero:02d}. {coluna} | "
                    f"tipo: {tipo} | "
                    f"ausentes: {valores_ausentes}"
                )


def principal() -> int:
    configuracao = carregar_configuracao()

    caminho_arquivo = localizar_arquivo_mais_recente(
        configuracao.pasta_raw
    )

    inspecionar_arquivo(caminho_arquivo)

    return 0


if __name__ == "__main__":
    raise SystemExit(principal())