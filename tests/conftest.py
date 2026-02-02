
import pytest
from app import create_app
from unittest.mock import MagicMock

@pytest.fixture
def client():
    """Flask test client"""
    app = create_app()
    app.config['TESTING'] = True
    app.secret_key = 'test_secret'
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_db(mocker):
    """Mock database connection and cursor"""
    # Create mocks
    mock_conn = MagicMock()
    mock_cursor = MagicMock(name='cursor')
    
    # Setup cursor context manager (with conn.cursor() as cursor)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.__enter__.return_value = mock_cursor
    
    # Mock psycopg2.connect to return our mock_conn
    mocker.patch('psycopg2.connect', return_value=mock_conn)
    
    # Configure fetchone/fetchall to return something by default (safeguard)
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    
    return {
        'conn': mock_conn,
        'cursor': mock_cursor
    }
