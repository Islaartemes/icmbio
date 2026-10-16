# Pipeline de dados de embargos do ICMBio

Projeto acadêmico de Engenharia e Análise de Dados que extrai semanalmente os
dados públicos de embargos do ICMBio, preserva os dados originais, realiza o
tratamento e organiza as informações em um Data Warehouse dimensional no
PostgreSQL.

O projeto cobre três etapas da pós-graduação:

1. construção do pipeline ETL e do Data Warehouse;
2. análise exploratória em Python com Jupyter Notebook;
3. dashboard e storytelling no Power BI.

## Fonte dos dados

Os dados são obtidos do arquivo público disponibilizado pelo ICMBio:

[Download dos embargos do ICMBio](https://www.gov.br/icmbio/pt-br/dados-icmbio/dados_geoespaciais/mapa-tematico-e-dados-geoestatisticos-das-unidades-de-conservacao-federais/embargos_icmbio.xlsx)

O endereço também é configurado pela variável `ICMBIO_XLSX_URL` no `.env`.

## Arquitetura

```text
Arquivo XLSX do ICMBio
          ↓
      Extração
          ↓
 raw.embargo_icmbio
          ↓
 Limpeza e transformação
          ↓
 stg.embargo_icmbio
          ↓
 Carga dimensional
          ↓
 Dimensões + fato_embargo
          ↓
 dw.vw_embargo_atual
       ↙       ↘
Jupyter       Power BI
```

### Camadas do banco

| Camada | Finalidade |
|---|---|
| `controle` | Registra cada execução, seu status, hash e quantidades processadas. |
| `raw` | Preserva os dados como foram recebidos do arquivo oficial. |
| `stg` | Contém a carga atual limpa, normalizada e tipada. |
| `dw` | Contém as dimensões, a tabela fato e a view de embargos atuais. |

Os campos `cpf_cnpj` e `autuado` permanecem somente na RAW. Eles não são
enviados ao Data Warehouse, ao Power BI ou ao GitHub.

## Modelo dimensional

O grão da tabela fato é uma linha para cada embargo identificado por
`vw_num_emb` na fonte oficial.

### Tabela fato

`dw.fato_embargo` contém:

- identificador do embargo na fonte;
- números do embargo, auto de infração e processo;
- chaves das dimensões;
- quantidade do embargo, sempre igual a `1`;
- área original e área válida convertida para hectares;
- hash do registro;
- indicador de presença na publicação atual;
- identificadores da primeira e da última carga.

### Dimensões

| Dimensão | Conteúdo |
|---|---|
| `dw.dim_tempo` | Data, dia, mês, trimestre e ano do embargo. |
| `dw.dim_localidade` | Município e unidade federativa. |
| `dw.dim_unidade_conservacao` | Código CNUC e nome da unidade. |
| `dw.dim_infracao` | Tipo da infração e artigos relacionados. |
| `dw.dim_origem` | Origem e série do documento. |

### View atual

`dw.vw_embargo_atual` apresenta apenas os registros presentes na publicação
mais recente:

```sql
SELECT *
FROM dw.fato_embargo
WHERE presente_na_fonte = TRUE;
```

A view não armazena outra cópia. Quando a fato é atualizada, o resultado da
view muda automaticamente.

## Tecnologias

- Python 3.11 ou superior;
- PostgreSQL 17;
- Docker e Docker Compose;
- pg8000 e openpyxl;
- pandas, NumPy e Matplotlib;
- Jupyter Notebook;
- DBeaver;
- Power BI.

## Estrutura do projeto

```text
.
├── data/
│   ├── raw/                         # XLSX arquivados por data
│   └── tmp/                         # downloads temporários
├── notebooks/
│   └── analise_exploratoria.ipynb
├── sql/
│   ├── 000_create_raw.sql
│   ├── 001_create_dw.sql
│   ├── 002_create_staging.sql
│   ├── 003_create_history.sql
│   ├── 004_add_download_status.sql
│   ├── 005_ajustar_campos_texto.sql
├── src/icmbio_pipeline/
│   ├── __main__.py
│   ├── banco.py
│   ├── carga_dw.py
│   ├── carga_raw.py
│   ├── carga_stg.py
│   ├── configuracao.py
│   ├── extracao.py
│   ├── inspecao.py
│   └── pipeline.py
├── .env.example
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Pré-requisitos

- Docker com Docker Compose;
- Python 3.11 ou superior;
- Git;
- DBeaver, opcional para consultar o PostgreSQL;
- Power BI Desktop para construir o dashboard.

## Configuração do ambiente

### 1. Criar o arquivo `.env`

No Linux:

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Conteúdo esperado:

```dotenv
POSTGRES_DB=icmbio_dw
POSTGRES_USER=icmbio
POSTGRES_PASSWORD=troque_esta_senha
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
TZ=America/Recife

ICMBIO_XLSX_URL=https://www.gov.br/icmbio/pt-br/dados-icmbio/dados_geoespaciais/mapa-tematico-e-dados-geoestatisticos-das-unidades-de-conservacao-federais/embargos_icmbio.xlsx
ICMBIO_RAW_DIR=data/raw
ICMBIO_TEMP_DIR=data/tmp
HTTP_TIMEOUT_SECONDS=120
```

O `.env` contém credenciais locais e está ignorado pelo Git. Apenas o
`.env.example`, sem senha real, deve ser versionado.

### 2. Iniciar o PostgreSQL

```bash
docker compose up -d
```

Verifique o container:

```bash
docker compose ps
```

Na primeira criação do volume, o PostgreSQL executa automaticamente os arquivos
da pasta `sql/` em ordem alfabética. Em um volume já existente, esses scripts
não são executados novamente. Nesse caso, scripts pendentes podem ser aplicados
manualmente pelo DBeaver.

Conexão padrão:

| Campo | Valor padrão |
|---|---|
| Host | `localhost` |
| Porta | `5432` |
| Banco | `icmbio_dw` |
| Usuário | `icmbio` |
| Senha | valor definido em `POSTGRES_PASSWORD` |

### 3. Ambiente Python no Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4. Ambiente Python no Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Se o PowerShell bloquear a ativação, libere scripts apenas na sessão atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Também é possível executar sem ativar o ambiente:

```powershell
.\.venv\Scripts\python.exe -m icmbio_pipeline
```

## Execução do pipeline completo

Na raiz do projeto, execute:

```bash
python -m icmbio_pipeline
```

O comando realiza:

1. download do XLSX oficial;
2. validação da estrutura do arquivo;
3. cálculo e comparação do hash SHA-256;
4. arquivamento em `data/raw/AAAA-MM-DD/`;
5. carga dos dados originais na RAW;
6. limpeza e transformação para a STG;
7. carga das dimensões;
8. inserção ou atualização da fato;
9. identificação de registros ausentes na nova publicação;
10. atualização do controle da carga.

Quando o arquivo é novo, o status final esperado é:

```text
CONCLUIDA
```

Quando o arquivo possui o mesmo hash da última carga concluída, o pipeline não
duplica dados e registra:

```text
SEM_ALTERACAO
```

As alterações no banco são confirmadas juntas. Se ocorrer um erro antes do
`commit`, a transação é desfeita com `rollback`.

## Execução das etapas separadamente

As etapas separadas são úteis para estudo, apresentação e diagnóstico.

### Inspecionar o arquivo mais recente

```bash
python -m icmbio_pipeline.inspecao
```

Apresenta planilhas, colunas, tipos e valores ausentes sem exibir CPF, nome do
autuado ou o conteúdo completo das linhas.

### Carregar a STG

```bash
python -m icmbio_pipeline.carga_stg
```

Exige uma carga com status `RAW_CARREGADA` ou `STG_CARREGADA`.

### Carregar o Data Warehouse

```bash
python -m icmbio_pipeline.carga_dw
```

Exige uma carga com status `STG_CARREGADA`.

No uso semanal normal, basta executar `python -m icmbio_pipeline`.

## Regras principais de transformação

- textos são normalizados e espaços excedentes são removidos;
- ausências nas dimensões recebem categorias como `NAO_INFORMADA`;
- datas são convertidas para `DATE`;
- UFs válidas são padronizadas em letras maiúsculas;
- áreas reconhecidas em hectares são convertidas para `NUMERIC(18,4)`;
- áreas sem interpretação segura permanecem em `area_original` e recebem
  `area_valida = FALSE`;
- cada registro tratado recebe um hash para detectar alterações;
- um embargo ausente na publicação mais recente permanece na fato, mas recebe
  `presente_na_fonte = FALSE`.

## Controle das cargas

A tabela `controle.carga` registra UUID, datas da execução, origem, hash,
status, quantidades da RAW, STG e fato e totais de registros novos, alterados e
ausentes.

Fluxo normal:

```text
ARQUIVO_BAIXADO
      ↓
RAW_CARREGADA
      ↓
STG_CARREGADA
      ↓
CONCLUIDA
```

Se o arquivo não mudou, a execução termina em `SEM_ALTERACAO`.


## Análise exploratória com Jupyter

Com o ambiente ativado, execute:

```bash
jupyter notebook
```

Abra `notebooks/analise_exploratoria.ipynb` e execute as células em ordem com
`Shift + Enter`. O notebook consulta o banco, mas não altera os dados.

A análise contém:

- estrutura e qualidade dos dados;
- valores ausentes e duplicidades;
- indicadores gerais;
- distribuição das áreas;
- possíveis outliers pelo método IQR;
- quantidade e área por UF;
- evolução anual;
- ranking de unidades de conservação e respectivos estados;
- ranking de tipos de infração;
- conclusões para o dashboard.

Possíveis outliers não são excluídos automaticamente. Um valor extremo pode ser
real e deve ser investigado antes de qualquer remoção.

## Preparação para o Power BI

No Power BI, conecte ao PostgreSQL e importe:

- `dw.vw_embargo_atual`;
- `dw.dim_tempo`;
- `dw.dim_localidade`;
- `dw.dim_unidade_conservacao`;
- `dw.dim_infracao`;
- `dw.dim_origem`.

Crie relacionamentos de `1` para `muitos`, com filtro em uma direção:

```text
dim_tempo[tempo_sk]
    1 ─── * vw_embargo_atual[tempo_sk]

dim_localidade[localidade_sk]
    1 ─── * vw_embargo_atual[localidade_sk]

dim_unidade_conservacao[unidade_sk]
    1 ─── * vw_embargo_atual[unidade_sk]

dim_infracao[infracao_sk]
    1 ─── * vw_embargo_atual[infracao_sk]

dim_origem[origem_sk]
    1 ─── * vw_embargo_atual[origem_sk]
```

Indicadores recomendados:

- quantidade de embargos;
- área total válida em hectares;
- percentual de registros com área válida;
- quantidade por UF e município;
- evolução por ano;
- unidades de conservação com mais embargos;
- tipos de infração mais frequentes.

## Testes

```bash
python -m pytest
```

Os testes verificam o download, a validação do XLSX, o cálculo do hash e o
arquivamento do arquivo.

## Decisões de escopo

- O ETL foi desenvolvido em Python, sem Pentaho, mantendo as etapas separadas.
- O PostgreSQL é o banco do Data Warehouse.
- A análise exploratória é realizada no Jupyter.
- O Power BI consome o modelo dimensional do PostgreSQL.
- A análise por WKT e interseções ficou como melhoria futura.
- A RAW preserva as cargas recebidas e a fato indica se o registro ainda está
  presente na fonte. O histórico completo de versões pode ser evoluído depois.

## Melhorias futuras

- agendamento semanal com cron ou Agendador de Tarefas do Windows;
- usuário PostgreSQL somente leitura para o Power BI;
- histórico completo das versões alteradas;
- mapas com geometrias WKT;
- testes adicionais das transformações e da carga dimensional;
- publicação automatizada do dashboard.
