from app.database import engine, SessionLocal
from app import models, security
from sqlalchemy import text

db = SessionLocal()
org = db.query(models.Organization).filter(models.Organization.id == '76043d11-b671-420b-b1cc-3991c5547bbc').first()

if org:
    raw_token = "EAAOp93fauOMBScGULZBDyZCRqkNNnIh4s10ZCjWa89QPLBnfM8Iw2TL2NYSD0a8aZBrhqifHvpe7fGtbYAR3wZAqhAx766ZCpOgZB4jTWyqSLAsjvYa5DDjvOgdZCZBnwPk8hwJZBUYEkWDGG73ZCmSMrwLsiPu4Ft24OY6dTNCdJwEW6ZBSDr3HJnntMZCI2dKKObQZDZD"
    enc_token = security.encrypt_token(raw_token)
    
    org.name = "Sri Siddi Vinayaka"
    org.whatsapp_number = "+919014348483"
    org.whatsapp_phone_number_id = "1332071853322957"
    org.whatsapp_business_account_id = "1077336617997411"
    org.whatsapp_access_token = enc_token
    org.is_whatsapp_connected = 1
    org.whatsapp_onboarding_state = "LIVE_CONNECTED"
    
    policies = dict(org.policies or {})
    policies["operating_mode"] = "LIVE"
    policies["emergency_kill_switch"] = False
    policies["whatsapp_access_token"] = enc_token
    policies["whatsapp_phone_number_id"] = "1332071853322957"
    policies["whatsapp_business_account_id"] = "1077336617997411"
    org.policies = policies
    
    db.commit()
    db.refresh(org)
    print("Updated Organization:", org.name, org.whatsapp_number, "is_connected:", org.is_whatsapp_connected, "policies:", org.policies)
else:
    print("Org not found")

db.close()
