-- Habilita meta_tracking_enabled para pools enterprise que já têm pixel_id configurado
-- Mas estavam com tracking desligado (default=False na coluna)
--
-- Uso: psql -d <dbname> -f migrations/20260610_enable_meta_tracking_for_enterprise.sql

BEGIN;

UPDATE redirect_pools
SET meta_tracking_enabled = TRUE
WHERE meta_pixel_id IS NOT NULL
  AND meta_pixel_id != ''
  AND meta_tracking_enabled = FALSE;

-- Relatório
SELECT 
    COUNT(*) AS pools_ativadas,
    (SELECT COUNT(*) FROM redirect_pools WHERE meta_tracking_enabled = TRUE) AS total_ativas,
    (SELECT COUNT(*) FROM redirect_pools WHERE meta_pixel_id IS NOT NULL AND meta_pixel_id != '') AS pools_com_pixel
FROM redirect_pools
WHERE meta_pixel_id IS NOT NULL
  AND meta_pixel_id != ''
  AND meta_tracking_enabled = FALSE;

COMMIT;
