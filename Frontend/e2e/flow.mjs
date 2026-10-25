// End-to-end check of the web app in a real browser, against a throwaway backend (see e2e/README.md).
// Roles: brand manager sets up, creator drafts, reviewer rejects, creator revises, history and comments work for all three.
import { chromium } from 'playwright'

const BASE = process.env.E2E_BASE || 'http://localhost:4175'
const PW = 'demo-password-1'
const BAD = 'NimbusDB is a cheap database with 100% uptime. Try it free forever.'
const GOOD = 'Nimbus DB is a reliable platform for modern teams.'
let failed = 0
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`)
  if (!cond) failed++
}

const browser = await chromium.launch()
const errors = []
const page = async (label) => {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const p = await ctx.newPage()
  p.on('pageerror', (e) => errors.push(`${label}: ${e}`))
  await p.goto(BASE)
  return p
}
const signUp = async (p, name, email, purpose, brand) => {
  await p.getByRole('tab', { name: 'Sign up' }).click()
  if (purpose === 'Business') await p.getByRole('radio', { name: /Brand manager/ }).click()
  await p.getByPlaceholder('e.g. Priya Sharma').fill(name)
  await p.getByPlaceholder('you@example.com').fill(email)
  if (brand) await p.getByPlaceholder('e.g. Nimbus Cloud').fill(brand)
  await p.getByPlaceholder('At least 8 characters').fill(PW)
  await p.getByPlaceholder('Type it again').fill(PW)
  await p.getByRole('button', { name: 'Create account' }).click()
}

// ---- manager sets up
const M = await page('manager')
await signUp(M, 'Maya', 'maya@e2e.test', 'Business', 'E2E Brand')
await M.getByRole('link', { name: 'Workspaces' }).click()
await M.getByPlaceholder('e.g. Nimbus Marketing Team').fill('Marketing')
await M.getByRole('button', { name: 'Create workspace' }).click()
const code = (await M.getByText(/Join code: ENG-/).textContent()).match(/ENG-[A-Z0-9]{6}/)[0]
await M.getByPlaceholder('Reviewer’s name').fill('Rita')
await M.getByPlaceholder('reviewer@company.com').fill('rita@e2e.test')
await M.getByRole('button', { name: 'Create reviewer account' }).click()
const reviewerPw = (await M.getByText(/^Password: /).textContent()).replace('Password: ', '').trim()
await M.getByRole('link', { name: 'Brand Guidelines' }).click()
await M.locator('select').first().selectOption("DON'T")
await M.getByPlaceholder(/Never use the word cheap/).fill('Never use the word cheap.')
await M.getByRole('button', { name: 'Add Guideline' }).click()
await M.getByText('Never use the word cheap.').first().waitFor()
ok('manager set up workspace, reviewer and a rule', !!code && reviewerPw.length >= 8)

// ---- creator drafts and submits
const C = await page('creator')
await signUp(C, 'Arjun', 'arjun@e2e.test', 'Content Creator')
await C.getByRole('button', { name: 'Join workspace' }).click()
await C.getByLabel('Workspace code').fill(code)
await C.getByRole('button', { name: 'Join workspace' }).last().click()
await C.getByRole('link', { name: 'Assignments' }).waitFor()
await C.getByRole('link', { name: 'Studio' }).click()
await C.getByText('Create draft').first().click()
await C.getByPlaceholder('Paste or write your content…').fill(BAD)
await C.getByRole('button', { name: 'Run ENGANO Review' }).click()
await C.waitForSelector('mark[data-key]', { timeout: 40000 })
await C.getByRole('button', { name: 'Send for review' }).click()
await C.getByText('Pending Review').first().waitFor()
ok('creator draft with a banned word went to a reviewer', true)

// ---- reviewer: sees history, comments, rejects with a note
const R = await page('reviewer')
await R.getByPlaceholder('you@example.com').fill('rita@e2e.test')
await R.getByPlaceholder('Enter your password').fill(reviewerPw)
await R.getByRole('button', { name: 'Sign in' }).click()
await R.getByRole('button', { name: /Open (Submission|Review)/ }).first().click()
await R.getByRole('tab', { name: /History/ }).click()
ok('reviewer sees version 1 and the timeline', (await R.getByText('Arjun sent version 1 for review').count()) === 1)
await R.getByRole('tab', { name: /Comments/ }).click()
await R.getByLabel('Write a comment').fill('Is 99.95 the right uptime figure?')
await R.getByRole('button', { name: 'Comment', exact: true }).click()
await R.getByText('Is 99.95 the right uptime figure?').waitFor()
await R.getByRole('button', { name: 'Reject', exact: true }).click()
await R.getByRole('dialog').locator('textarea').fill('Remove "cheap", the uptime claim and the free-forever offer.')
await R.getByRole('dialog').getByRole('button', { name: 'Reject draft' }).click()
await R.getByRole('link', { name: 'Review Queue' }).waitFor()
ok('reviewer commented and rejected with a note', true)

// ---- creator: sees the comment and the rejection, replies, revises
await C.getByRole('link', { name: 'Approvals' }).click()
await C.getByRole('button', { name: /History & comments/ }).first().click()
await C.getByRole('tab', { name: /Comments/ }).click()
await C.getByText('Is 99.95 the right uptime figure?').waitFor({ timeout: 12000 })
await C.getByLabel('Write a comment').fill('Yes, 99.95 is in the SLA. Fixing the rest now.')
await C.getByRole('button', { name: 'Comment', exact: true }).click()
await C.getByText('Yes, 99.95 is in the SLA.').waitFor()
await C.getByRole('tab', { name: /History/ }).click()
ok('creator sees who rejected it and why', (await C.getByText('Rita asked for changes').count()) === 1 && (await C.getByText(/Remove "cheap"/).count()) >= 1)
await C.getByRole('button', { name: /Edit & resubmit/ }).click()
const box = C.getByPlaceholder('Paste or write your content…')
await box.click()
await C.keyboard.press('Control+A')
await C.keyboard.type(GOOD)
await C.getByRole('button', { name: 'Run ENGANO Review' }).click()
await C.getByText('Ready to publish').waitFor({ timeout: 40000 })
await C.getByRole('button', { name: 'Send for review' }).click()
await C.getByText('Cleared by AI').first().waitFor({ timeout: 12000 })
ok('creator revised the draft and ENGANO cleared it', true)

// ---- history: version 2 shows what changed
await C.getByRole('button', { name: /History & comments \(2 versions/ }).click()
await C.getByRole('tab', { name: /History \(2\)/ }).click()
await C.getByRole('button', { name: /Version 2/ }).click()
ok('version 2 shows added and removed words', (await C.locator('ins').count()) > 0 && (await C.locator('del').count()) > 0)
ok('timeline shows resubmitted and cleared', (await C.getByText(/sent version 2 after changes/).count()) === 1 && (await C.getByText(/ENGANO cleared it/).count()) === 1)
await C.getByRole('button', { name: /Version 1/ }).click()
ok('version 1 is still there, unchanged', (await C.getByText(BAD).count()) >= 1)

// ---- manager: approved drafts, history and comments
await M.getByRole('link', { name: 'Approved drafts' }).click()
await M.getByRole('button', { name: /History & comments/ }).first().click()
await M.getByRole('tab', { name: /Comments \(2\)/ }).waitFor({ timeout: 12000 })
await M.getByRole('tab', { name: /Comments/ }).click()
await M.getByLabel('Write a comment').fill('Thanks both. Approved for the launch.')
await M.getByRole('button', { name: 'Comment', exact: true }).click()
await M.getByText('Thanks both. Approved for the launch.').waitFor()
ok('manager can read the whole thread and join in', (await M.getByText('Yes, 99.95 is in the SLA.').count()) === 1)
ok('the address bar follows the page', new URL(M.url()).pathname.startsWith('/approved/'), M.url())

// ---- the frame stays put
await M.getByRole('link', { name: 'Workspaces' }).click()
const before = await M.evaluate(() => document.querySelector('aside').getBoundingClientRect().top)
await M.evaluate(() => document.querySelector('main').scrollTo(0, 400))
const after = await M.evaluate(() => ({ aside: document.querySelector('aside').getBoundingClientRect().top, head: document.querySelector('header').getBoundingClientRect().top, win: window.scrollY }))
ok('top bar and sidebar stay fixed while the page scrolls', after.aside === before && after.head === 0 && after.win === 0)

console.log('page errors:', errors.length ? errors : 'none')
await browser.close()
process.exit(failed ? 1 : 0)
