BEGIN;

-- Migration para bancos criados antes da etapa Python de extracao.
ALTER TABLE controle.carga
    DROP CONSTRAINT IF EXISTS ck_controle_carga_status;

ALTER TABLE controle.carga
    ADD CONSTRAINT ck_controle_carga_status
    CHECK (
        status IN (
            'INICIADA',
            'SEM_ALTERACAO',
            'ARQUIVO_BAIXADO',
            'RAW_CARREGADA',
            'STG_CARREGADA',
            'CONCLUIDA',
            'ERRO'
        )
    );

COMMIT;