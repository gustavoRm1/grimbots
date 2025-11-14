-- Script SQL para verificar transações do UmbrellaPay
-- Busca transações por gateway_transaction_id

-- IDs das transações fornecidas pelo gateway
WITH transacoes_gateway AS (
    SELECT unnest(ARRAY[
        '454ae28b-fafe-4248-aae5-12fada764bf5',
        'c88246c2-cb24-4f90-8625-8608676ee09a',
        '5c172285-b9ea-4793-a941-afe151b22801',
        '722664db-384a-4342-94cf-603c0eea2702',
        'bdee31e2-7da6-4825-ae54-5d9a5bd48f04',
        'e98fe6ca-4f29-4847-9c94-6ca8e2bb4b7e',
        '86315068-8540-48c9-8979-d98303ad9892',
        'bd9634b4-5898-4ef5-b360-44ec0a2e1e6a',
        '5561f532-9fc2-40f9-bdd6-132be6769bbc',
        '6cff8262-b2fd-43d5-9501-7d7cb57fbfef',
        'e7fa25e1-98c1-4acc-8ff4-6e6c21d9b35e',
        '3420c849-7dea-494d-bd75-e553776f5318',
        '65a6d20a-3a2a-4ded-a035-9969659f42c1',
        'a0cd464c-7361-449c-bcac-286d2e7aa853',
        '92998f88-70a6-470a-b5e6-3145ae9cbe90',
        '18b3488b-b030-417a-9cb5-274c41143609',
        '80211675-fdd4-4edc-9af2-f719278b08ad',
        'b425c8ba-accf-42a8-8bf7-734bbc6145f0',
        '358d6cb7-84eb-49f7-b9fe-0adbb67377f2',
        'df22dff0-388e-4a20-8161-a541fe72fd98',
        'f68dd1f7-700c-4de4-b626-d05c2136ffea',
        '62d3863f-e747-4b67-92de-a49689bd6bbe',
        'fd2ffd9e-ac58-44a0-b0d0-9cf28cf64b99',
        'd0dde35f-fed1-4645-8e56-81d226fc1914',
        '63a02dd9-1d70-48ac-8036-4eff20350d2b',
        'feac4996-713b-48ad-929d-2d0c30f856f7',
        '27deeea7-7f4a-4a1b-9145-9a9d558eeacb',
        'f0212d7f-269e-49dd-aeea-212a521d2e1',
        '8c15646f-3b76-49ea-8dd9-00339536099c',
        '6330117a-cda7-4da7-a65e-82d7d086d95e',
        '425a5f31-7733-4682-a07c-4152e2945182',
        '283f2b4b-f0f4-4460-a405-259443a5cb1f',
        '61e95772-4cd5-48bd-a3de-4176e29a2569',
        'd5b97666-9eaf-442e-aaba-eee53e96cad8',
        'b4eba878-a6a5-472e-9feb-ad3e4f434513',
        'bfc9a555-113b-432f-8c1b-f7963308d325',
        'bba23567-908a-41e0-8051-586869655ebe',
        '1a71167d-62ea-4ac5-a088-925e5878d0c9',
        '78366e3e-999b-4a5a-8232-3e442bd480eb',
        '4ee2b3c0-0910-41aa-9aa4-64af9b387028',
        'f4d8d570-3de9-4ebf-b74e-0f8991acf989',
        '1e988422-d007-43b9-9b73-c5beae715404',
        '748651d6-ad22-4459-9763-a97f5aa63572',
        '7c9a5e2d-a584-49f4-bc8f-0a4e7f6d9934',
        '8739b70e-a3f9-425f-8f8a-f2db1945bde9',
        'eccb8530-7667-4642-89d7-fa9f60871445',
        '828b626d-b31e-4405-9607-303331b36ef0',
        '870957c7-8440-44bc-b8ec-dea5863304fa',
        '4515f361-d30f-4496-aa6b-682cd48a4e5c',
        'e30aef35-be81-4eb6-a890-0deb76cf1016',
        '65a4184d-54b5-438f-8091-bf067297394f',
        '09895fa4-854f-40a5-8bf2-6501c7286919',
        'ff651b4f-6f6a-42cf-bb91-4658b8c1576c',
        '9e7e184e-9c29-4fa2-8020-12e4aedfbd11',
        'a14a152b-aa62-473d-af81-2142c1d64483',
        'd8dbb9f9-ec93-46ff-a788-2b32c640bd80',
        '4b82d6f4-464d-44a2-8fb6-dd095d4d3dd5',
        'eefedc4d-fa76-4589-8043-6f800ee46995',
        '063a0a5d-eed1-4f7e-bbf2-bb353dee5d82'
    ]) AS gateway_id
)
-- 1. TRANSAÇÕES PAGAS (PAID)
SELECT 
    'PAGAS' as tipo,
    p.gateway_transaction_id,
    p.payment_id,
    p.status,
    p.amount as valor_payment,
    p.customer_user_id as cpf,
    p.customer_name as nome,
    p.customer_username as telefone,
    p.created_at,
    p.paid_at
FROM payments p
INNER JOIN transacoes_gateway tg ON p.gateway_transaction_id = tg.gateway_id
WHERE p.gateway_type = 'umbrellapag'
  AND p.status = 'paid'
ORDER BY p.paid_at DESC;

-- 2. TRANSAÇÕES PENDENTES (PENDING)
SELECT 
    'PENDENTES' as tipo,
    p.gateway_transaction_id,
    p.payment_id,
    p.status,
    p.amount as valor_payment,
    p.customer_user_id as cpf,
    p.customer_name as nome,
    p.customer_username as telefone,
    p.created_at,
    p.paid_at
FROM payments p
INNER JOIN transacoes_gateway tg ON p.gateway_transaction_id = tg.gateway_id
WHERE p.gateway_type = 'umbrellapag'
  AND p.status = 'pending'
ORDER BY p.created_at DESC;

-- 3. TRANSAÇÕES NÃO ENCONTRADAS
SELECT 
    'NAO_ENCONTRADAS' as tipo,
    tg.gateway_id,
    NULL as payment_id,
    NULL as status,
    NULL as valor_payment,
    NULL as cpf,
    NULL as nome,
    NULL as telefone,
    NULL as created_at,
    NULL as paid_at
FROM transacoes_gateway tg
LEFT JOIN payments p ON p.gateway_transaction_id = tg.gateway_id AND p.gateway_type = 'umbrellapag'
WHERE p.id IS NULL
ORDER BY tg.gateway_id;

-- 4. RESUMO
SELECT 
    COUNT(CASE WHEN p.status = 'paid' THEN 1 END) as total_pagas,
    COUNT(CASE WHEN p.status = 'pending' THEN 1 END) as total_pendentes,
    COUNT(CASE WHEN p.id IS NULL THEN 1 END) as total_nao_encontradas,
    SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as valor_total_pagas,
    SUM(CASE WHEN p.status = 'pending' THEN p.amount ELSE 0 END) as valor_total_pendentes
FROM transacoes_gateway tg
LEFT JOIN payments p ON p.gateway_transaction_id = tg.gateway_id AND p.gateway_type = 'umbrellapag';

