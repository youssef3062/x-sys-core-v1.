
def test_api_patient_get(client, mock_db):
    """Test fetching patient data"""
    mock_db['cursor'].fetchone.return_value = {
        'qr_id': 'TEST-QR', 'name': 'Test Pat'
    }
    
    res = client.get('/api/patient/TEST-QR')
    assert res.status_code == 200
    assert res.json['name'] == 'Test Pat'
    
    calls = mock_db['cursor'].execute.call_args_list
    assert any("SELECT" in str(call) for call in calls)

def test_api_doctor_add_visit(client, mock_db):
    """Test doctor adding visit API"""
    # Mock doctor check (often API checks doctor existence or just assumes valid if no session enforcement on API which is stateless mostly?)
    # API usually expects created_by or relies on payload.
    
    mock_db['conn'].commit.return_value = None
    
    res = client.post('/api/visit', json={
        'qr_id': 'TEST-QR',
        'visit_date': '2025-01-01',
        'diagnosis': 'Flu',
        'created_by': 'Dr. Test'
    })
    
    assert res.status_code == 200
    
    calls = mock_db['cursor'].execute.call_args_list
    assert any("INSERT INTO visits" in str(call) for call in calls)

def test_api_search_patients(client, mock_db):
    """Test operator search API"""
    mock_db['cursor'].fetchall.return_value = [
        {'qr_id': 'TEST-QR', 'name': 'Found'}
    ]
    
    res = client.get('/api/search/patients?q=Test')
    assert res.status_code == 200
    assert len(res.json) == 1
    
    calls = mock_db['cursor'].execute.call_args_list
    assert any("SELECT" in str(call) and "patients" in str(call) for call in calls)
