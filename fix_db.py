import sys
import os

# Use port 5434 mapped in docker-compose for external connections
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5434/closely_db"

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.app.database import SessionLocal
from backend.app.models import Organization

db = SessionLocal()
orgs = db.query(Organization).all()
for org in orgs:
    print(f'Org: {org.name}')
    policies = org.policies or {}
    print(f'  Policies before: {policies}')
    
    modified = False
    if 'whatsapp_access_token' in policies:
        del policies['whatsapp_access_token']
        modified = True
    if 'whatsapp_phone_number_id' in policies:
        del policies['whatsapp_phone_number_id']
        modified = True
        
    if modified:
        org.policies = policies
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(org, "policies")
        print(f'  Policies after: {org.policies}')

db.commit()
print('Cleared dummy tokens successfully!')
