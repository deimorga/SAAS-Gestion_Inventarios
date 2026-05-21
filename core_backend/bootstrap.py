import httpx

url = "http://localhost:8000/admin/auth/register"
headers = {"X-Bootstrap-Secret": "change-me-bootstrap-secret"}
data = {"email": "cristian@superadmin.com", "password": "cris1234", "full_name": "Cristian Super Admin"}

try:
    r = httpx.post(url, headers=headers, json=data)
    print(r.status_code, r.text)
except Exception as e:
    print(e)
