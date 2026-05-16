import requests

try:
    res = requests.get('http://localhost:3000/api/projects')
    print('Status:', res.status_code)
    print('Response:', res.text)
except Exception as e:
    print('Error:', e)
