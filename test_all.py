import requests

print('=== Testing Backend Direct (127.0.0.1:8000) ===')
try:
    res = requests.get('http://127.0.0.1:8000/api/projects')
    print(f'Backend Direct: {res.status_code}')
    print(f'Body: {res.text[:200]}')
except Exception as e:
    print(f'Backend Direct FAILED: {e}')

print()
print('=== Testing Frontend Proxy (127.0.0.1:3000) ===')
try:
    res = requests.get('http://127.0.0.1:3000/api/projects')
    print(f'Frontend Proxy: {res.status_code}')
    print(f'Body: {res.text[:200]}')
except Exception as e:
    print(f'Frontend Proxy FAILED: {e}')

print()
print('=== Testing localhost:3000 (IPv6 test) ===')
try:
    res = requests.get('http://localhost:3000/api/projects')
    print(f'localhost:3000 Proxy: {res.status_code}')
    print(f'Body: {res.text[:200]}')
except Exception as e:
    print(f'localhost:3000 Proxy FAILED: {e}')
