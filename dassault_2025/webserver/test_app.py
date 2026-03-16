import pytest
from app import app, db, Mission

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

@pytest.fixture(autouse=True)
def clear_db():
    yield
    with app.app_context():
        db.drop_all()
        db.create_all()

def test_add_mission(client):
    response = client.post('/api/missions', json={"name": "Nouvelle Mission", "drone": "Zeus"})
    assert response.status_code == 201
    mission = response.json["mission"]
    assert mission["name"] == "Nouvelle Mission"
    assert mission["drone"] == "Zeus"

def test_update_mission(client):
    # Ajouter une mission pour la mettre à jour
    response = client.post('/api/missions', json={"name": "Nouvelle Mission", "drone": "Zeus"})
    mission_id = response.json["mission"]["id"]
    response = client.put(f'/api/missions/{mission_id}', json={"status": "En cours"})
    assert response.status_code == 200
    mission = response.json["mission"]
    assert mission["status"] == "En cours"

def test_delete_mission(client):
    # Ajouter une mission pour la supprimer
    response = client.post('/api/missions', json={"name": "Nouvelle Mission", "drone": "Zeus"})
    mission_id = response.json["mission"]["id"]
    print(f"Mission ID à supprimer : {mission_id}")
    response = client.delete(f'/api/missions/{mission_id}')
    assert response.status_code == 200
    response = client.get('/api/missions')
    missions = response.json
    print(f"Missions restantes : {missions}")
    assert len(missions) == 0