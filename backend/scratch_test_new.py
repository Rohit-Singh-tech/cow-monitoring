import requests
import json

print("=== 1. FETCH COWS ===")
r_cows = requests.get("http://127.0.0.1:8000/api/cows")
cows = r_cows.json().get("cows", [])
for c in cows:
    print(f"ID={c['id']}, DevID={c['device_id']}, Source={c['source']}, Name='{c['name']}'")

print("\n=== 2. FETCH COW 17 CURRENT ===")
r_17 = requests.get("http://127.0.0.1:8000/api/cow/17/current")
d_17 = r_17.json()
print(f"Cow 17 Current -> DeviceID={d_17.get('device_id')}, Source={d_17.get('source')}, Name='{d_17.get('cowName')}', Tag='{d_17.get('tagNumber')}'")

print("\n=== 3. FETCH COW 17 7-DAY ===")
r_17_7 = requests.get("http://127.0.0.1:8000/api/cow/17/7day")
d_17_7 = r_17_7.json()
print(f"Cow 17 7-Day -> Source={d_17_7.get('source')}, WeeklyAvg={d_17_7.get('weeklyAverageHours')}")

print("\n=== 4. FETCH AWS COW 8 CURRENT ===")
r_8 = requests.get("http://127.0.0.1:8000/api/cow/aws-8/current")
d_8 = r_8.json()
print(f"AWS 8 Current -> DeviceID={d_8.get('device_id')}, Source={d_8.get('source')}, Name='{d_8.get('cowName')}', Tag='{d_8.get('tagNumber')}'")

print("\n=== 5. FETCH AWS COW 8 7-DAY ===")
r_8_7 = requests.get("http://127.0.0.1:8000/api/cow/aws-8/7day")
d_8_7 = r_8_7.json()
print(f"AWS 8 7-Day -> Source={d_8_7.get('source')}, WeeklyAvg={d_8_7.get('weeklyAverageHours')}")
