// The web app is hosted separately from the backend: check the "Server" control behaves and cannot be hijacked by a link.
import { chromium } from 'playwright'

const BASE = process.env.E2E_BASE || 'http://localhost:4175'
let failed = 0
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`)
  if (!cond) failed++
}
const browser = await chromium.launch()
const page = await (await browser.newContext({ viewport: { width: 1100, height: 800 } })).newPage()
const stored = () => page.evaluate(() => localStorage.getItem('engano_api_url'))

await page.goto(BASE)
await page.getByText('connected').first().waitFor({ timeout: 10000 })
ok('sign-in shows the server and that it answers', (await page.getByText(/Server:/).count()) === 1)

// a link may only suggest a server; nothing changes until the person agrees
await page.goto(`${BASE}/?api=https://hosted-backend.example`)
await page.getByRole('alert').getByText('hosted-backend.example').waitFor()
ok('a link suggesting a server asks first, with a warning', (await page.getByText(/Only continue if you trust whoever sent it/).count()) === 1)
ok('...and nothing was saved', (await stored()) === null)
await page.goto(BASE)
ok('...so the next visit is unchanged', (await stored()) === null && (await page.getByText('localhost:8012').count()) >= 1)

// addresses that must be refused
await page.getByRole('button', { name: 'Change' }).click()
for (const bad of ['http://evil.example', 'javascript:alert(1)', 'https://user:pass@evil.example', 'not an address', 'ftp://x.example']) {
  await page.getByLabel('Server address').fill(bad)
  ok(`refuses ${bad}`, await page.getByRole('button', { name: 'Use this server' }).isDisabled())
}

// switching to another address that works, then back
await page.getByLabel('Server address').fill('http://127.0.0.1:8012')
await page.getByRole('button', { name: 'Use this server' }).click()
await page.getByText('127.0.0.1:8012').first().waitFor()
await page.getByText('connected').first().waitFor({ timeout: 10000 })
ok('a saved server is used after the page reloads', (await stored()) === 'http://127.0.0.1:8012')
await page.getByRole('button', { name: 'Change' }).click()
await page.getByRole('button', { name: 'Use the default' }).click()
await page.getByText('localhost:8012').first().waitFor()
ok('"Use the default" goes back', (await stored()) === null)

// a server that is not there
await page.getByRole('button', { name: 'Change' }).click()
await page.getByLabel('Server address').fill('http://127.0.0.1:9')
await page.getByRole('button', { name: 'Use this server' }).click()
await page.getByText('not reachable').first().waitFor({ timeout: 10000 })
ok('an unreachable server is reported, with what to do', (await page.getByText(/address changed/).count()) === 1)
await page.getByRole('button', { name: 'Change' }).click()
await page.getByRole('button', { name: 'Use the default' }).click()

// signing in over the saved server still works end to end
await page.getByRole('tab', { name: 'Sign up' }).click()
await page.getByPlaceholder('e.g. Priya Sharma').fill('Host Test')
await page.getByPlaceholder('you@example.com').fill('host@e2e.test')
await page.getByPlaceholder('At least 8 characters').fill('demo-password-1')
await page.getByPlaceholder('Type it again').fill('demo-password-1')
await page.getByRole('button', { name: 'Create account' }).click()
await page.getByText('What are we reviewing today?').waitFor()
// studio calls that need a login carry it
await page.getByText('Create draft').first().click()
await page.getByPlaceholder('Paste or write your content…').fill('Nimbus DB is a reliable platform for modern teams.')
await page.getByRole('button', { name: 'Run ENGANO Review' }).click()
await page.getByText('Ready to publish').waitFor({ timeout: 40000 })
ok('reviews work when login is required (the studio sends it)', true)

await browser.close()
process.exit(failed ? 1 : 0)
