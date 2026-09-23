import requests
import time

t0 = time.time()
r_act = requests.get('http://127.0.0.1:8000/api/config/activities')
t_act = time.time() - t0
print(f"Activities: {r_act.status_code} in {t_act:.3f}s")

t0 = time.time()
r_cows = requests.get('http://127.0.0.1:8000/api/cows')
t_cows = time.time() - t0
cows_data = r_cows.json().get("cows", [])
print(f"Cows: {r_cows.status_code} in {t_cows:.3f}s, cow_count={len(cows_data)}")

t0 = time.time()
r_tags = requests.get('http://127.0.0.1:8000/api/tags')
t_tags = time.time() - t0
tags_data = r_tags.json().get("tags", [])
print(f"Tags: {r_tags.status_code} in {t_tags:.3f}s, tags_count={len(tags_data)}")

for c in cows_data:
    if c['id'] in [8, 'aws-8', 17]:
        print(f"  Cow ID={c['id']}, Name='{c['name']}', Breed='{c.get('breed')}', Tag='{c.get('tagNumber')}'")
