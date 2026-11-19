"""Quick end-to-end smoke test for Waste Wise Bengaluru upgrade."""
import urllib.request
import urllib.parse
import http.cookiejar
import json

BASE = "http://127.0.0.1:5000"
PASS_MARK = "PASS"
FAIL_MARK = "FAIL"

results = []

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def check(label, condition):
    mark = PASS_MARK if condition else FAIL_MARK
    results.append((mark, label))
    print(f"  {mark}  {label}")

# ---- 1. Login page loads ----
r = opener.open(BASE + "/auth/login")
html = r.read().decode()
check("Login page loads (200)", r.status == 200)
check("Login page has form", "<form" in html)
check("Demo credentials shown", "Admin@123" in html)

# ---- 2. Admin login ----
data = urllib.parse.urlencode({"username": "admin", "password": "Admin@123"}).encode()
req = urllib.request.Request(BASE + "/auth/login", data=data, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
r2 = opener.open(req)
final_url = r2.url
html2 = r2.read().decode()
check("Admin login succeeds (redirects)", "login" not in final_url.rstrip("/").lower().split("/")[-1])
check("Admin dashboard renders (no traceback)", "Traceback" not in html2 and "Internal Server Error" not in html2)
check("Admin dashboard has Reports link", "Reports" in html2 or "reports" in html2)
check("Admin dashboard has stat cards", "Total Reports" in html2 or "stat-value" in html2)

# ---- 3. Citizen pages ----
# Logout and login as citizen
opener2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
r3 = opener2.open(BASE + "/auth/login")
data3 = urllib.parse.urlencode({"username": "citizen1", "password": "Citizen@123"}).encode()
req3 = urllib.request.Request(BASE + "/auth/login", data=data3, method="POST")
req3.add_header("Content-Type", "application/x-www-form-urlencoded")
r4 = opener2.open(req3)
html4 = r4.read().decode()
check("Citizen login succeeds", "Traceback" not in html4 and "Internal Server Error" not in html4)
check("Citizen dashboard has Report Waste button", "Report Waste" in html4)

# My Reports page
r5 = opener2.open(BASE + "/citizen/reports")
html5 = r5.read().decode()
check("My Reports page loads", r5.status == 200 and "Traceback" not in html5)

# Report form page
r6 = opener2.open(BASE + "/citizen/report-waste")
html6 = r6.read().decode()
check("Report form page loads", r6.status == 200 and "<form" in html6)

# ---- 4. Original API still works ----
body = json.dumps({"waste_type": "organic", "quantity_tons": 5, "origin": "Koramangala"}).encode()
req7 = urllib.request.Request(BASE + "/api/allocate", data=body, headers={"Content-Type": "application/json"})
r7 = urllib.request.urlopen(req7, timeout=15)
d7 = json.loads(r7.read())
check("/api/allocate still works", d7.get("success") == True)

r8 = urllib.request.urlopen(BASE + "/api/facilities", timeout=5)
d8 = json.loads(r8.read())
check("/api/facilities returns 6 facilities", len(d8.get("facilities", [])) == 6)

r9 = urllib.request.urlopen(BASE + "/api/stats", timeout=5)
d9 = json.loads(r9.read())
check("/api/stats returns total_requests", "total_requests" in d9)

# ---- 5. Register a new user ----
opener3 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener3.open(BASE + "/auth/register")
reg_data = urllib.parse.urlencode({
    "username": "testjudge", "email": "testjudge@example.com",
    "password": "Judge@12345", "confirm_password": "Judge@12345",
    "full_name": "Test Judge", "area": "Koramangala", "phone": ""
}).encode()
req_reg = urllib.request.Request(BASE + "/auth/register", data=reg_data, method="POST")
req_reg.add_header("Content-Type", "application/x-www-form-urlencoded")
r_reg = opener3.open(req_reg)
check("New user registration works", r_reg.status == 200 and "Traceback" not in r_reg.read().decode())

# ---- Summary ----
passed = sum(1 for m, _ in results if m == PASS_MARK)
total = len(results)
print(f"\n{'='*50}")
print(f"  {passed}/{total} checks passed")
if passed == total:
    print("  ALL CHECKS PASSED - project is ready!")
else:
    failed = [(m, l) for m, l in results if m == FAIL_MARK]
    print("  FAILED checks:")
    for _, l in failed:
        print(f"     - {l}")
