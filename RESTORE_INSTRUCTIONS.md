# SCRIPT DE RESTAURACAO DE EMERGENCIA

Se algo der errado, execute:

```powershell
# Restaurar do backup
Copy-Item -Path "backups\backup_pre_limpeza_20251020_203431\*" -Destination . -Recurse -Force

# OU restaurar do archive manualmente consultando:
# ARCHIVE_INDEX.md
```

**Data do Backup:** 2025-10-20 20:34
**Arquivos no Backup:** 2.310
**Tamanho:** 27.4 MB
