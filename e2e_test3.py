import requests
import time
import json

BASE_URL = 'http://localhost:8000/api'

print('1. Creating Project...')
res = requests.post(f'{BASE_URL}/projects', json={'name': 'E2E Test', 'description': 'desc'})
if res.status_code != 201:
    print('Failed to create project:', res.status_code, res.text)
    exit(1)
project_id = res.json()['id']
print('Project Created:', project_id)

print('\n2. Uploading PDF...')
pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources <<>> /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 21 >>\nstream\nBT /F1 12 Tf (Hello) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000222 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n293\n%%EOF\n'

with open('dummy.pdf', 'wb') as f:
    f.write(pdf_content)

with open('dummy.pdf', 'rb') as f:
    res = requests.post(f'{BASE_URL}/projects/{project_id}/files', files={'file': ('dummy.pdf', f, 'application/pdf')})

if res.status_code != 200:
    print('Upload failed:', res.status_code, res.text)
    exit(1)
file_id = res.json()['file_id']
print('File Uploaded:', file_id)

print('\n3. Waiting for processing to finish (polling status)...')
ready = False
for _ in range(60):
    res = requests.get(f'{BASE_URL}/projects/{project_id}/status')
    if res.status_code == 200:
        status = res.json()['overall_status']
        print(f'Status: {status}')
        if status == 'ready':
            ready = True
            break
        elif status == 'failed':
            print('Processing failed!')
            break
    time.sleep(2)

if not ready:
    print('Document not ready or failed.')
    exit(1)

print('\n4. Testing Chat...')
res = requests.post(f'{BASE_URL}/chat', json={
    'project_id': project_id,
    'message': 'What does the document say?'
}, stream=True)

if res.status_code != 200:
    print('Chat failed:', res.status_code, res.text)
    exit(1)

print('Chat Response:', end=' ')
for line in res.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data_str = line[6:]
            if data_str == '[DONE]':
                break
            try:
                data = json.loads(data_str)
                if 'content' in data:
                    print(data['content'], end='', flush=True)
            except:
                pass
print('\n\nE2E Test Passed Successfully!')
