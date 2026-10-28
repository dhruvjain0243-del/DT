import csv
from datetime import UTC, datetime
from io import BytesIO, StringIO
from zipfile import ZipFile
from urllib.parse import parse_qs, urlsplit

from backend.app.models import ParkingSession, UserRole
from .helpers import create_user, headers_for


def setup_places(client, db_session):
    admin = create_user(db_session, email="dhruvjain1223@gmail.com", role=UserRole.ADMIN)
    headers = headers_for(admin)
    places = []
    for name, lat in [("North parking", 12.639), ("South parking", 12.641)]:
        response = client.post("/api/college/admin/locations", headers=headers, json={"name": name, "address": "Campus road, Bengaluru", "latitude": lat, "longitude": 77.444, "capacity": 2, "timezone": "Asia/Kolkata"})
        assert response.status_code == 201, response.text
        places.append(response.json())
    return headers, places


def test_locations_qr_capacity_and_scanner_isolation(client, db_session):
    headers, places = setup_places(client, db_session)
    assert len(client.get('/api/college/locations', headers=headers).json()) == 2
    urls = []
    for place in places:
        query = {"facility_id": place['id']}
        links = client.get('/api/college/qr', params=query, headers=headers).json()
        assert links['entry_path'] != links['exit_path']
        parsed = urlsplit(links['entry_path'])
        assert parsed.scheme == 'http'
        params = parse_qs(parsed.query)
        assert params['facility_id'] == [str(place['id'])]
        assert float(params['latitude'][0]) == place['latitude']
        assert params['flow'] == ['entry']
        urls.append(links['entry_path'])
        image = client.get('/api/college/qr/entry.png', params=query, headers=headers)
        assert image.status_code == 200
        assert image.content.startswith(b'\x89PNG')
    assert urls[0] != urls[1]
    gate = client.post(f"/api/operations/facilities/{places[0]['id']}/gates", headers=headers, json={"name":"North entrance", "gate_type":"ENTRY"}).json()
    assert client.post(f"/api/operations/gates/{gate['id']}/scanners", headers=headers, json={"name":"North camera", "device_identifier":"north-camera"}).status_code == 201
    assert client.get(f"/api/operations/facilities/{places[1]['id']}/gates", headers=headers).json() == []
    data = {"name":"North parking", "address":"Campus road, Bengaluru", "latitude":12.639,"longitude":77.444,"capacity":1,"timezone":"Asia/Kolkata"}
    assert client.put('/api/college/admin/config', params={"facility_id":places[0]['id']}, headers=headers,json=data).json()['capacity'] == 1
    data['capacity'] = 2
    assert client.put('/api/college/admin/config', params={"facility_id":places[0]['id']}, headers=headers,json=data).json()['capacity'] == 2
    assert client.get('/api/college/facility',params={"facility_id":places[1]['id']},headers=headers).json()['capacity'] == 2


def test_location_actions_and_date_exports(client, db_session):
    headers, places = setup_places(client, db_session)
    student = create_user(db_session, email='parking.user@example.com')
    user_headers = headers_for(student)
    assert client.put('/api/college/profile', headers=user_headers, json={"full_name":"Parking User", "registration_number":"MH04AC9999"}).status_code == 200
    first, second = places
    entry = client.post('/api/college/entry', params={"facility_id":first['id']},headers=user_headers)
    assert entry.status_code == 201, entry.text
    session_id = entry.json()['session']['id']
    assert entry.json()['session']['facility_id'] == first['id']
    occupied_slots = entry.json()['facility']['slots']
    assert [slot['vehicle_number'] for slot in occupied_slots if slot['status'] == 'OCCUPIED'] == ['MH04AC9999']
    assert all(slot['vehicle_number'] is None for slot in occupied_slots if slot['status'] == 'AVAILABLE')
    # 23:45 UTC on Oct 27 is 05:15 on Oct 28 in the location's timezone.
    session = db_session.get(ParkingSession, session_id)
    session.entry_time = datetime(2026,10,27,23,45,tzinfo=UTC)
    db_session.commit()
    query={"facility_id":first['id'], "selected_date":"2026-10-28"}
    result=client.get('/api/reports/location-records', params=query, headers=headers)
    assert result.status_code == 200, result.text
    row=result.json()['rows'][0]
    assert row == ['North parking','Parking User','2026-10-28','05:15:00','',entry.json()['session']['space'],'MH04AC9999','Currently occupied']
    assert client.get('/api/reports/location-records',params={**query,"facility_id":second['id']},headers=headers).json()['rows'] == []
    assert client.get('/api/reports/location-records',params={**query,"selected_date":"2026-10-26"},headers=headers).json()['rows'] == []
    exported=client.get('/api/reports/export-csv',params=query,headers=headers)
    csv_rows=list(csv.reader(StringIO(exported.content.decode('utf-8-sig'))))
    assert csv_rows == [result.json()['columns'],row]
    assert str(first['id'])+'-2026-10-28' in exported.headers['content-disposition']
    xlsx=client.get('/api/reports/export-xlsx',params=query,headers=headers)
    with ZipFile(BytesIO(xlsx.content)) as archive:
        xml=archive.read('xl/worksheets/sheet1.xml').decode()
        assert 'North parking' in xml and 'South parking' not in xml
        assert 'Time of exit' in xml and '05:15:00' in xml
    assert client.post('/api/college/exit',params={"facility_id":second['id']},headers=user_headers).status_code == 404
    assert client.get('/api/college/facility',params={"facility_id":first['id']},headers=user_headers).json()['occupied'] == 1
    exit_result = client.post('/api/college/exit',params={"facility_id":first['id']},headers=user_headers)
    assert exit_result.status_code == 200
    assert all(slot['vehicle_number'] is None for slot in exit_result.json()['facility']['slots'])
    assert client.get('/api/reports/location-records',params=query,headers=headers).json()['rows'][0][-1] == 'Currently available'
    assert client.get('/api/reports/export-csv',headers=headers).status_code == 400
    assert client.get('/api/reports/export-csv',params=query,headers=user_headers).status_code == 403
    assert client.get('/api/college/facility',params={"facility_id":9999},headers=headers).status_code == 404
    assert client.get('/api/college/my-sessions',params={"facility_id":second['id']},headers=user_headers).json() == []
