import requests
from crypto import decrypt_key

url = "https://mhbexakitlucgflziosg.supabase.co/rest/v1/instances"
key = "sb_secret_c02hiBBrF6UYZL20zxJ65g__smDosMO"
instance_id = "i-01a3d00e6c1ac9162"

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

params = {
    "instance_id": f"eq.{instance_id}",
    "select": "private_key"
}

try:
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data and data[0].get("private_key"):
            encrypted = data[0]["private_key"]
            decrypted = decrypt_key(encrypted)
            if decrypted:
                print("Key Decrypted Successfully.")
                with open("temp_key.pem", "w") as f:
                    f.write(decrypted)
                import os
                os.chmod("temp_key.pem", 0o600)
            else:
                print("Decryption failed.")
        else:
            print("No private key found.")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
