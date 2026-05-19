# 🔧 Executar no Servidor

## 📋 Passo 1: Verificar o arquivo atual

Execute no servidor:

```bash
cd /root/grimbots
bash show_bot_config_info.sh
```

Isso vai mostrar:
- Quantas linhas tem o arquivo
- Quais componentes estão presentes
- Se está completo ou não

## 📋 Passo 2: Restaurar do backup

Se o arquivo estiver incompleto, execute:

```bash
cd /root/grimbots
bash restore_bot_config_server.sh
```

Isso vai:
1. Fazer backup do arquivo atual
2. Tentar restaurar do backup do Git
3. Verificar se está completo
4. Mostrar próximos passos

## 📋 Passo 3: Se não funcionar

Se não conseguir restaurar do backup, você pode:

1. **Ver o conteúdo do arquivo no servidor:**
   ```bash
   cd /root/grimbots
   head -100 templates/bot_config.html
   tail -100 templates/bot_config.html
   wc -l templates/bot_config.html
   ```

2. **Copiar o conteúdo e me enviar** para eu recriar o arquivo completo

3. **Ou me dizer o que está faltando** e eu recrio baseado no que sei

## 🎯 Objetivo

Garantir que o arquivo `templates/bot_config.html` no servidor tenha:
- ✅ ~5000+ linhas
- ✅ Todas as funções Alpine.js
- ✅ CSS completo
- ✅ HTML completo
- ✅ Integração com flow_editor.js
- ✅ Order bumps, subscriptions, downsells, upsells
- ✅ Flow editor visual

## 📝 Após restaurar

Se conseguir restaurar, faça commit:

```bash
cd /root/grimbots
git add templates/bot_config.html
git commit -m "fix(bot_config): restore complete functional bot_config.html"
git push origin main
```

