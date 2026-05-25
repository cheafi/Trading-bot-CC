import urllib.request
try:
    r = urllib.request.urlopen("http://localhost:8000/api/v7/today")
    print(r.read()[:200])
except Exception as e:
    print(e)
