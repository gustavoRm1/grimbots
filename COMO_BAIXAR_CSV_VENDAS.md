# 📥 COMO BAIXAR O CSV DE VENDAS PARADISE

## ✅ MUDANÇAS REALIZADAS

Foi adicionado um **botão temporário** no painel de administração que permite fazer download do CSV de vendas Paradise.

### Arquivos Modificados:
1. `app.py` - Nova rota `/admin/download_csv`
2. `templates/admin/dashboard.html` - Botão amarelo temporário no topo

---

## 📋 INSTRUÇÕES PARA USAR

### 1️⃣ FAÇA O DEPLOY DA MUDANÇA

```bash
# No terminal local (Windows)
git add .
git commit -m "temp: botão download CSV vendas Paradise"
git push origin main
```

### 2️⃣ NO VPS, FAÇA PULL E RESTART

```bash
# SSH no VPS
cd ~/grimbots
git pull origin main
sudo systemctl restart grimbots
```

### 3️⃣ COPIE O CSV PARA O DIRETÓRIO DA APLICAÇÃO

```bash
# No VPS, copie o CSV gerado para o diretório do grimbots
cp vendas_paradise_2025-10-21_to_2025-10-27.csv /root/grimbots/
```

**OU** se você já está no diretório `/root/grimbots` quando rodou o script:

```bash
# Verifique se o arquivo existe
ls -lh vendas_paradise_2025-10-21_to_2025-10-27.csv
```

### 4️⃣ ACESSE O PAINEL ADMIN NO BROWSER

1. Acesse: `https://seu-dominio.com/admin`
2. Faça login como admin
3. Você verá um **botão amarelo** no topo da página:
   ```
   📄 Download CSV - Vendas Paradise (21/10 - 27/10)
   [Baixar CSV]
   ```

### 5️⃣ CLIQUE NO BOTÃO "Baixar CSV"

O arquivo será baixado automaticamente com o nome:
`vendas_paradise_2025-10-21_to_2025-10-27.csv`

---

## ⚠️ IMPORTANTE

- Este é um **botão TEMPORÁRIO** apenas para essa situação específica
- Após baixar o CSV, você pode remover o botão e a rota quando quiser
- O arquivo CSV contém todas as vendas confirmadas (PAID) do gateway Paradise entre 21/10 e 27/10

---

## 🔧 REMOVENDO O BOTÃO (DEPOIS DE BAIXAR)

Se quiser remover o botão temporário após baixar o CSV:

```bash
git revert HEAD
git push origin main
```

Ou simplesmente edite e remova:
- A rota `/admin/download_csv` do `app.py`
- O bloco amarelo do `templates/admin/dashboard.html`

