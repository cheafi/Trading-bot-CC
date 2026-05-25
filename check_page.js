const puppeteer = require('puppeteer-core');
(async () => {
    // Launch Chrome using the system installed one or install a quick chromium if possible.
    // Mac chrome path:
    const browser = await puppeteer.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--no-sandbox']});
    const page = await browser.newPage();
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.message));
    await page.goto('http://localhost:8000', {waitUntil: 'networkidle0'}).catch(e => console.log(e));
    const content = await page.content();
    console.log("HTML length:", content.length);
    console.log("Empty body?", content.includes('<body></body>'));
    await browser.close();
})();
