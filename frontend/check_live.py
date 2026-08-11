import urllib.request
import re

try:
    with urllib.request.urlopen('https://cow-monitoring-li58.onrender.com/') as response:
        html = response.read().decode('utf-8')
        print('HTML:', html[:150])
        js_file = re.search(r'src=\"(/assets/index-.*?\.js)\"', html)
        if js_file:
            js_url = 'https://cow-monitoring-li58.onrender.com' + js_file.group(1)
            print('Found JS:', js_url)
            with urllib.request.urlopen(js_url) as js_response:
                js_code = js_response.read().decode('utf-8')
                print('Contains isAuthenticated?', 'isAuthenticated' in js_code)
                print('Contains Admin Panel?', 'Admin Panel' in js_code)
                print('Contains IIT Ropar AwaDH?', 'IIT Ropar AwaDH' in js_code)
        else:
            print('No JS found in HTML')
except Exception as e:
    print('Error:', e)
