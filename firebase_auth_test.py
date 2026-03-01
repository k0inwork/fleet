import httpx
import asyncio

API_KEY = "AIzaSyBJZRcly1AvfUpQysVH9MHWkKDya90zgCs"

async def test_auth():
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={"returnSecureToken": True})
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")

asyncio.run(test_auth())
