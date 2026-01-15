# Opção de posição do preço nos botões de pagamento

## Contexto atual
- Formulário em `templates/bot_config.html` define botões de pagamento com campos: texto, descrição e **Preço (R$)** (`input type="number" x-model.number="button.price"`).
- O preview formata sempre o preço **após** o texto (`R$ <valor>`), usando `toFixed(2)`/`parseFloat(...).toFixed(2)`.
- Não existe configuração para posicionar o preço antes ou depois do texto do botão.

## Problema/Oportunidade
- Usuários querem escolher onde exibir o preço no botão (antes ou depois do texto). Hoje é fixo "depois".

## Requisito
- Tornar a posição do preço configurável por botão, com duas opções:
  - `before`: exibir `R$ <valor>` antes do texto do botão.
  - `after` (padrão atual): exibir `R$ <valor>` depois do texto do botão.

## Proposta de implementação
1) **Estado/dados do botão**
   - Adicionar campo opcional `price_position` no objeto do botão. Valores: `'after'` (default), `'before'`.
   - Compatibilidade: se ausente, assumir `'after'` para não quebrar bots existentes.

2) **UI (bot_config.html)**
   - No bloco do preço, adicionar seletor (radio/select) com rótulos claros:
     - "Preço antes do texto" (`price_position='before'`).
     - "Preço depois do texto" (`price_position='after'`, default).
   - Vincular com `x-model="button.price_position"`.

3) **Preview (bot_config.html)**
   - Ajustar renderização do preview do botão:
     - Se `price_position === 'before'`: mostrar `R$ <valor>` antes do texto.
     - Se `price_position === 'after'`: manter comportamento atual.
   - Reutilizar a mesma formatação numérica (`toFixed(2)` / `parseFloat(...).toFixed(2)`).

4) **Persistência/validação**
   - Se `BotConfig` permite JSON flexível, apenas salvar `price_position` junto aos demais campos do botão.
   - Se houver validação server-side, aceitar `price_position` com default `'after'` quando ausente.

5) **Backwards compatibility**
   - Bots existentes continuam exibindo preço após o texto (default `'after'`).
   - Nenhum impacto em valores numéricos ou lógica de pagamento; é apenas posicionamento visual.

6) **Testes sugeridos**
   - Criar/editar botão com `price_position='before'` e verificar preview.
   - Salvar e recarregar config; garantir que a escolha persiste.
   - Confirmar que valores numéricos e fluxo de pagamento não mudam.

## Próximos passos
- Implementar seletor + binding `price_position` no form de botões em `bot_config.html`.
- Ajustar preview para condicionar a posição do preço.
- (Opcional) Documentar no help/tooltip que a posição é apenas visual, sem afetar valor.
