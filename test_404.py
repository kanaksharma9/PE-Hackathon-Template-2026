from app import create_app
from app.database import db
from app.models import Event, Url, User

app = create_app({'TESTING': True, 'DATABASE': ':memory:'})
with app.app_context():
    db.create_tables([User, Url, Event], safe=True)

client = app.test_client()
r = client.get('/no-such-route-xyz')
print('Status:', r.status_code)
print('JSON:', r.get_json())
print('Content-Type:', r.headers.get('Content-Type'))
print('Data:', r.data)
