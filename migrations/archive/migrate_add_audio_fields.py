#!/usr/bin/env python3
"""
Migração: Adicionar campos de áudio complementar
- welcome_audio_enabled e welcome_audio_url em BotConfig
- audio_enabled e audio_url em RemarketingCampaign
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate():
    """Adiciona campos de áudio"""
    print("=" * 60)
    print("📊 MIGRAÇÃO: Adicionar Campos de Áudio")
    print("=" * 60)
    print()
    
    with app.app_context():
        try:
            # 1. Adicionar campos em BotConfig
            print("📝 Adicionando campos de áudio em BotConfig...")
            
            # welcome_audio_enabled
            try:
                db.session.execute(text("""
                    ALTER TABLE bot_configs 
                    ADD COLUMN welcome_audio_enabled BOOLEAN DEFAULT 0
                """))
                print("   ✅ welcome_audio_enabled adicionado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("   ⚠️  welcome_audio_enabled já existe")
                else:
                    raise
            
            # welcome_audio_url
            try:
                db.session.execute(text("""
                    ALTER TABLE bot_configs 
                    ADD COLUMN welcome_audio_url VARCHAR(500)
                """))
                print("   ✅ welcome_audio_url adicionado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("   ⚠️  welcome_audio_url já existe")
                else:
                    raise
            
            # 2. Adicionar campos em RemarketingCampaign
            print("\n📝 Adicionando campos de áudio em RemarketingCampaign...")
            
            # audio_enabled
            try:
                db.session.execute(text("""
                    ALTER TABLE remarketing_campaigns 
                    ADD COLUMN audio_enabled BOOLEAN DEFAULT 0
                """))
                print("   ✅ audio_enabled adicionado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("   ⚠️  audio_enabled já existe")
                else:
                    raise
            
            # audio_url
            try:
                db.session.execute(text("""
                    ALTER TABLE remarketing_campaigns 
                    ADD COLUMN audio_url VARCHAR(500)
                """))
                print("   ✅ audio_url adicionado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print("   ⚠️  audio_url já existe")
                else:
                    raise
            
            # Commit
            db.session.commit()
            
            print()
            print("=" * 60)
            print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 60)
            print()
            print("📊 Resumo:")
            print("   • BotConfig: welcome_audio_enabled, welcome_audio_url")
            print("   • RemarketingCampaign: audio_enabled, audio_url")
            print()
            print("🎯 Agora você pode adicionar áudio complementar em:")
            print("   ✅ Mensagens de boas-vindas")
            print("   ✅ Campanhas de remarketing")
            print()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print()
            print("=" * 60)
            print("❌ ERRO NA MIGRAÇÃO!")
            print("=" * 60)
            print(f"Erro: {e}")
            print()
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)

