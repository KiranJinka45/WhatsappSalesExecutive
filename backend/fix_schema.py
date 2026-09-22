from app.database import engine
from sqlalchemy import text
from app import security

with engine.begin() as conn:
    conn.execute(text("""
        ALTER TABLE organizations 
        ADD COLUMN IF NOT EXISTS whatsapp_connected_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS whatsapp_token_expires_at TIMESTAMP WITH TIME ZONE;
    """))
    print("Added missing columns to organizations table.")

    raw_token = "EAAOp93fauOMBScGULZBDyZCRqkNNnIh4s10ZCjWa89QPLBnfM8Iw2TL2NYSD0a8aZBrhqifHvpe7fGtbYAR3wZAqhAx766ZCpOgZB4jTWyqSLAsjvYa5DDjvOgdZCZBnwPk8hwJZBUYEkWDGG73ZCmSMrwLsiPu4Ft24OY6dTNCdJwEW6ZBSDr3HJnntMZCI2dKKObQZDZD"
    enc_token = security.encrypt_token(raw_token)
    
    # Update organization 76043d11-b671-420b-b1cc-3991c5547bbc (Sri Siddi Vinayaka)
    conn.execute(text("""
        UPDATE organizations 
        SET name = 'Sri Siddi Vinayaka',
            whatsapp_number = '+919014348483',
            whatsapp_phone_number_id = '1332071853322957',
            whatsapp_business_account_id = '1077336617997411',
            whatsapp_access_token = :token,
            is_whatsapp_connected = 1,
            whatsapp_onboarding_state = 'LIVE_CONNECTED',
            policies = jsonb_build_object(
                'operating_mode', 'LIVE',
                'emergency_kill_switch', false,
                'whatsapp_access_token', :token,
                'whatsapp_phone_number_id', '1332071853322957',
                'whatsapp_business_account_id', '1077336617997411'
            )
        WHERE id = '76043d11-b671-420b-b1cc-3991c5547bbc';
    """), {"token": enc_token})
    print("Successfully updated Organization Sri Siddi Vinayaka with live Meta credentials and LIVE operating mode!")
