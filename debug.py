import requests
from bs4 import BeautifulSoup

s = requests.Session()
s.post('http://127.0.0.1:5001/login', data={'username':'tc_senior','password':'password123'}, allow_redirects=False)
res = s.post('http://127.0.0.1:5001/processing', data={'amount': '25000', 'phone': '1234567890', 'receiver': 'suspect@upi', 'device': 'mobile', 'location': 'mumbai', 'merchant': 'retail'})

soup = BeautifulSoup(res.text, 'html.parser')
# Print all text content safely
with open('debug_out.txt', 'w', encoding='utf-8') as f:
    f.write(soup.get_text())
