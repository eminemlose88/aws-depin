import requests
import json

url = "https://mhbexakitlucgflziosg.supabase.co/rest/v1/instances"
key = "sb_secret_c02hiBBrF6UYZL20zxJ65g__smDosMO"
user_id = "51f8a054-a24d-4a41-bff8-faa2be1ac34f"

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

params = {
    "user_id": f"eq.{user_id}",
    "select": "instance_id,ip_address,status,proj_nexus,project_name"
}

print(f"Querying for user: {user_id}")
try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data)} instances.")
        for i in data:
            print(f"ID: {i.get('instance_id')} | IP: {i.get('ip_address')} | Nexus: {i.get('proj_nexus')} | ProjName: {i.get('project_name')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
