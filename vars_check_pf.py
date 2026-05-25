import re
with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

m = re.search(r'function cc\(\)\s*\{\s*return\s*\{([\s\S]*?)\s*\}\s*\}', text)
if m:
    cc_body = m.group(1)
    
    # Are methods defined?
    for mth in ["pfRisk", "dosVerdict", "fetchCcStatus", "fetchScanners", "opsDetail", "scannerHub", "showGuideModal", "opsDetail"]:
        if mth in cc_body:
            print(f"{mth} exists in cc()")
        else:
            print(f"{mth} missing from cc()")

