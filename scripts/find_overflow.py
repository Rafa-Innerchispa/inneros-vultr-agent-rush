from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto("https://45.77.164.161.sslip.io/judge", wait_until="networkidle")
    wide = page.evaluate("""() => {
        const res = [];
        for (const el of document.querySelectorAll("body *")) {
            const rect = el.getBoundingClientRect();
            if (rect.right > 390.5) {
                res.push({
                    tag: el.tagName,
                    id: el.id,
                    cls: el.className,
                    right: Math.round(rect.right),
                    width: Math.round(rect.width)
                });
            }
        }
        return res;
    }""")
    print("Found", len(wide), "overflowing elements:")
    for el in wide[:15]:
        print(el)
    browser.close()

