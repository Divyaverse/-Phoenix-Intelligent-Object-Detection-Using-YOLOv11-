import urllib.request
import json
import websockets
import asyncio

async def main():
    base_url = "http://localhost:8000/api/v1"
    
    # 1. Login
    login_req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=json.dumps({"email": "admin@phoenix.local", "password": "AdminPass123!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(login_req) as resp:
            login_data = json.loads(resp.read().decode("utf-8"))
            token = login_data["access_token"]
            print("1. Login Success. Token:", token[:25], "...")
    except Exception as e:
        print("1. Login Failed:", e)
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Cameras
    cam_req = urllib.request.Request(f"{base_url}/cameras?building_id=bldg-hq-01", headers=headers)
    try:
        with urllib.request.urlopen(cam_req) as resp:
            cams = json.loads(resp.read().decode("utf-8"))
            print(f"2. Cameras: {len(cams)} found")
            for c in cams:
                print(f"   Camera: {c['camera_id']} ({c['name']}) -> {c['source_uri']}")
    except Exception as e:
        print("2. Cameras Failed:", e)

    # 3. Floorplan
    fp_req = urllib.request.Request(f"{base_url}/spatial/floorplans/bldg-hq-01/fl-01", headers=headers)
    try:
        with urllib.request.urlopen(fp_req) as resp:
            fp = json.loads(resp.read().decode("utf-8"))
            print(f"3. Floorplan: {fp.get('name')} | Nodes: {len(fp.get('nodes', []))} | Regions: {len(fp.get('regions', []))}")
    except Exception as e:
        print("3. Floorplan Failed:", e)

    # 4. Building
    bldg_req = urllib.request.Request(f"{base_url}/buildings/bldg-hq-01", headers=headers)
    try:
        with urllib.request.urlopen(bldg_req) as resp:
            bldg = json.loads(resp.read().decode("utf-8"))
            print(f"4. Building: {bldg.get('name')}")
    except Exception as e:
        print("4. Building Failed:", e)

    # 5. Incident
    inc_req = urllib.request.Request(f"{base_url}/incidents/current?building_id=bldg-hq-01", headers=headers)
    try:
        with urllib.request.urlopen(inc_req) as resp:
            inc = json.loads(resp.read().decode("utf-8"))
            print(f"5. Incident: {inc.get('incident_id') if inc else 'None'}")
    except Exception as e:
        print("5. Incident Failed:", e)

    # 6. WebSocket
    ws_url = f"ws://localhost:8000/ws/v1/buildings/bldg-hq-01?token={token}"
    try:
        async with websockets.connect(ws_url) as ws:
            print("6. WebSocket Connected successfully!")
            await ws.send("ping")
            pong = await asyncio.wait_for(ws.recv(), timeout=2.0)
            print("   WebSocket Pong response:", pong)
    except Exception as e:
        print("6. WebSocket Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
