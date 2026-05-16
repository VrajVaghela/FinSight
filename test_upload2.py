import requests

# Get existing project
projects = requests.get('http://localhost:8000/api/projects', headers={'Authorization': 'Bearer test_token_if_auth_is_disabled'})
if projects.status_code == 200 and projects.json():
    project_id = projects.json()[0]['id']
else:
    # Just try with a dummy id, since the 500 error probably happens before project validation if there's a DB issue
    project_id = '00000000-0000-0000-0000-000000000000'

print('Using project_id:', project_id)

url = f'http://localhost:8000/api/projects/{project_id}/files'
with open('test.pdf', 'wb') as f:
    f.write(b'%PDF-1.4\n%EOF\n')

with open('test.pdf', 'rb') as f:
    res = requests.post(url, files={'file': f})

print('Upload Status:', res.status_code)
print('Upload Response:', res.text)
