BEGIN;

CREATE SCHEMA IF NOT EXISTS stg;

-- Camada temporaria da carga atual. Esta tabela e truncada antes de cada
-- arquivo novo e recebe somente valores limpos, normalizados e tipados.
CREATE TABLE IF NOT EXISTS stg.embargo_icmbio (
    id_carga               UUID NOT NULL,
    embargo_id_fonte       BIGINT NOT NULL,
    numero_embargo         VARCHAR(255) NOT NULL,
    numero_auto_infracao   VARCHAR(255),
    numero_processo        VARCHAR(255),

    data_embargo           DATE,
    municipio              VARCHAR(150) NOT NULL,
    uf                     VARCHAR(20) NOT NULL,
    codigo_cnuc            VARCHAR(30) NOT NULL,
    nome_unidade           VARCHAR(200) NOT NULL,
    tipo_infracao          VARCHAR(200) NOT NULL,
    artigo_1               VARCHAR(30) NOT NULL,
    artigo_2               VARCHAR(30) NOT NULL,
    origem                 VARCHAR(30) NOT NULL,
    serie                  VARCHAR(30) NOT NULL,

    area_original          VARCHAR(255),
    area_ha                NUMERIC(18, 4),
    area_valida            BOOLEAN NOT NULL DEFAULT FALSE,
    hash_registro          CHAR(64) NOT NULL,
    data_processamento     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_stg_embargo_icmbio
        PRIMARY KEY (id_carga, embargo_id_fonte),
    CONSTRAINT ck_stg_embargo_uf
        CHECK (uf = 'NAO_INFORMADA' OR uf ~ '^[A-Z]{2}$'),
    CONSTRAINT ck_stg_embargo_area_nao_negativa
        CHECK (area_ha IS NULL OR area_ha >= 0),
    CONSTRAINT ck_stg_embargo_area_consistente
        CHECK (
            (area_valida = TRUE AND area_ha IS NOT NULL)
            OR
            (area_valida = FALSE AND area_ha IS NULL)
        ),
    CONSTRAINT ck_stg_embargo_hash
        CHECK (hash_registro ~ '^[0-9a-f]{64}$'),
    CONSTRAINT fk_stg_embargo_carga
        FOREIGN KEY (id_carga)
        REFERENCES controle.carga (id_carga)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

COMMENT ON TABLE stg.embargo_icmbio IS
    'Carga atual de embargos apos limpeza, normalizacao e conversao de tipos.';
COMMENT ON COLUMN stg.embargo_icmbio.hash_registro IS
    'SHA-256 dos atributos de negocio usado para detectar alteracoes entre cargas.';

CREATE INDEX IF NOT EXISTS idx_stg_embargo_id_fonte
    ON stg.embargo_icmbio (embargo_id_fonte);

CREATE INDEX IF NOT EXISTS idx_stg_embargo_hash
    ON stg.embargo_icmbio (hash_registro);

COMMIT;