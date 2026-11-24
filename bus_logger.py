import requests
import csv
import time
import os
from datetime import datetime, timezone, timedelta

CLIENT_ID = os.environ["TDX_CLIENT_ID"]
CLIENT_SECRET = os.environ["TDX_CLIENT_SECRET"]

ROUTES = [
    ("YunlinCounty", "201"),
    ("Taichung", "220")
]
CSV_FILE = "bus_log.csv"
RUN_MINUTES = 55       # 每次啟動跑 55 分鐘
INTERVAL_SECONDS = 60  # 每 60 秒抓一次
TW_TZ = timezone(timedelta(hours=8))

def get_access_token():
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    res = requests.post(auth_url, data=payload, timeout=10)
    res.raise_for_status()
    return res.json()["access_token"]

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["記錄時間", "縣市", "路線", "方向", "車牌", "站名", "狀態", "GPS時間"])

def main():
    init_csv()
    seen_records = set()
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    end_time = time.time() + (RUN_MINUTES * 60)

    while time.time() < end_time:
        try:
            with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                for city, route in ROUTES:
                    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/RealTimeNearStop/City/{city}/{route}"
                    res = requests.get(url, headers=headers, params={"$format": "JSON"}, timeout=10)
                    res.raise_for_status()
                    for bus in res.json():
                        plate = bus.get("PlateNumb", "")
                        direction = "去程" if bus.get("Direction") == 0 else "返程"
                        stop_name = bus.get("StopName", {}).get("Zh_tw", "")
                        event = "進站" if bus.get("A2EventType") == 1 else "離站"
                        gps_time = bus.get("GPSTime", "")

                        record_key = (city, route, plate, stop_name, event, gps_time)
                        if record_key not in seen_records:
                            seen_records.add(record_key)
                            now_str = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
                            writer.writerow([now_str, city, route, direction, plate, stop_name, event, gps_time])
        except Exception as e:
            print(f"發生錯誤：{e}")

        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
