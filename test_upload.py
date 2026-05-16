import requests
import io
import json

# Get a project
r = requests.get('http://127.0.0.1:8000/api/projects')
projects = r.json()
if not projects:
    r = requests.post('http://127.0.0.1:8000/api/projects', json={'name': 'Test Project', 'description': ''})
    project_id = r.json()['id']
else:
    project_id = projects[0]['id']

print('Using project:', project_id)

dummy_content = b'%PDF-1.4\n' + b'A' * 15 * 1024 * 1024  # 15 MB dummy PDF

files = {'file': ('dummy.pdf', io.BytesIO(dummy_content), 'application/pdf')}
url = f'http://127.0.0.1:8000/api/projects/{project_id}/files'

response = requests.post(url, files=files)
print('Response:', response.status_code)
print('Body:', response.text)

import glob
from pathlib import Path
uploads = sorted(glob.glob('backend/uploads/*.pdf'), key=lambda x: Path(x).stat().st_mtime, reverse=True)
latest = uploads[0]
print(f'Latest file size: {Path(latest).stat().st_size} bytes')
