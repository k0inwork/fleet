import httpx
import asyncio

API_KEY = "AIzaSyBJZRcly1AvfUpQysVH9MHWkKDya90zgCs"

async def test_auth():
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={"returnSecureToken": True})
        print(f"Auth Status: {resp.status_code}")
        print(f"Auth Response: {resp.text}")
        if resp.status_code == 200:
            id_token = resp.json().get("idToken")
            db_url = f"https://channel1-2792f-default-rtdb.firebaseio.com/test_jules.json?auth={id_token}"
            db_resp = await client.put(db_url, json={"test": "authed_hello"})
            print(f"DB Status: {db_resp.status_code}")
            print(f"DB Response: {db_resp.text}")

asyncio.run(test_auth())
