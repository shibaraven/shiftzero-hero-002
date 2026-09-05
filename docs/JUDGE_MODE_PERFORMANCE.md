# Judge Mode performance gate

The local acceptance target is first-page load under 5,000 ms. This is a website usability
measurement only; it does not satisfy anonymous public access.

## Recorded method

- Build: `npm run build` in `apps/web`.
- Runtime: the generated Cloudflare Worker-compatible production bundle served on loopback.
- Browser: Codex in-app Chromium browser.
- Samples: 20 total—one new-tab navigation followed by 19 same-tab reloads.
- Timing: end-to-end wall time immediately before navigation until the browser reported the page
  `load` state.
- Statistics: median and interpolated p95; acceptance requires every p95 result to remain below
  5,000 ms.

The raw values, environment, timestamp, target, median and p95 are stored in
`evidence/judge-mode-load.json`. This local result must be repeated against the final anonymous
public URL before A09 can pass.
