<?php
// PARADISE CHECKOUT BUILDER - PROXY V30 (Direct Status Check)
$API_TOKEN         = 'sk_c3728b109649c7ab1d4e19a61189dbb2b07161d6955b8f20b6023c55b8a9e722';
$OFFER_HASH        = '';
$PRODUCT_HASH      = 'prod_6c60b3dd3ae2c63e';
$BASE_AMOUNT       = 1997;
$PRODUCT_TITLE     = 'Flix';
$IS_DROPSHIPPING   = false;
$THREE_STEP_CHECKOUT = false;
$TIMER_TEXT        = 'Esta oferta expira em: {{tempo}}';
$TIMER_BG_COLOR    = '#111827';
$TIMER_TEXT_COLOR  = '#ffffff';
$PIX_EXPIRATION_MINUTES = 10;

// Style variables
$ELEMENT_BG_COLOR       = '#FFFFFF';
$ELEMENT_BORDER_RADIUS  = 12;
$CARD_RADIUS            = $ELEMENT_BORDER_RADIUS . 'px';
$BUTTON_RADIUS          = round($ELEMENT_BORDER_RADIUS * 0.8) . 'px';
$INPUT_RADIUS           = round($ELEMENT_BORDER_RADIUS * 0.66) . 'px';

// PIX Modal Texts & Styles
$PIX_MODAL_TITLE                     = 'Pagamento via PIX';
$PIX_MODAL_COPY_BUTTON_TEXT          = 'Copiar código PIX';
$PIX_MODAL_VALUE_TEXT                = '💰 Valor:';
$PIX_MODAL_EXPIRATION_TEXT           = '🕒 Válido até:';
$PIX_MODAL_SECURE_PAYMENT_TEXT       = 'Pagamento seguro via PIX';
$PIX_MODAL_BG_COLOR                  = '#ffffff';
$PIX_MODAL_TEXT_COLOR                = '#1f2937';
$PIX_MODAL_INFO_TEXT_COLOR           = '#0f172a';
$PIX_MODAL_SECURE_PAYMENT_TEXT_COLOR = '#00c27a';
$PIX_MODAL_BUTTON_COLOR              = '#00c27a';
$PIX_MODAL_BUTTON_TEXT_COLOR         = '#FFFFFF';
$PIX_MODAL_INPUT_BG_COLOR            = '#f9fafb';
$PIX_MODAL_INPUT_BORDER_COLOR        = '#d1d5db';
$PIX_MODAL_INPUT_TEXT_COLOR          = '#374151';
// Data
$ALL_ORDER_BUMPS      = json_decode(base64_decode('W10='), true);
$ALL_COUPONS = json_decode(base64_decode('W10='), true);
$ALL_TESTIMONIALS     = json_decode(base64_decode('W10='), true);
$ALL_BANNERS          = json_decode(base64_decode('W10='), true);
$ALL_VIDEOS           = json_decode(base64_decode('W10='), true);
$ALL_TEXT_BLOCKS      = json_decode(base64_decode('W10='), true);
$COMPONENT_ORDER      = json_decode(base64_decode('WyJzaW5nbGV0b25faWRlbnRpdHkiLCJzaW5nbGV0b25fcGF5bWVudCJd'), true);
$SOCIAL_PROOF_SETTINGS = json_decode(base64_decode('eyJlbmFibGVkIjpmYWxzZSwibmFtZXMiOltdLCJwYXlvdXRNZXNzYWdlIjoie3tuYW1lfX0gYWNhYm91IGRlIHBhZ2FyIHt7dmFsdWV9fSIsInBheW91dE1pbiI6MTUwLCJwYXlvdXRNYXgiOjUwMCwiaW5pdGlhbERlbGF5Ijo1LCJkaXNwbGF5RHVyYXRpb24iOjQsImludGVydmFsTWluIjo4LCJpbnRlcnZhbE1heCI6MjB9'), true);
$SECURITY_SEAL_SETTINGS = json_decode(base64_decode('eyJlbmFibGVkIjpmYWxzZSwiYmFja2dyb3VuZENvbG9yIjoiI0ZGRkZGRiIsIml0ZW1zIjpbeyJpZCI6InNlYWwtMSIsImljb24iOiJleWUtc2xhc2giLCJ0aXRsZSI6IkRhZG9zIHByb3RlZ2lkb3MiLCJ0ZXh0IjoiT3Mgc2V1cyBkYWRvcyBzw6NvIGNvbmZpZGVuY2lhaXMgZSBzZWd1cm9zLiJ9LHsiaWQiOiJzZWFsLTIiLCJpY29uIjoibG9jayIsInRpdGxlIjoiUGFnYW1lbnRvIDEwMCUgU2VndXJvIiwidGV4dCI6IkFzIGluZm9ybWHDp8O1ZXMgZGVzdGEgY29tcHJhIHPDo28gY3JpcHRvZ3JhZmFkYXMuIn0seyJpZCI6InNlYWwtMyIsImljb24iOiJhY2FkZW1pYy1jYXAiLCJ0aXRsZSI6IkNvbnRlw7pkbyBBcHJvdmFkbyIsInRleHQiOiIxMDAlIHJldmlzYWRvIGUgYXByb3ZhZG8gcG9yIHByb2Zpc3Npb25haXMifSx7ImlkIjoic2VhbC00IiwiaWNvbiI6InNoaWVsZCIsInRpdGxlIjoiR2FyYW50aWEgZGUgNyBkaWFzIiwidGV4dCI6IlZvY8OqIGVzdGEgcHJvdGVnaWRvIHBvciB1bWEgZ2FyYW50aWEgZGUgc2F0aXNmYcOnw6NvIn1dfQ=='), true);
$STEP_ORDERS          = json_decode(base64_decode('eyJzdGVwMSI6WyJzaW5nbGV0b25faWRlbnRpdHkiXSwic3RlcDIiOlsic2luZ2xldG9uX2FkZHJlc3MiXSwic3RlcDMiOlsic2luZ2xldG9uX3N1bW1hcnkiLCJzaW5nbGV0b25fYnVtcHMiLCJzaW5nbGV0b25fcGF5bWVudCIsInNpbmdsZXRvbl9zZWN1cml0eV9zZWFsIl19'), true);
$SHIPPING_SETTINGS = json_decode(base64_decode('W10='), true);
$QUANTITY_SELECTOR_SETTINGS = json_decode(base64_decode('W10='), true);
// Define as configurações do checkout para a função de renderização
$checkout_settings = [
    'buttonColor' => '#21bfeb',
    'headerColor' => '#21bfeb',
    'headerTextColor' => '#ffffff',
    'headerText' => 'Compra Segura e Rápida',
    'summaryText' => 'Você está adquirindo:',
    'productLogoURL' => 'https://multi.paradisepags.com/uploads/product_images/store_177_68cc0b6d75e9c_ONLYPRIV.png',
    'title' => 'Flix',
    'amountFormatted' => 'R$ ' . number_format(1997 / 100, 2, ',', '.'),
    'buttonText' => 'PAGAR AGORA',
    'fields' => [
        'name' => true,
        'email' => true,
        'phone' => false,
        'document' => false,
        'cep' => false
    ]
];
// Create maps for efficient lookup
$banners_map = array_column($ALL_BANNERS, null, 'id');
$videos_map = array_column($ALL_VIDEOS, null, 'id');
$testimonials_map = array_column($ALL_TESTIMONIALS, null, 'id');
$text_blocks_map = array_column($ALL_TEXT_BLOCKS, null, 'id');
$all_components_map = [
    'banners' => $banners_map,
    'videos' => $videos_map,
    'testimonials' => $testimonials_map,
    'text_blocks' => $text_blocks_map
];
// Agrupa todas as variáveis "globais" em um único array para passar para a função de renderização
$php_globals = [
    'ELEMENT_BG_COLOR' => $ELEMENT_BG_COLOR,
    'CARD_RADIUS' => $CARD_RADIUS,
    'INPUT_RADIUS' => $INPUT_RADIUS,
    'BUTTON_RADIUS' => $BUTTON_RADIUS,
    'ALL_ORDER_BUMPS' => $ALL_ORDER_BUMPS,
    'IS_DROPSIPPING' => $IS_DROPSIPPING,
    'THREE_STEP_CHECKOUT' => $THREE_STEP_CHECKOUT,
    'SECURITY_SEAL_SETTINGS' => $SECURITY_SEAL_SETTINGS,
    'QUANTITY_SELECTOR_SETTINGS' => $QUANTITY_SELECTOR_SETTINGS,

    
    'SHIPPING_SETTINGS' => $SHIPPING_SETTINGS
];
// --- AJAX ENDPOINTS ---

// --- AJAX ENDPOINTS ---
// Endpoint for AJAX coupon validation
if (isset($_GET['action']) && $_GET['action'] === 'validate_coupon' && !$THREE_STEP_CHECKOUT) {
    header('Content-Type: application/json');
    $code = $_GET['code'] ?? '';
    $found_coupon = null;
    foreach ($ALL_COUPONS as $coupon) {
        if (strcasecmp($coupon['code'], $code) === 0) {
            $found_coupon = $coupon;
            break;
        }
    }

    if ($found_coupon) {
        echo json_encode(['success' => true, 'coupon' => $found_coupon]);
    } else {
        http_response_code(404);
        echo json_encode(['success' => false, 'message' => 'Cupom inválido ou expirado.']);
    }
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json');
    $api_url = 'https://multi.paradisepags.com/api/v1/transaction.php';
    $customer_data = $_POST;
    $utms = $_POST['utms'] ?? [];

    // --- FAKE DATA GENERATION FOR DISABLED FIELDS V3.1 ---
    $cpfs = ['42879052882', '07435993492', '93509642791', '73269352468', '35583648805', '59535423720', '77949412453', '13478710634', '09669560950', '03270618638'];
    $firstNames = ['João', 'Marcos', 'Pedro', 'Lucas', 'Mateus', 'Gabriel', 'Daniel', 'Bruno', 'Maria', 'Ana', 'Juliana', 'Camila', 'Beatriz', 'Larissa', 'Sofia', 'Laura'];
    $lastNames = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves', 'Pereira', 'Lima', 'Gomes', 'Costa', 'Ribeiro', 'Martins', 'Carvalho'];
    $ddds = ['11', '21', '31', '41', '51', '61', '71', '81', '85', '92', '27', '48'];
    $emailProviders = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com.br', 'uol.com.br', 'terra.com.br'];
    $generatedName = null;

    if (empty($customer_data['name']) && !true) {
        $randomFirstName = $firstNames[array_rand($firstNames)];
        $randomLastName = $lastNames[array_rand($lastNames)];
        $generatedName = $randomFirstName . ' ' . $randomLastName;
        $customer_data['name'] = $generatedName;
    }
    if (empty($customer_data['email']) && !true) {
        $nameForEmail = $generatedName ?? ($customer_data['name'] ?? ($firstNames[array_rand($firstNames)] . ' ' . $lastNames[array_rand($lastNames)]));
        $nameParts = explode(' ', (string)$nameForEmail, 2);
        
        $normalize = fn($str) => preg_replace('/[^w]/', '', strtolower(iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $str) ?? ''));
        
        $emailUserParts = [];
        if (!empty($nameParts[0])) {
            $part1 = $normalize($nameParts[0]);
            if (strlen($part1) > 0) $emailUserParts[] = $part1;
        }
        if (isset($nameParts[1])) {
            $part2 = $normalize($nameParts[1]);
            if (strlen($part2) > 0) $emailUserParts[] = $part2;
        }

        if (empty($emailUserParts)) {
            $emailUserParts[] = 'cliente';
        }

        $emailUser = implode('.', $emailUserParts) . mt_rand(100, 999);
        $customer_data['email'] = $emailUser . '@' . $emailProviders[array_rand($emailProviders)];
    }
    // ALTERAÇÃO 1: Garante que o telefone sempre exista
    if (empty($customer_data['phone_number'])) {
        $customer_data['phone_number'] = $ddds[array_rand($ddds)] . '9' . mt_rand(10000000, 99999999);
    }
    if (empty($customer_data['document']) && !false) {
        $customer_data['document'] = $cpfs[array_rand($cpfs)];
    }
    // --- END FAKE DATA ---

    if (!$IS_DROPSHIPPING) {
        $customer_data['street_name'] = $customer_data['street_name'] ?? 'Rua do Produto Digital'; $customer_data['number'] = $customer_data['number'] ?? '0'; $customer_data['complement'] = $customer_data['complement'] ?? 'N/A'; $customer_data['neighborhood'] = $customer_data['neighborhood'] ?? 'Internet'; $customer_data['city'] = $customer_data['city'] ?? 'Brasil'; $customer_data['state'] = $customer_data['state'] ?? 'BR';
        if (empty($customer_data['zip_code'])) { $customer_data['zip_code'] = '00000000'; }
    }
// ... (código anterior)

// --- DYNAMIC PRICE CALCULATION V2 ---
// 1. Inicia com o valor base (produto x quantidade)
$quantity = isset($_POST['quantity']) && is_numeric($_POST['quantity']) ? max(1, (int)$_POST['quantity']) : 1;
$total_amount = $BASE_AMOUNT * $quantity;
$order_bumps_value = 0;
// 2. SOMA OS ORDER BUMPS (LÓGICA QUE FALTAVA) para formar o subtotal
if (!empty($_POST['orderbump']) && is_array($_POST['orderbump'])) {
    $all_bumps_map = array_column($ALL_ORDER_BUMPS, null, 'offerHash');
    foreach ($_POST['orderbump'] as $bump_hash) {
        if (isset($all_bumps_map[$bump_hash])) {
            $total_amount += $all_bumps_map[$bump_hash]['price'];
            $order_bumps_value += $all_bumps_map[$bump_hash]['price'];
        }
    }
}

// 3. APLICA O CUPOM (AGORA NO LOCAL CORRETO) sobre o subtotal (produto + bumps)
if (!$THREE_STEP_CHECKOUT && isset($_POST['coupon_code']) && !empty($_POST['coupon_code'])) {
    $applied_coupon = null;
    foreach ($ALL_COUPONS as $c) {
        if (strcasecmp($c['code'], $_POST['coupon_code']) === 0) {
            $applied_coupon = $c;
            break;
        }
    }

    if ($applied_coupon) {
        if ($applied_coupon['type'] === 'fixed') {
            $total_amount -= $applied_coupon['value'];
        } elseif ($applied_coupon['type'] === 'percentage') {
            // O desconto agora é calculado sobre o total que já inclui os bumps
            $discount_value = $total_amount * ($applied_coupon['value'] / 100);
            $total_amount -= $discount_value;
        }
    }
}

// 4. SOMA O FRETE POR ÚLTIMO (não recebe desconto)
if ($IS_DROPSHIPPING && isset($_POST['shipping_price']) && is_numeric($_POST['shipping_price'])) {
    $total_amount += (int)$_POST['shipping_price'];
}

// 5. Garante que o total não seja negativo
$total_amount = max(0, $total_amount);
// --- END DYNAMIC PRICE ---
    // Add Shipping Cost

// ... (código anterior)

    $reference = 'CKO-' . uniqid();
    $clean_document = preg_replace('/\D/', '', $customer_data['document'] ?? '');
    $clean_phone = preg_replace('/\D/', '', $customer_data['phone_number'] ?? '');

    $payload = [
      "amount" => round($total_amount - $order_bumps_value),
        "description" => $PRODUCT_TITLE,
        "reference" => $reference,
      "checkoutUrl" => $_POST['checkout_url'] ?? '', // <-- ADICIONE ESTA LINHA
        "productHash" => $PRODUCT_HASH, // <-- ADICIONADO AQUI
        "orderbump" => array_values(array_filter($_POST['orderbump'] ?? [])),
        "customer" => [
            'name' => $customer_data['name'] ?? 'N/A',
            'email' => $customer_data['email'] ?? 'na@na.com',
            'document' => $clean_document,
            'phone' => $clean_phone
        ]
    ];

    // Add tracking object if UTMs are present
    if (!empty($utms)) {
        $payload['tracking'] = [];
      $tracking_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'src', 'sck', 'fbc', 'fbp'];
        foreach ($tracking_keys as $key) {
            if (!empty($utms[$key])) {
                $payload['tracking'][$key] = $utms[$key];
            }
        }
        // Ensure we don't send an empty tracking object
        if (empty($payload['tracking'])) {
            unset($payload['tracking']);
        }
    }

    // Adiciona o endereço ao payload se for dropshipping OU se um CEP opcional foi enviado
    if (($IS_DROPSHIPPING || !$IS_DROPSHIPPING) && !empty($customer_data['zip_code'])) {
        $payload['address'] = [
            // Para produtos digitais, preenchemos os outros campos com valores padrão se não existirem
            "street" => $customer_data['street_name'] ?? 'Rua do Produto Digital',
            "number" => $customer_data['number'] ?? '0',
            "neighborhood" => $customer_data['neighborhood'] ?? 'Internet',
            "city" => $customer_data['city'] ?? 'Brasil',
            "state" => $customer_data['state'] ?? 'BR',
            "zipcode" => preg_replace('/\D/', '', $customer_data['zip_code'] ?? ''),
            "complement" => $customer_data['complement'] ?? ''
        ];
    }

  
// ... (código seguinte)

    $ch = curl_init($api_url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Accept: application/json',
        'X-API-Key: ' . $API_TOKEN
    ]);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curl_error = curl_error($ch);
    curl_close($ch);

    if ($curl_error) { http_response_code(500); echo json_encode(['error' => 'cURL Error: ' . $curl_error]); exit; }
    
    $response_data = json_decode($response, true);
    if ($response_data && $http_code >= 200 && $http_code < 300) {
        // Updated for new API version: check for nested transaction data
        $transaction_data = $response_data['transaction'] ?? $response_data;

        // Reshape response for frontend compatibility
        $frontend_response = [
            'hash' => $transaction_data['id'] ?? $reference,
            'pix' => [
                'pix_qr_code' => $transaction_data['qr_code'] ?? '',
                'expiration_date' => $transaction_data['expires_at'] ?? null
            ],
            'amount_paid' => round($total_amount)
        ];
        http_response_code($http_code);
        echo json_encode($frontend_response);
    } else {
        http_response_code($http_code);
        echo $response;
    }
    exit;
}

// ... O RESTO DO ARQUIVO CONTINUA IGUAL ...
// --- RENDER FUNCTION ---
// ...
function render_checkout_component($component_id, $all_components_map, $checkout_settings, $php_globals) {
    // Extrai as variáveis do array $php_globals para uso local
    extract($php_globals);
    
    $checkout_settings = [
        'buttonColor' => '#21bfeb',
        'headerColor' => '#21bfeb',
        'headerTextColor' => '#ffffff',
        'headerText' => 'Compra Segura e Rápida',
        'summaryText' => 'Você está adquirindo:',
        'productLogoURL' => 'https://multi.paradisepags.com/uploads/product_images/store_177_68cc0b6d75e9c_ONLYPRIV.png',
        'title' => 'Flix',
        'amountFormatted' => 'R$ ' . number_format(1997 / 100, 2, ',', '.'),
        'buttonText' => 'PAGAR AGORA',
        'fields' => [
            'name' => true,
            'email' => true,
            'phone' => false,
            'document' => false,
            'cep' => false
        ]
    ];
    
    $is_full_width = in_array($component_id, ['singleton_header']);
    if (!$is_full_width) echo '<div class="constrained-width">';

    // --- RENDER COMPONENT LOGIC ---
    if ($component_id === 'singleton_header') {
        if (!empty($checkout_settings['headerText'])) {
            echo '<header style="background-color: ' . htmlspecialchars($checkout_settings['headerColor'] ?? '#1f2937') . '; color: ' . htmlspecialchars($checkout_settings['headerTextColor'] ?? '#ffffff') . ';" class="w-full p-3 text-center text-sm font-semibold shadow-md">' . htmlspecialchars($checkout_settings['headerText']) . '</header>';
        }
    } elseif (strpos($component_id, 'banner-') === 0 && isset($all_components_map['banners'][$component_id])) {
        $banner = $all_components_map['banners'][$component_id];
        echo '<div class="w-full bg-gray-200 overflow-hidden" style="border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';"><img src="' . htmlspecialchars($banner['path']) . '" alt="Banner" class="w-full object-cover"></div>';
    } elseif (strpos($component_id, 'video-') === 0 && isset($all_components_map['videos'][$component_id])) {
        $video = $all_components_map['videos'][$component_id];
        echo '<div class="overflow-hidden shadow-lg" style="border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';"><div class="video-container">' . ($video['type'] === 'url' ? '<video controls playsinline src="' . htmlspecialchars($video['content']) . '"></video>' : $video['content']) . '</div></div>';
    } elseif (strpos($component_id, 'textBlock-') === 0 && isset($all_components_map['text_blocks'][$component_id])) {
        $text_block = $all_components_map['text_blocks'][$component_id];
        $bg_color = !empty($text_block['backgroundColor']) ? htmlspecialchars($text_block['backgroundColor']) : $ELEMENT_BG_COLOR;
        $text_color = !empty($text_block['textColor']) ? 'color: ' . htmlspecialchars($text_block['textColor']) . ';' : '';
        echo '<div class="prose text-center max-w-none shadow-lg p-6" style="background-color: ' . $bg_color . '; ' . $text_color . ' border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">' . $text_block['content'] . '</div>';
    } elseif ($component_id === 'singleton_summary') {
        echo '<div class="shadow-lg p-5" style="background-color: ' . htmlspecialchars($ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
        if (!empty($checkout_settings['summaryText'])) echo '<p class="text-sm text-gray-600 font-medium mb-4">' . htmlspecialchars($checkout_settings['summaryText']) . '</p>';
        echo '<div class="flex items-center space-x-4">';
        if (!empty($checkout_settings['productLogoURL'])) echo '<img src="' . htmlspecialchars($checkout_settings['productLogoURL']) . '" alt="' . htmlspecialchars($checkout_settings['title']) . '" class="w-16 h-16 object-cover flex-shrink-0 border border-gray-200 p-1" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';">';
      
        echo '<div class="flex-grow"><h3 class="font-bold text-gray-800">' . htmlspecialchars($checkout_settings['title']) . '</h3><p class="text-lg font-semibold text-green-600">' . $checkout_settings['amountFormatted'] . '</p></div></div>';

if ($QUANTITY_SELECTOR_SETTINGS['enabled']) {
    echo '<div class="mt-4 flex items-center justify-between">';
    echo '<label class="text-sm font-medium text-gray-600">Quantidade</label>';
    echo '<div class="flex items-center border border-gray-200 rounded-md overflow-hidden" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';">';
    echo '<button type="button" id="quantity-minus" class="px-3 h-8 text-base font-bold text-gray-500 bg-gray-50 hover:bg-gray-100 transition-colors">-</button>';
    echo '<input type="text" name="quantity" id="quantity-input" value="' . $QUANTITY_SELECTOR_SETTINGS['default'] . '" min="' . $QUANTITY_SELECTOR_SETTINGS['min'] . '" max="' . $QUANTITY_SELECTOR_SETTINGS['max'] . '" class="w-10 h-8 text-center text-sm font-semibold text-gray-800 bg-white border-x border-gray-200 focus:outline-none" readonly>';
    echo '<button type="button" id="quantity-plus" class="px-3 h-8 text-base font-bold text-gray-500 bg-gray-50 hover:bg-gray-100 transition-colors">+</button>';
    echo '</div></div>';
}
        
        echo '<div id="order-bump-summary"></div><div id="coupon-summary" class="hidden text-sm mt-3 pt-3 border-t border-dashed"></div><hr class="my-4">';
        echo '<div class="flex justify-between items-center"><p class="font-bold text-lg text-gray-800">Total:</p><p id="total-price" class="font-bold text-lg text-gray-800">' . $checkout_settings['amountFormatted'] . '</p></div></div>';
    } elseif ($component_id === 'singleton_bumps' && !empty($ALL_ORDER_BUMPS)) {
        echo '<div class="shadow-lg p-6 sm:p-8 space-y-4" style="background-color: ' . htmlspecialchars($ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
        foreach($ALL_ORDER_BUMPS as $bump) {
            echo '<label class="block p-4 border-2 border-dashed border-gray-300 hover:border-[' . $checkout_settings['buttonColor'] . '] hover:bg-violet-50 transition-all cursor-pointer has-[:checked]:border-[' . $checkout_settings['buttonColor'] . '] has-[:checked]:ring-2 has-[:checked]:ring-[' . $checkout_settings['buttonColor'] . '] has-[:checked]:bg-violet-50" style="border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
         echo '<div class="flex items-start"><input type="checkbox" name="orderbump[]" value="' . htmlspecialchars($bump['offerHash'] ?? '') . '" data-price="' . $bump['price'] . '" class="order-bump-checkbox form-checkbox h-6 w-6 text-[' . $checkout_settings['buttonColor'] . '] mt-1 mr-4 rounded-md border-gray-400 focus:ring-[' . $checkout_settings['buttonColor'] . ']">';
            echo '<div class="flex-grow flex items-center space-x-4">';
            if(!empty($bump['logoUrl'])) echo '<img src="' . htmlspecialchars($bump['logoUrl']) . '" alt="' . htmlspecialchars($bump['title']) . '" class="w-12 h-12 object-cover flex-shrink-0" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';">';
            echo '<div class="flex-grow"><div class="flex items-center justify-between"><h4 class="font-bold text-gray-800 text-lg">' . htmlspecialchars($bump['title']) . '</h4><p class="font-semibold text-green-600 whitespace-nowrap">+ R$ ' . number_format($bump['price'] / 100, 2, ',', '.') . '</p></div>';
            echo '<p class="text-sm text-gray-600 mt-1">' . htmlspecialchars($bump['description']) . '</p></div></div></div></label>';
        }
        echo '</div>';


} elseif ($component_id === 'singleton_coupons' && !$THREE_STEP_CHECKOUT) {
    echo '<div class="shadow-lg p-6 sm:p-8" style="background-color: ' . htmlspecialchars($ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
    echo '<div id="coupon-area"><label for="coupon-code" class="block text-sm font-medium text-gray-600 mb-1">Cupom de Desconto</label>';
    echo '<div class="flex gap-2"><input type="text" id="coupon-code" placeholder="Insira seu cupom" class="flex-grow p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';">';
    echo '<button type="button" id="apply-coupon-btn" class="px-5 py-2 font-semibold text-white" style="background-color: ' . $checkout_settings['buttonColor'] . '; border-radius: ' . htmlspecialchars($BUTTON_RADIUS) . ';">Aplicar</button></div>';
    echo '<p id="coupon-message" class="text-sm mt-2"></p></div></div>';
    } elseif ($component_id === 'singleton_identity' || $component_id === 'singleton_address') {
        $is_identity = $component_id === 'singleton_identity';
        echo '<div class="shadow-lg p-6 sm:p-8" style="background-color: ' . htmlspecialchars($ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
        echo '<div class="flex items-center mb-6"><span class="text-white rounded-full h-8 w-8 flex items-center justify-center font-bold text-lg mr-3 flex-shrink-0" style="background-color: ' . $checkout_settings['buttonColor'] . ';">';
        echo $is_identity ? '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>' : '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.125-.504 1.125-1.125V14.25m-17.25 4.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H3.375A2.25 2.25 0 001.125 6.75v10.5a2.25 2.25 0 002.25 2.25z" /></svg>';
        echo '</span><h2 class="text-xl font-bold text-gray-800">' . ($is_identity ? 'Identifique-se' : 'Endereço de Entrega') . '</h2></div>';
        echo '<div class="space-y-4">';
        if ($is_identity) {
            if ($checkout_settings['fields']['name']) echo '<div><label for="name" class="block text-sm font-medium text-gray-600 mb-1">Nome e sobrenome</label><input type="text" id="name" name="name" placeholder="Nome e sobrenome" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
            if ($checkout_settings['fields']['email']) echo '<div><label for="email" class="block text-sm font-medium text-gray-600 mb-1">E-mail</label><input type="email" id="email" name="email" placeholder="E-mail" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
            if ($checkout_settings['fields']['phone']) echo '<div><label for="phone" class="block text-sm font-medium text-gray-600 mb-1">Telefone/WhatsApp</label><input type="tel" id="phone" name="phone_number" placeholder="(21) 99999-9999" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
            if ($checkout_settings['fields']['document']) echo '<div><label for="document" class="block text-sm font-medium text-gray-600 mb-1">CPF</label><input type="text" id="document" name="document" placeholder="000.000.000-00" required maxlength="14" class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
            if (!$THREE_STEP_CHECKOUT && $IS_DROPSHIPPING) {
                // Address fields for single-page dropshipping
                echo '</div><div class="pt-4 border-t border-gray-200 space-y-4 mt-4">';
                echo '<div><label for="zip_code" class="block text-sm font-medium text-gray-600 mb-1">CEP</label><input type="text" id="zip_code" name="zip_code" placeholder="00000-000" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
                echo '<div><label for="street_name" class="block text-sm font-medium text-gray-600 mb-1">Rua</label><input type="text" id="street_name" name="street_name" required class="w-full p-3 bg-gray-50 border border-gray-300" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
                // ... etc for other address fields
            } elseif (!$THREE_STEP_CHECKOUT && !$IS_DROPSHIPPING && $checkout_settings['fields']['cep']) {
                 echo '<div><label for="zip_code_optional" class="block text-sm font-medium text-gray-600 mb-1">CEP</label><input type="text" id="zip_code_optional" name="zip_code" placeholder="00000-000" class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
            }
        } else { // Address step
             echo '<div><label for="zip_code" class="block text-sm font-medium text-gray-600 mb-1">CEP</label><input type="text" id="zip_code" name="zip_code" placeholder="00000-000" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
             echo '<div><label for="street_name" class="block text-sm font-medium text-gray-600 mb-1">Rua / Logradouro</label><input type="text" id="street_name" name="street_name" placeholder="Ex: Av. Brasil" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
             echo '<div class="grid grid-cols-2 gap-4"> <div><label for="number" class="block text-sm font-medium text-gray-600 mb-1">Número</label><input type="text" id="number" name="number" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div> <div><label for="complement" class="block text-sm font-medium text-gray-600 mb-1">Complemento</label><input type="text" id="complement" name="complement" placeholder="Ex: Apto 101" class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div> </div>';
             echo '<div><label for="neighborhood" class="block text-sm font-medium text-gray-600 mb-1">Bairro</label><input type="text" id="neighborhood" name="neighborhood" placeholder="Ex: Centro" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div>';
             echo '<div class="grid grid-cols-3 gap-4"> <div class="col-span-2"><label for="city" class="block text-sm font-medium text-gray-600 mb-1">Cidade</label><input type="text" id="city" name="city" required class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div> <div><label for="state" class="block text-sm font-medium text-gray-600 mb-1">Estado</label><input type="text" id="state" name="state" placeholder="UF" required maxlength="2" class="w-full p-3 bg-gray-50 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[' . $checkout_settings['buttonColor'] . '] transition" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';"></div> </div>';
        }
// Render Shipping Options
if ($component_id === 'singleton_address') {
if (!empty($SHIPPING_SETTINGS['options'])) {
    echo '<div class="pt-4 mt-4 border-t border-gray-200">';
    echo '<h3 class="text-lg font-bold text-gray-800 mb-3">Opções de Frete</h3>';
    echo '<div class="space-y-3">';
    foreach($SHIPPING_SETTINGS['options'] as $index => $option) {
        $checked = $index === 0 ? 'checked' : '';
        echo '<label class="flex items-center justify-between p-4 border border-gray-200 has-[:checked]:border-[' . $checkout_settings['buttonColor'] . '] has-[:checked]:bg-violet-50 rounded-lg cursor-pointer" style="border-radius: ' . htmlspecialchars($INPUT_RADIUS) . ';">';
        echo '<div class="flex items-center">';
        echo '<input type="radio" name="shipping_price" value="' . $option['price'] . '" data-price="' . $option['price'] . '" class="form-radio h-5 w-5 text-[' . $checkout_settings['buttonColor'] . '] shipping-option" ' . $checked . '>';
        echo '<div class="ml-3"><span class="block font-semibold text-gray-800">' . htmlspecialchars($option['name']) . '</span><span class="block text-sm text-gray-500">' . htmlspecialchars($option['estimatedDeliveryTime']) . '</span></div>';
        echo '</div>';
        echo '<span class="font-semibold text-gray-800">R$ ' . number_format($option['price'] / 100, 2, ',', '.') . '</span>';
        echo '</label>';
    }
    echo '</div></div>';
    }
}
        
        echo '</div></div>';
    } elseif ($component_id === 'singleton_payment') {
        $pix_svg = '<svg class="h-6 w-6 text-[#32BCAD] mr-2 flex-shrink-0" viewBox="0 0 258 258" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M129 258C200.24 258 258 200.24 258 129C258 57.76 200.24 0 129 0C57.76 0 0 57.76 0 129C0 200.24 57.76 258 129 258Z" fill="#32BCAD"/><path d="M136.291 149.337L153.375 132.228H174.19L143.513 162.905H168.083V184.225H89.9174V162.905H114.487L83.8099 132.228H104.625L129 156.618L153.375 132.228L129 107.837L104.625 132.228H83.8099L114.487 101.551H89.9174V80.2305H168.083V101.551H143.513L174.19 132.228L136.291 149.337Z" fill="white"/></svg>';
        echo '<div class="shadow-lg p-6 sm:p-8" style="background-color: ' . htmlspecialchars($ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
        echo '<div class="flex items-center mb-4"><span class="text-white rounded-full h-8 w-8 flex items-center justify-center font-bold text-lg mr-3 flex-shrink-0" style="background-color: ' . $checkout_settings['buttonColor'] . ';"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15A2.25 2.25 0 002.25 6.75v10.5A2.25 2.25 0 004.5 21z" /></svg></span><h2 class="text-xl font-bold text-gray-800">Pagamento</h2></div>';
        echo '<button type="submit" id="pay-button" style="background-color: ' . $checkout_settings['buttonColor'] . '; border-radius: ' . htmlspecialchars($BUTTON_RADIUS) . ';" class="w-full p-4 text-white font-bold text-lg uppercase hover:opacity-90 flex items-center justify-center"><span>' . htmlspecialchars($checkout_settings['buttonText']) . '</span></button>';
        echo '<div class="mt-4 text-center text-gray-500 text-sm flex items-center justify-center gap-2">'  . '<span>Pagamento seguro via <strong>PIX</strong> com aprovação imediata.</span></div>';
        echo '</div>';
    } elseif ($component_id === 'singleton_testimonials' && !$THREE_STEP_CHECKOUT) {
        if (!empty($all_components_map['testimonials'])) {
            echo '<div class="space-y-6">';
            foreach($all_components_map['testimonials'] as $testimonial) {
             render_checkout_component($testimonial['id'], $all_components_map, $checkout_settings, $php_globals);
            }
            echo '</div>';
        }
    } elseif (strpos($component_id, 'testimonial-') === 0 && isset($all_components_map['testimonials'][$component_id])) {
        $testimonial = $all_components_map['testimonials'][$component_id];
        echo '<div class="shadow-lg p-6" style="background-color: ' . htmlspecialchars($ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
        echo '<div class="flex items-start space-x-4">';
        if (!empty($testimonial['avatarUrl'])) {
            echo '<img src="' . htmlspecialchars($testimonial['avatarUrl']) . '" alt="' . htmlspecialchars($testimonial['author']) . '" class="w-12 h-12 rounded-full object-cover">';
        } else {
            echo '<div class="w-12 h-12 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 font-bold text-xl flex-shrink-0">' . strtoupper(substr($testimonial['author'], 0, 1)) . '</div>';
        }
        echo '<div><p class="text-gray-600 italic">"' . htmlspecialchars($testimonial['text']) . '"</p><p class="font-bold text-gray-800 mt-3">- ' . htmlspecialchars($testimonial['author']) . '</p></div></div></div>';
    } elseif ($component_id === 'singleton_security_seal' && $SECURITY_SEAL_SETTINGS['enabled']) {
        $icons = [
            'shield' => '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.286zm0 13.036h.008v.008h-.008v-.008z" /></svg>',
            'lock' => '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 00-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" /></svg>',
            'academic-cap' => '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /><path stroke-linecap="round" stroke-linejoin="round" d="M12 21.75l-3.75-3.75m3.75 3.75V3.75m0 18l3.75-3.75M4.5 6.75A2.25 2.25 0 016.75 4.5h10.5a2.25 2.25 0 012.25 2.25v10.5a2.25 2.25 0 01-2.25 2.25H6.75a2.25 2.25 0 01-2.25-2.25V6.75z" /></svg>',
            'eye-slash' => '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.243 4.243l-4.243-4.243" /></svg>'
        ];
        echo '<div class="shadow-lg" style="background-color: ' . htmlspecialchars($SECURITY_SEAL_SETTINGS['backgroundColor'] ?? $ELEMENT_BG_COLOR) . '; border-radius: ' . htmlspecialchars($CARD_RADIUS) . ';">';
        echo '<div class="divide-y divide-gray-200">';
        foreach ($SECURITY_SEAL_SETTINGS['items'] as $item) {
            echo '<div class="p-4 flex items-center space-x-4">';
            echo '<div class="flex-shrink-0 w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center text-green-600">' . ($icons[$item['icon']] ?? '') . '</div>';
            echo '<div><h4 class="font-bold text-gray-800">' . htmlspecialchars($item['title']) . '</h4><p class="text-sm text-gray-600">' . htmlspecialchars($item['text']) . '</p></div>';
            echo '</div>';
        }
        echo '</div></div>';
    }
    // --- END RENDER COMPONENT ---
    if (!$is_full_width) echo '</div>';
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars('Flix'); ?></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/gh/davidshimjs/qrcodejs/qrcode.min.js"></script>
 <?php if (!empty('')): ?>
<script>
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
    n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
    document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', '<?php echo htmlspecialchars(""); ?>');
    fbq('track', 'PageView');
    
   
    fbq('track', 'InitiateCheckout'); 

</script>
<noscript><img height="1" width="1" style="display:none"
    src="https://www.facebook.com/tr?id=<?php echo htmlspecialchars(""); ?>&ev=PageView&noscript=1"
/></noscript>
<?php endif; ?>
<?php if (!empty('')): ?>
<script>
    !function (w, d, t) {
        w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"],ttq.setAndDefer=function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e},ttq.load=function(e,n){var i="https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{},ttq._i[e]=[],ttq._i[e]._u=i,ttq._t=ttq._t||{},ttq._t[e]=+new Date,ttq._o=ttq._o||{},ttq._o[e]=n||{};var o=document.createElement("script");o.type="text/javascript",o.async=!0,o.src=i+"?sdkid="+e+"&lib="+t;var a=document.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)};
        
        ttq.load('<?php echo htmlspecialchars(""); ?>');
                  ttq.track('InitiateCheckout', {
                content_type: 'product',
                content_id: '<?php echo htmlspecialchars($PRODUCT_HASH); ?>',
                value: <?php echo $BASE_AMOUNT / 100; ?>,
                currency: 'BRL'
            });
    }(window, document, 'ttq');
</script>
<?php endif; ?>
    <style>
        body { background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
        .constrained-width { max-width: 32rem; margin-left: auto; margin-right: auto; padding-left: 1rem; padding-right: 1rem; }
        @media (min-width: 640px) { .constrained-width { padding-left: 0; padding-right: 0; } }
        .form-checkbox { -webkit-appearance: none; -moz-appearance: none; appearance: none; padding: 0; -webkit-print-color-adjust: exact; color-adjust: exact; display: inline-block; vertical-align: middle; background-origin: border-box; -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; user-select: none; flex-shrink: 0; height: 1rem; width: 1rem; color: #14b8a6; background-color: #fff; border-color: #64748b; border-width: 1px; border-radius: .25rem; }
        .form-checkbox:checked { background-image: url("data:image/svg+xml,%3csvg viewBox='0 0 16 16' fill='white' xmlns='http://www.w3.org/2000/svg'%3e%3cpath d='M12.207 4.793a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0l-2-2a1 1 0 011.414-1.414L6.5 9.086l4.293-4.293a1 1 0 011.414 0z'/%3e%3c/svg%3e"); border-color: transparent; background-color: currentColor; background-size: 100% 100%; background-position: center; background-repeat: no-repeat; }
        #pay-button, .step-nav-btn { transition: opacity 0.2s; }
        #pay-button:disabled, .step-nav-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #21bfeb; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; display: inline-block; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        #copy-button { transition: transform 0.1s ease; } #copy-button:active { transform: scale(0.97); }
        .form-step { display: none; animation: fadeIn 0.5s; }
        .form-step.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .video-container { position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000; border-radius: 0.5rem; }
        .video-container iframe, .video-container video { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
        .prose { color: inherit; } .prose h1, .prose h2, .prose h3, .prose b, .prose strong { color: inherit; } .prose p, .prose ul, .prose ol, .prose i { color: inherit; margin-top: 1em; margin-bottom: 1em; }
        .prose.text-center * { text-align: center; }
        .social-proof-toast {
            background-color: rgba(30, 41, 59, 0.9);
            backdrop-filter: blur(5px);
            color: white;
            padding: 12px 16px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1), 0 10px 20px rgba(0,0,0,0.2);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: opacity 0.5s ease-out, transform 0.5s ease-out;
            opacity: 0;
            transform: translateY(20px) scale(0.95);
            margin-top: 10px;
            width: fit-content;
            max-width: 350px;
        }
        .social-proof-toast.show {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
        @keyframes backdropFadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes popupSlideIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <?php if (0 > 0): ?>
    <div id="timer-container" style="background-color: <?php echo htmlspecialchars($TIMER_BG_COLOR); ?>; color: <?php echo htmlspecialchars($TIMER_TEXT_COLOR); ?>; text-align: center; padding: 0.5rem; font-weight: 500; font-size: 0.9rem; position: sticky; top: 0; z-index: 100;">
        <span id="timer-display"></span>
    </div>
    <?php endif; ?>
    
    <?php if (true): ?>
    <form id="payment-form" method="POST" action="">
    <input type="hidden" name="coupon_code" id="applied-coupon-code" value="">
       
<input type="hidden" name="checkout_url" id="checkout_url_field" value="">
    <?php endif; ?>

    <main id="checkout-container" class="space-y-6 <?php echo (!$THREE_STEP_CHECKOUT && !empty($COMPONENT_ORDER) && in_array($COMPONENT_ORDER[0], ['singleton_header'])) ? 'pb-6' : 'py-6'; ?>">
        <?php if ($THREE_STEP_CHECKOUT): ?>
            <div class="constrained-width">
                <div id="step-indicator-container" class="flex justify-between items-center mb-6">
                     <?php $step_titles = ["Identificação", "Endereço", "Pagamento"]; ?>
                     <?php foreach($step_titles as $i => $title): ?>
                        <div class="flex items-center flex-col text-center">
                            <div id="step-bubble-<?php echo $i + 1; ?>" class="step-bubble w-8 h-8 rounded-full flex items-center justify-center font-bold text-white transition-colors bg-gray-400">
                                <?php echo $i + 1; ?>
                            </div>
                            <p id="step-title-<?php echo $i + 1; ?>" class="step-title mt-1 text-xs font-semibold transition-colors text-gray-500"><?php echo $title; ?></p>
                        </div>
                        <?php if ($i < count($step_titles) - 1): ?>
                            <div id="step-line-<?php echo $i + 1; ?>" class="step-line flex-1 h-1 mx-2 transition-colors bg-gray-300"></div>
                        <?php endif; ?>
                     <?php endforeach; ?>
                </div>
            </div>
            
            <div id="form-steps" class="space-y-6">
                <div id="step-1" class="form-step active space-y-6">
                   <?php foreach ($STEP_ORDERS['step1'] as $component_id) { render_checkout_component($component_id, $all_components_map, $checkout_settings, $php_globals); } ?>
                </div>
                <div id="step-2" class="form-step space-y-6">
                 <?php foreach ($STEP_ORDERS['step2'] as $component_id) { render_checkout_component($component_id, $all_components_map, $checkout_settings, $php_globals); } ?>
                </div>
                <div id="step-3" class="form-step space-y-6">
                 <?php foreach ($STEP_ORDERS['step3'] as $component_id) { render_checkout_component($component_id, $all_components_map, $checkout_settings, $php_globals); } ?>
                </div>
            </div>

            <div class="constrained-width mt-6">
                <div id="step-navigation" class="flex gap-4">
                    <button type="button" id="prev-btn" class="w-1/3 p-3 font-bold rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-700 transition" style="display: none; border-radius: <?php echo $BUTTON_RADIUS; ?>;">Voltar</button>
                    <button type="button" id="next-btn" class="flex-1 p-3 font-bold text-white transition" style="background-color: #21bfeb; border-radius: <?php echo $BUTTON_RADIUS; ?>;">Continuar</button>
                </div>
            </div>

        <?php else: // DEFAULT SINGLE-PAGE LAYOUT ?>
         <?php foreach ($COMPONENT_ORDER as $component_id) { render_checkout_component($component_id, $all_components_map, $checkout_settings, $php_globals); } ?>
        <?php endif; ?>
      
      <div class="constrained-width">
        <?php if (!empty('Compra 100% segura. Reembolso garantido em até 7 dias.')): ?> <p class="text-center text-sm text-gray-500 mt-6"><?php echo htmlspecialchars('Compra 100% segura. Reembolso garantido em até 7 dias.'); ?></p> <?php endif; ?>
      </div>
    </main>
    
    <?php if (true): ?>
    </form>
    <?php endif; ?>

    <div id="pix-modal" class="hidden fixed top-0 left-0 w-full h-full bg-black/70 z-[9999] flex items-center justify-center" style="animation:backdropFadeIn 0.3s ease-out forwards;">
      <div style="background:<?php echo htmlspecialchars($PIX_MODAL_BG_COLOR); ?>;padding:32px;border-radius:16px;max-width:380px;width:90%;box-shadow:0 8px 24px rgba(0,0,0,0.2);font-family:Inter, sans-serif;position:relative;animation:popupSlideIn 0.3s ease-out forwards;text-align: center;">
        <button id="pix-modal-close" style="position:absolute;top:10px;right:15px;font-size:24px;color:#9ca3af;background:none;border:none;cursor:pointer;">&times;</button>
        <?php if (!empty($PIX_MODAL_TITLE)): ?>
        <h2 style="margin:0 0 16px;font-size:20px;color:<?php echo htmlspecialchars($PIX_MODAL_TEXT_COLOR); ?>;line-height:1.4;"><?php echo htmlspecialchars($PIX_MODAL_TITLE); ?></h2>
        <?php endif; ?>
        <div style="display:flex;justify-content:center;margin-bottom:16px;">
            <div id="qrcode" style="padding: 4px; background: white; border-radius: 4px; line-height: 0;"></div>
        </div>
        <input id="pix-code-input" type="text" readonly style="width:100%;box-sizing:border-box;padding:12px;font-size:14px;margin-bottom:12px;border:1px solid <?php echo htmlspecialchars($PIX_MODAL_INPUT_BORDER_COLOR); ?>;border-radius:8px;color:<?php echo htmlspecialchars($PIX_MODAL_INPUT_TEXT_COLOR); ?>;background:<?php echo htmlspecialchars($PIX_MODAL_INPUT_BG_COLOR); ?>;text-align:center;font-family:monospace;">
        <button id="copy-button" style="background:<?php echo htmlspecialchars($PIX_MODAL_BUTTON_COLOR); ?>;color:<?php echo htmlspecialchars($PIX_MODAL_BUTTON_TEXT_COLOR); ?>;border:none;width:100%;padding:14px 20px;border-radius:8px;font-weight:600;font-size:15px;cursor:pointer;transition: filter 0.2s ease;margin-bottom:16px;" onmouseover="this.style.filter='brightness(1.1)'" onmouseout="this.style.filter='brightness(1)';">
          <?php echo htmlspecialchars($PIX_MODAL_COPY_BUTTON_TEXT); ?>
        </button>
        <div class="modal-info" style="font-size:14px;color:<?php echo htmlspecialchars($PIX_MODAL_INFO_TEXT_COLOR); ?>;line-height:1.5;text-align: center;">
          <?php if (!empty($PIX_MODAL_VALUE_TEXT)): ?>
          <p style="margin:8px 0;"><?php echo htmlspecialchars($PIX_MODAL_VALUE_TEXT); ?> <strong id="pix-valor">--</strong></p>
          <?php endif; ?>
          <?php if (!empty($PIX_MODAL_EXPIRATION_TEXT)): ?>
          <p style="margin:8px 0;"><?php echo htmlspecialchars($PIX_MODAL_EXPIRATION_TEXT); ?> <span id="modal-expiration">--</span></p>
          <?php endif; ?>
          <?php if (!empty($PIX_MODAL_SECURE_PAYMENT_TEXT)): ?>
          <p class="modal-warning" style="margin:12px 0 0;color:<?php echo htmlspecialchars($PIX_MODAL_SECURE_PAYMENT_TEXT_COLOR); ?>;font-weight:bold;"><?php echo htmlspecialchars($PIX_MODAL_SECURE_PAYMENT_TEXT); ?></p>
          <?php endif; ?>
        </div>
      </div>
    </div>
    
    <div id="social-proof-container" style="position: fixed; bottom: 20px; left: 20px; z-index: 100; pointer-events: none;"></div>

<?php if (!empty('https://t.me/desejuflixbot')): ?>
<script type="text/javascript">
    (function() {
        var backRedirectUrl = '<?php echo htmlspecialchars("https://t.me/desejuflixbot"); ?>';
        var currentUrl = window.location.href;
        var stateObj = { paradiseCheckoutBackredirect: true, timestamp: new Date().getTime() };

        try {
            history.pushState(stateObj, '', currentUrl);
        } catch(e) {
            console.warn("Could not push state for backredirect:", e);
        }

        var hasPopped = false;
        window.addEventListener('popstate', function(event) {
            if (!hasPopped) {
                hasPopped = true;
                window.location.replace(backRedirectUrl);
            }
        });
    })();
</script>
<?php endif; ?>
<script>
const utms = Object.fromEntries(new URLSearchParams(window.location.search));

// Função para ler cookies
const getCookie = (name) => {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : null;
};

// Adiciona os cookies do Facebook ao objeto utms, se existirem
const fbc = getCookie('_fbc');
const fbp = getCookie('_fbp');
if (fbc) utms.fbc = fbc;
if (fbp) utms.fbp = fbp;

const CHECKOUT_ID = '3685527b';

// Função para gerar uma chave de cache dinâmica baseada no valor total
const generateCacheKey = (amount) => 'paradise_checkout_pix_' + CHECKOUT_ID + '_' + amount;

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('checkout_url_field')) {
        document.getElementById('checkout_url_field').value = window.location.href;
    }

    const form = document.getElementById('payment-form');
    const payButton = document.getElementById('pay-button');
    const originalButtonContent = payButton?.innerHTML;

    const totalPriceEl = document.getElementById('total-price');
    const shippingOptions = document.querySelectorAll('.shipping-option');
    const bumpCheckboxes = document.querySelectorAll('.order-bump-checkbox');
    const applyCouponBtn = document.getElementById('apply-coupon-btn');
const couponCodeInput = document.getElementById('coupon-code');
const couponMessageEl = document.getElementById('coupon-message');
const appliedCouponInput = document.getElementById('applied-coupon-code');
 const quantityInput = document.getElementById('quantity-input');
const quantityPlus = document.getElementById('quantity-plus');
const quantityMinus = document.getElementById('quantity-minus');

    let totalAmount = 1997;
    let baseAmount = 1997;
let appliedCoupon = null;
    let validateStep = () => true;
    let currentStep = 1;

    const formatCurrency = (value) => 'R$ ' + (value / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    
    const clearAllCheckoutCaches = () => {
        const cachePrefix = 'paradise_checkout_pix_' + CHECKOUT_ID;
        for (let i = 0; i < localStorage.length; i++){
            const key = localStorage.key(i);
            if (key && key.startsWith(cachePrefix)) {
                localStorage.removeItem(key);
                i--;
            }
        }
        console.log("Todos os caches para este checkout foram limpos.");
    };



const updateTotalPrice = () => {
    const oldTotal = totalAmount;
    const quantity = quantityInput ? parseInt(quantityInput.value, 10) : 1;
    let currentTotal = baseAmount * quantity;

    // Add bumps price
    document.querySelectorAll('.order-bump-checkbox:checked').forEach(box => {
        currentTotal += parseInt(box.dataset.price, 10);
    });

    // Apply coupon
    if (appliedCoupon && !<?php echo $THREE_STEP_CHECKOUT ? 'true' : 'false'; ?>) {
        if (appliedCoupon.type === 'fixed') {
            currentTotal -= appliedCoupon.value;
        } else if (appliedCoupon.type === 'percentage') {
            const discountableAmount = (baseAmount * quantity) + Array.from(document.querySelectorAll('.order-bump-checkbox:checked')).reduce((acc,b) => acc + parseInt(b.dataset.price, 10), 0);
            const discount = discountableAmount * (appliedCoupon.value / 100);
            currentTotal -= discount;
        }
    }

    // Add shipping price
    const selectedShipping = document.querySelector('.shipping-option:checked');
    if (selectedShipping) {
        currentTotal += parseInt(selectedShipping.dataset.price, 10);
    }

    totalAmount = Math.max(0, currentTotal);
    if(totalPriceEl) totalPriceEl.textContent = formatCurrency(totalAmount);
    if (oldTotal !== totalAmount) {
        clearAllCheckoutCaches();
    }
};

    const cameFromBackRedirect = document.referrer.includes(window.location.hostname) && utms.from_checkout;
    if (cameFromBackRedirect) {
        clearAllCheckoutCaches();
    }

    document.querySelectorAll('.order-bump-checkbox').forEach(box => {
        box.addEventListener('change', updateTotalPrice);
    });
shippingOptions.forEach(radio => {
    radio.addEventListener('change', updateTotalPrice);
});

if (quantityInput) {
    const updateQuantity = (amount) => {
        const min = parseInt(quantityInput.min, 10);
        const max = parseInt(quantityInput.max, 10);
        let currentValue = parseInt(quantityInput.value, 10);
        currentValue += amount;
        if (currentValue < min) currentValue = min;
        if (currentValue > max) currentValue = max;
        quantityInput.value = currentValue;
        updateTotalPrice();
    };
    quantityPlus.addEventListener('click', () => updateQuantity(1));
    quantityMinus.addEventListener('click', () => updateQuantity(-1));
}

if (applyCouponBtn) {
    applyCouponBtn.addEventListener('click', async () => {
        const code = couponCodeInput.value.trim();
        if (!code) {
            couponMessageEl.textContent = 'Por favor, insira um código.';
            couponMessageEl.className = 'text-sm mt-2 text-yellow-600';
            return;
        }
        applyCouponBtn.disabled = true;
        applyCouponBtn.textContent = '...';
        try {
            const response = await fetch('?action=validate_coupon&code=' + encodeURIComponent(code));
            const result = await response.json();
            if (response.ok && result.success) {
                appliedCoupon = result.coupon;
                updateTotalPrice();
                couponMessageEl.textContent = 'Cupom aplicado com sucesso!';
                couponMessageEl.className = 'text-sm mt-2 text-green-600';
                appliedCouponInput.value = code;
                document.getElementById('coupon-area').style.opacity = '0.7';
                couponCodeInput.disabled = true;
                applyCouponBtn.textContent = 'Aplicado';
            } else {
                couponMessageEl.textContent = result.message || 'Cupom inválido.';
                couponMessageEl.className = 'text-sm mt-2 text-red-600';
                applyCouponBtn.disabled = false;
                applyCouponBtn.textContent = 'Aplicar';
            }
        } catch (err) {
            couponMessageEl.textContent = 'Erro ao validar cupom.';
            couponMessageEl.className = 'text-sm mt-2 text-red-600';
            applyCouponBtn.disabled = false;
            applyCouponBtn.textContent = 'Aplicar';
        }
    });
}
 
updateTotalPrice(); // Set initial price with default shipping
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const isThreeStep = <?php echo $THREE_STEP_CHECKOUT ? 'true' : 'false'; ?>;

            if (!isThreeStep || (isThreeStep && currentStep === 3)) {
                 if (isThreeStep && (!validateStep(1) || !validateStep(2))) {
                    if (!validateStep(1)) {
                        document.dispatchEvent(new CustomEvent('checkout:step:change', { detail: 1 }));
                    } else if (!validateStep(2)) {
                        document.dispatchEvent(new CustomEvent('checkout:step:change', { detail: 2 }));
                    }
                    form.reportValidity();
                    return; 
                }

                if (!isThreeStep && !form.checkValidity()) {
                    form.reportValidity();
                    return;
                }
                
                const currentCacheKey = generateCacheKey(totalAmount);
                const cachedPix = localStorage.getItem(currentCacheKey);

                if (cachedPix) {
                    const { pixData, expiresAt } = JSON.parse(cachedPix);
                    if (new Date().getTime() < expiresAt) {
                        console.log("Usando PIX do cache para o valor " + formatCurrency(totalAmount));
                        showPixModal(pixData);
                        return;
                    } else {
                        console.log("PIX do cache expirado. Removendo.");
                        localStorage.removeItem(currentCacheKey);
                    }
                }
                
                const submitButton = isThreeStep ? document.getElementById('next-btn') : payButton;
                if (!submitButton) return;
                const originalSubmitContent = submitButton.innerHTML;

                submitButton.disabled = true;
                submitButton.innerHTML = '<div class="loader"></div><span>Processando...</span>';
                
                const formData = new FormData(form);

            for (const key in utms) {
    if (utms[key]) { // Garante que apenas chaves com valor (não nulo ou undefined) sejam enviadas
        formData.append('utms[' + key + ']', utms[key]);
    }
}

                try {
                    const response = await fetch(window.location.href, { method: 'POST', body: formData });
                    const result = await response.json();
                    if (!response.ok) {
                        const errorMessage = result?.errors ? Object.values(result.errors).flat().join(' ') : (result.message || result.error || 'Ocorreu um erro ao gerar o PIX.');
                        throw new Error(errorMessage);
                    }

                    if (result && result.pix && result.pix.pix_qr_code) {
                        const expirationMinutes = <?php echo $PIX_EXPIRATION_MINUTES; ?>;
                        const expiresAt = new Date().getTime() + expirationMinutes * 60 * 1000;
                        const cacheObject = { pixData: result, expiresAt: expiresAt };
                        localStorage.setItem(currentCacheKey, JSON.stringify(cacheObject));
                    }
                    showPixModal(result);
                } catch (error) {
                    console.error('API Error:', error);
                    alert('Erro: ' + error.message);
                } finally {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalSubmitContent;
                }
            }
        });
    }

    if (<?php echo $THREE_STEP_CHECKOUT ? 'true' : 'false'; ?>) {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const steps = Array.from(document.querySelectorAll('.form-step'));
        
        validateStep = (stepNumber) => {
            const currentStepEl = document.getElementById('step-' + stepNumber);
            if (!currentStepEl) return false;
            const inputs = currentStepEl.querySelectorAll('input[required], select[required], textarea[required]');
            for (const input of inputs) {
                if (!input.checkValidity()) {
                    return false;
                }
            }
            return true;
        };

        const updateStepUI = () => {
            steps.forEach((step, index) => {
                step.classList.toggle('active', index + 1 === currentStep);
            });
            
            for(let i=1; i<=3; i++) {
                const bubble = document.getElementById('step-bubble-' + i);
                const title = document.getElementById('step-title-' + i);
                const line = document.getElementById('step-line-' + i);

                if (i < currentStep) {
                    bubble.classList.add('bg-teal-500'); bubble.classList.remove('bg-gray-400', 'bg-red-500');
                    bubble.innerHTML = '✓';
                    title.classList.add('text-gray-800'); title.classList.remove('text-gray-500');
                    if (line) { line.classList.add('bg-teal-500'); line.classList.remove('bg-gray-300'); }
                } else if (i === currentStep) {
                    bubble.classList.add('bg-teal-500'); bubble.classList.remove('bg-gray-400', 'bg-red-500');
                    bubble.innerHTML = i;
                    title.classList.add('text-gray-800'); title.classList.remove('text-gray-500');
                    if (line) { line.classList.remove('bg-teal-500'); line.classList.add('bg-gray-300'); }
                } else {
                     bubble.classList.remove('bg-teal-500', 'bg-red-500'); bubble.classList.add('bg-gray-400');
                     bubble.innerHTML = i;
                     title.classList.remove('text-gray-800'); title.classList.add('text-gray-500');
                     if (line) { line.classList.remove('bg-teal-500'); line.classList.add('bg-gray-300'); }
                }
            }

            prevBtn.style.display = currentStep > 1 ? 'block' : 'none';
            if (currentStep === 3) {
                nextBtn.textContent = '<?php echo htmlspecialchars('PAGAR AGORA'); ?>';
                updateTotalPrice();
            } else {
                nextBtn.textContent = 'Continuar';
            }
            window.scrollTo(0, 0);
        };
        
        const payButtonInStep3 = document.querySelector('#step-3 #pay-button');
        if (payButtonInStep3) {
            payButtonInStep3.style.display = 'none';
        }

        nextBtn.addEventListener('click', () => {
            if (currentStep < 3) {
                if (validateStep(currentStep)) {
                    currentStep++;
                    updateStepUI();
                } else {
                    const bubble = document.getElementById('step-bubble-' + currentStep);
                    if(bubble) bubble.classList.add('bg-red-500');
                    form.reportValidity();
                }
            } else {
                if (form.requestSubmit) {
                    form.requestSubmit();
                } else {
                    form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                }
            }
        });

        prevBtn.addEventListener('click', () => {
            if (currentStep > 1) {
                currentStep--;
                updateStepUI();
            }
        });
        
        document.addEventListener('checkout:step:change', (e) => {
            currentStep = e.detail;
            updateStepUI();
        });
        
        updateTotalPrice();
        updateStepUI();
    }
    
    const modal = document.getElementById('pix-modal');
    const qrCodeContainer = document.getElementById('qrcode');
    const copyButton = document.getElementById('copy-button');
    const pixCodeInputElement = document.getElementById('pix-code-input');
    const pixValorEl = document.getElementById('pix-valor');
    const modalExpirationEl = document.getElementById('modal-expiration');
    const closeModalBtn = document.getElementById('pix-modal-close');
    let qrCodeInstance = null;
    
    function startPaymentChecker(hash) {
        if (window._paymentChecker) {
            clearInterval(window._paymentChecker);
        }
        window._paymentChecker = setInterval(async () => {
            try {
               const response = await fetch('https://multi.paradisepags.com/api/v1/check_status.php?hash=' + hash + '&_=' + new Date().getTime(), {
                   headers: { 'X-API-Key': '<?php echo $API_TOKEN; ?>' }
               });
                if (!response.ok) return;
                const data = await response.json();

                if (data && data.payment_status === 'paid') {
                    clearInterval(window._paymentChecker);
                    clearAllCheckoutCaches();

                    <?php if (!empty('')): ?>
                    if (typeof fbq === 'function') {
                        fbq('track', 'Purchase', { value: totalAmount / 100, currency: 'BRL' });
                    }
                    <?php endif; ?>
                    <?php if (!empty('')): ?>
                    if (typeof ttq === 'function') {
                        ttq.track('CompletePayment', {
                            content_type: 'product',
                            content_id: '<?php echo htmlspecialchars($PRODUCT_HASH); ?>',
                            value: totalAmount / 100,
                            currency: 'BRL'
                        });
                    }
                    <?php endif; ?>

                    <?php if (!empty('https://oacessoliberado.shop/comprarealizada')): ?>
                    const upsellUrl = '<?php echo 'https://oacessoliberado.shop/comprarealizada'; ?>';
                    const params = new URLSearchParams(utms);
                    params.append('fpay', hash);
                    params.append('domain', 'https://go.paradisepagbr.com');
                    
                    const newQueryString = params.toString();
                    const finalUrl = upsellUrl + (upsellUrl.includes('?') ? '&' : '?') + newQueryString;
                    window.location.href = finalUrl;
                    <?php else: ?>
                    const modalContent = modal.querySelector('div');
                    if (modalContent) {
                         modalContent.innerHTML = '<h2 style="font-size:2rem;font-weight:bold;">Pagamento Aprovado!</h2><p>Obrigado por sua compra.</p>';
                    }
                    <?php endif; ?>
                }
            } catch (error) {
                console.error('Payment check failed:', error);
            }
        }, 1500);
    }

function showPixModal(result) {
        const pixCodeText = result?.pix?.pix_qr_code;
        const transactionHash = result?.hash;
        const amountPaid = result?.amount_paid;

        // IGNORA a data da API e SEMPRE calcula a data de expiração localmente.
        let expirationDate = null;
        const expirationMinutes = <?php echo $PIX_EXPIRATION_MINUTES; ?>;
        if (expirationMinutes > 0) {
            expirationDate = new Date(Date.now() + expirationMinutes * 60 * 1000);
        }

        if (!pixCodeText) { throw new Error('Resposta da API inválida.'); }
        
        pixCodeInputElement.value = pixCodeText;
        
        if(qrCodeContainer) {
            qrCodeContainer.innerHTML = '';
            qrCodeInstance = new QRCode(qrCodeContainer, {
                text: pixCodeText,
                width: 184,
                height: 184,
                colorDark : "#000000",
                colorLight : "#ffffff",
                correctLevel : QRCode.CorrectLevel.M
            });
        }
        
      if (pixValorEl) pixValorEl.textContent = formatCurrency(totalAmount);
        
        if (!expirationDate) {
            const expirationMinutes = <?php echo $PIX_EXPIRATION_MINUTES; ?>;
            if (expirationMinutes > 0) {
                expirationDate = new Date(Date.now() + expirationMinutes * 60 * 1000);
            }
        }
        
        if (modalExpirationEl && expirationDate) {
            modalExpirationEl.textContent = new Date(expirationDate).toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            }).replace(',', '');
        }

        modal.classList.remove('hidden');
        modal.classList.add('flex');
        
        if (transactionHash) {
            startPaymentChecker(transactionHash);
        }
    }

    function copyToClipboard(text, button) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                const originalText = button.textContent; button.textContent = 'Copiado!';
                setTimeout(() => { button.textContent = originalText; }, 2000);
            }).catch(err => fallbackCopy(text, button));
        } else { fallbackCopy(text, button); }
    }
    function fallbackCopy(text, button) {
        const ta = document.createElement("textarea"); ta.value = text; ta.style.position="fixed"; ta.style.opacity="0"; document.body.appendChild(ta); ta.focus(); ta.select();
        try { if (document.execCommand('copy')) { const ot=button.textContent; button.textContent='Copiado!'; setTimeout(()=>button.textContent=ot,2000); } } catch (err) { alert('Falha ao copiar'); }
        document.body.removeChild(ta);
    }
    if (modal) {
        const closeAndClear = () => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            if (window._paymentChecker) clearInterval(window._paymentChecker);
        };
        modal.addEventListener('click', (e) => { if (e.target === modal) closeAndClear(); });
        if(closeModalBtn) closeModalBtn.addEventListener('click', closeAndClear);
        copyButton.addEventListener('click', () => { const code = pixCodeInputElement.value; if (code) copyToClipboard(code, copyButton); });
    }

    const phoneInput = document.querySelector('input[name="phone_number"]');
    if (phoneInput) {
         phoneInput.addEventListener('input', (e) => { let v = e.target.value.replace(/[^0-9]/g, ''); v = v.replace(/^([0-9]{2})([0-9])/g, '($1) $2'); v = v.replace(/([0-9]{5})([0-9]{4})$/, '$1-$2'); e.target.value = v.substring(0, 15); });
    }
    
    const documentInput = document.getElementById('document');
    if (documentInput) {
        documentInput.addEventListener('input', (e) => {
            let value = e.target.value.replace(/D/g, "");
            
            let formattedValue = value;
            if (value.length > 9) {
                formattedValue = value.replace(/(d{3})(d{3})(d{3})(d{2})/, '$1.$2.$3-$4');
            } else if (value.length > 6) {
                formattedValue = value.replace(/(d{3})(d{3})(d{1,3})/, '$1.$2.$3');
            } else if (value.length > 3) {
                formattedValue = value.replace(/(d{3})(d{1,3})/, '$1.$2');
            }
            e.target.value = formattedValue;
        });
    }

    const cepInput = document.getElementById('zip_code');
    if (cepInput) {
        cepInput.addEventListener('blur', () => {
            const cep = cepInput.value.replace(/[^0-9]/g, ''); if (cep.length !== 8) return;
            fetch('https://viacep.com.br/ws/' + cep + '/json/').then(r=>r.json()).then(d=>{if(!d.erro){document.getElementById('street_name').value=d.logradouro;document.getElementById('neighborhood').value=d.bairro;document.getElementById('city').value=d.localidade;document.getElementById('state').value=d.uf;document.getElementById('number').focus();}else{alert('CEP não encontrado.');}}).catch(e=>console.error('Erro CEP',e));
        });
    }
    
    const timerDurationInMinutes = 0;
    if (timerDurationInMinutes > 0) {
        const timerDisplay = document.getElementById('timer-display');
        const timerTextTemplate = '<?php echo htmlspecialchars($TIMER_TEXT); ?>';
        let time = timerDurationInMinutes * 60;
        const interval = setInterval(() => {
            if (time <= 0) { clearInterval(interval); timerDisplay.textContent = "OFERTA ENCERRADA"; if(payButton) {payButton.disabled=true; payButton.style.opacity='0.5';} const nextBtn=document.getElementById('next-btn'); if(nextBtn){nextBtn.disabled=true; nextBtn.style.opacity='0.5';} return; }
            time--; const m=String(Math.floor(time/60)).padStart(2,'0'); const s=String(time%60).padStart(2,'0');
            timerDisplay.textContent = timerTextTemplate.replace('{{tempo}}', m + ':' + s);
        }, 1000);
    }

    const socialProofSettings = <?php echo json_encode($SOCIAL_PROOF_SETTINGS); ?>;
    if (socialProofSettings && socialProofSettings.enabled) {
        const container = document.getElementById('social-proof-container');
        const defaultNames = ["Maria", "José", "Ana", "João", "Antônio", "Francisco", "Carlos", "Paulo", "Pedro", "Lucas", "Luiz", "Marcos", "Gabriel", "Rafael", "Daniel", "Marcelo", "Bruno", "Eduardo", "Felipe", "Sandra", "Camila", "Amanda", "Fernanda", "Patrícia", "Juliana", "Aline", "Mariana", "Vanessa", "Carolina"];
        const names = socialProofSettings.names && socialProofSettings.names.length > 0 ? socialProofSettings.names : defaultNames;
        
        const getRandomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

        const createNotification = () => {
            const name = names[Math.floor(Math.random() * names.length)];
            const value = getRandomInt(socialProofSettings.payoutMin, socialProofSettings.payoutMax);
            const formattedValue = value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
            const message = socialProofSettings.payoutMessage
                .replace('{{name}}', '<strong>' + name + '</strong>')
                .replace('{{value}}', '<strong>' + formattedValue + '</strong>');

            const notifElement = document.createElement('div');
            notifElement.className = 'social-proof-toast';
            notifElement.innerHTML = 
                '<div style="display:flex; align-items:center; gap: 12px;">' +
                    '<img src="https://picsum.photos/40/40?random=' + Date.now() + '" alt="User" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex-shrink: 0;">' +
                    '<div style="font-size: 14px; color: #e2e8f0;">' +
                        message +
                        '<div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">agora mesmo</div>' +
                    '</div>' +
                '</div>';
            
            container.appendChild(notifElement);

            setTimeout(() => {
                notifElement.classList.remove('show');
                setTimeout(() => notifElement.remove(), 500);
            }, (socialProofSettings.displayDuration || 4) * 1000);
            
            setTimeout(() => notifElement.classList.add('show'), 100);
        };

        const scheduleNextNotification = () => {
            const interval = getRandomInt(socialProofSettings.intervalMin, socialProofSettings.intervalMax) * 1000;
            setTimeout(() => {
                createNotification();
                scheduleNextNotification();
            }, interval);
        };

        setTimeout(scheduleNextNotification, (socialProofSettings.initialDelay || 5) * 1000);
    }
});
</script>
</body>
</html>
