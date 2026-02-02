
from werkzeug.security import generate_password_hash

def test_api_patient_login_success(client, mock_db):
    """Test patient login API"""
    mock_db['cursor'].fetchone.return_value = {
        'qr_id': 'TEST-QR',
        'password': generate_password_hash('pass123'),
        'username': 'pt1'
    }
    
    res = client.post('/api/login', json={'username': 'pt1', 'password': 'pass123'})
    assert res.status_code == 200
    assert res.json['qr_id'] == 'TEST-QR'
    
    calls = mock_db['cursor'].execute.call_args_list
    assert any("SELECT * FROM patients" in str(call) for call in calls)

def test_api_doctor_login_success(client, mock_db):
    """Test doctor login API"""
    mock_db['cursor'].fetchone.return_value = {
        'username': 'doc1',
        'password': generate_password_hash('docpass'), 
        'role': 'doctor',
        'id': 1
    }
    
    res = client.post('/api/doctor/login', json={'username': 'doc1', 'password': 'docpass'})
    assert res.status_code == 200
    assert 'doctor' in res.json
    
    calls = mock_db['cursor'].execute.call_args_list
    assert any("SELECT * FROM doctors" in str(call) for call in calls)

def test_api_operator_login_success(client, mock_db):
    """Test operator login API"""
    operator_data = {
        'username': 'op1',
        'password': generate_password_hash('oppass'),
        'role': 'operator',
        'hospital_id': 1,
        'id': 1
    }
    hospital_data = {'name': 'General Hospital'}
    
    # Use side_effect to return different values for consecutive calls
    mock_db['cursor'].fetchone.side_effect = [operator_data, hospital_data]
    
    res = client.post('/api/operator/login', json={'username': 'op1', 'password': 'oppass'})
    assert res.status_code == 200
    assert res.json['hospital_name'] == 'General Hospital'
    
    calls = mock_db['cursor'].execute.call_args_list
    assert any("SELECT * FROM operators" in str(call) for call in calls)
