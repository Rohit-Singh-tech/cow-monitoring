import time
import urllib.request
import json

devices = ['8', '1', '7', '9', '3', '4', '5', '6']
for dev in devices:
    t0 = time.time()
    url = f"https://a03ztkg2f5.execute-api.us-east-1.amazonaws.com/default/CowNeck_API_Function?deviceid={dev}&startdate=22-09-2026&enddate=23-09-2026"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Test/1.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            dt = time.time() - t0
            print(f"Device {dev}: {dt:.2f}s, count={data.get('Count', 0)}")
    except Exception as e:
        print(f"Device {dev}: {time.time() - t0:.2f}s, error={e}")
