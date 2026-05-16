import requests, time

print('=== 1. Backend direct test ===')
r = requests.get('http://127.0.0.1:8000/api/projects')
print(f'Backend: {r.status_code}')

print()
print('=== 2. Frontend proxy test ===')
# Wait for Next.js to compile
time.sleep(5)
r = requests.get('http://127.0.0.1:3000/api/projects')
print(f'Frontend proxy: {r.status_code}')
print(f'Body: {r.text[:200]}')

print()
print('=== 3. Create project ===')
r = requests.post('http://127.0.0.1:8000/api/projects', json={'name': 'Upload Test', 'system_prompt': ''})
print(f'Create: {r.status_code}')
proj = r.json()
print(f'Project ID: {proj["id"]}')

print()
print('=== 4. Upload PDF ===')
with open('test.pdf', 'rb') as f:
    r = requests.post(f'http://127.0.0.1:8000/api/projects/{proj["id"]}/files', files={'file': ('test.pdf', f, 'application/pdf')})
print(f'Upload: {r.status_code}')
print(f'Response: {r.json()}')

print()
print('=== ALL TESTS PASSED ===' if r.status_code == 200 else '=== SOME TESTS FAILED ===')
