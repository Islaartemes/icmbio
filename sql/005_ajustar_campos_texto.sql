BEGIN;

DROP VIEW IF EXISTS dw.vw_embargo_atual;

ALTER TABLE stg.embargo_icmbio
    ALTER COLUMN numero_auto_infracao TYPE TEXT;

ALTER TABLE stg.embargo_icmbio
    ALTER COLUMN area_original TYPE TEXT;

ALTER TABLE dw.fato_embargo
    ALTER COLUMN numero_auto_infracao TYPE TEXT;

ALTER TABLE dw.fato_embargo
    ALTER COLUMN area_original TYPE TEXT;

CREATE VIEW dw.vw_embargo_atual AS
SELECT
    f.*
FROM dw.fato_embargo AS f
WHERE f.presente_na_fonte = TRUE;

COMMENT ON VIEW dw.vw_embargo_atual IS
    'Embargos encontrados na publicacao mais recente processada com sucesso.';

COMMIT;