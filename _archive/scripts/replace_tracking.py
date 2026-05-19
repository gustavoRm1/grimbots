from pathlib import Path
old = """                    # QI 500: GERAR TRACKING_TOKEN V4
                    from utils.tracking_service import TrackingServiceV4
                    tracking_service = TrackingServiceV4()
                    
                    # Recuperar dados de tracking do bot_user
                    fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
                    utm_source = getattr(bot_user, 'utm_source', None) if bot_user else None
                    utm_medium = getattr(bot_user, 'utm_medium', None) if bot_user else None
                    utm_campaign = getattr(bot_user, 'utm_campaign', None) if bot_user else None
                    
                    # Gerar tracking_token
                    tracking_token = tracking_service.generate_tracking_token(
                        bot_id=bot_id,
                        customer_user_id=customer_user_id,
                        payment_id=None,  # Sera atualizado apos criar payment
                        fbclid=fbclid,
                        utm_source=utm_source,
                        utm_medium=utm_medium,
                        utm_campaign=utm_campaign
                    )
                    
                    # Gerar fbp/fbc
                    fbp = tracking_service.generate_fbp(str(customer_user_id))
                    fbc = tracking_service.generate_fbc(fbclid) if fbclid else None
                    
                    # Gerar external_ids
                    external_ids = tracking_service.build_external_id_array(
                        fbclid=fbclid,
                        telegram_user_id=str(customer_user_id),
                        email=getattr(bot_user, 'email', None) if bot_user else None,
                        phone=getattr(bot_user, 'phone', None) if bot_user else None
                    )
                    
                    logger.info(f"Tracking Token V4 gerado: {tracking_token}")
"""
new = """                    # QI 500: GERAR/REUTILIZAR TRACKING_TOKEN V4
                    from utils.tracking_service import TrackingServiceV4
                    tracking_service = TrackingServiceV4()

                    fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
                    utm_source = getattr(bot_user, 'utm_source', None) if bot_user else None
                    utm_medium = getattr(bot_user, 'utm_medium', None) if bot_user else None
                    utm_campaign = getattr(bot_user, 'utm_campaign', None) if bot_user else None

                    tracking_token = getattr(bot_user, 'tracking_session_id', None) if bot_user else None
                    tracking_data = {}

                    if tracking_token:
                        try:
                            tracking_data = tracking_service.recover_tracking_data(tracking_token) or {}
                            logger.info(f"Tracking token reutilizado: {tracking_token[:12]}...")
                        except Exception as recover_error:
                            logger.warning(f"Erro ao recuperar tracking existente: {recover_error}")
                            tracking_data = {}
                    else:
                        tracking_token = tracking_service.generate_tracking_token(
                            bot_id=bot_id,
                            customer_user_id=customer_user_id,
                            payment_id=None,
                            fbclid=fbclid,
                            utm_source=utm_source,
                            utm_medium=utm_medium,
                            utm_campaign=utm_campaign
                        )
                        logger.info(f"Tracking token gerado: {tracking_token}")
                        if bot_user:
                            bot_user.tracking_session_id = tracking_token

                    fbp = tracking_data.get('fbp') or tracking_service.generate_fbp(str(customer_user_id))
                    fbc = tracking_data.get('fbc') or tracking_service.generate_fbc(fbclid)

                    external_ids = tracking_service.build_external_id_array(
                        fbclid=fbclid,
                        telegram_user_id=str(customer_user_id),
                        email=getattr(bot_user, 'email', None) if bot_user else None,
                        phone=getattr(bot_user, 'phone', None) if bot_user else None
                    )

                    base_payload = {
                        'tracking_token': tracking_token,
                        'bot_id': bot_id,
                        'customer_user_id': customer_user_id,
                        'fbclid': fbclid,
                        'fbp': fbp,
                        'fbc': fbc,
                        'utm_source': utm_source,
                        'utm_medium': utm_medium,
                        'utm_campaign': utm_campaign,
                        'external_ids': external_ids,
                    }
                    compact_base_payload = {k: v for k, v in base_payload.items() if v not in (None, '', [])}
                    ok_tracking = tracking_service.save_tracking_token(tracking_token, compact_base_payload)
                    if not ok_tracking:
                        logger.warning("Retry saving tracking_token once (generate_pix)")
                        tracking_service.save_tracking_token(tracking_token, compact_base_payload)
"""
path = Path('bot_manager.py')
data = path.read_text(encoding='utf-8')
if old not in data:
    raise SystemExit('old block not found')
path.write_text(data.replace(old, new), encoding='utf-8')
