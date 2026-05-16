import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment before importing the app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["PDF_UPLOAD_DIR"] = "./data/test_uploads"
os.environ["BM25_INDEX_DIR"] = "./data/test_bm25"
os.makedirs(os.environ["PDF_UPLOAD_DIR"], exist_ok=True)
os.makedirs(os.environ["BM25_INDEX_DIR"], exist_ok=True)

from backend.main import app
from backend.database import Base, get_db
from backend.models import File, Project

# Use SQLite for testing
engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_upload_unsupported_file():
    """Test that the API rejects unsupported file extensions."""
    project_id = str(uuid.uuid4())
    files = {"file": ("test.xyz", b"fake content", "text/plain")}
    response = client.post(f"/api/projects/{project_id}/files", files=files)
    
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_upload_valid_file_creates_pending_status(mocker):
    """Test that uploading a valid file immediately returns a pending status."""
    # Mock celery task to prevent it from actually running
    mocker.patch("backend.main.ingest_document.delay")
    
    project_id = str(uuid.uuid4())
    files = {"file": ("test.pdf", b"fake pdf content", "application/pdf")}
    
    response = client.post(f"/api/projects/{project_id}/files", files=files)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "pending"
    assert data["project_id"] == project_id
    assert "file_id" in data
    
    # Check if it was saved in DB
    db = TestingSessionLocal()
    db_file = db.query(File).filter(File.id == data["file_id"]).first()
    assert db_file is not None
    assert db_file.docling_status == "pending"
    db.close()

def test_get_status_endpoint():
    """Test that the status endpoint returns the mapped generic 'status'."""
    db = TestingSessionLocal()
    project_id = uuid.uuid4()
    
    # Create project and file
    db.add(Project(id=project_id, name="Test Project"))
    db.add(File(
        id=uuid.uuid4(),
        project_id=project_id,
        original_name="test.pdf",
        file_path="/tmp/test.pdf",
        docling_status="ready",
        page_count=5,
        chunk_count=20
    ))
    db.commit()
    db.close()
    
    response = client.get(f"/api/projects/{project_id}/status")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "ready"  # Testing the schema mapping
    assert data[0]["page_count"] == 5
    assert data[0]["chunk_count"] == 20
