# OpenLine Idea Layer

A free, single-file tool that helps you pick a concrete small-business hypothesis, see its hard safety boundaries and cheapest real-world demand test upfront, and copy a build-ready assignment straight into your coding agent.

**No account, API key, or telemetry.** The page runs entirely in your browser (`connect-src 'none'`). It makes no network requests.

## Try it (No install needed)

1. Open `index.html` in any modern browser, or visit the hosted site: https://terryncew.github.io/openline-idea-layer/
2. Pick what interests you, who the customer could be, and how it might earn money — or tap **Surprise me with another**.
3. Read the hypothesis: buyer, revenue path, hard safety boundary, first real test, budget ceiling, stop rule, first thing to build, and how to know it works.
4. Click **Copy this idea for my AI** or **Save agent brief** to hand a complete Markdown assignment to your coding agent.

Or inspect and export briefs from a terminal with Node 18+ (zero npm packages required):

```sh
node export_brief.mjs --list
node export_brief.mjs --sector 0 --audience individuals --format service --budget 0
```

## Free, Open-Source AI Path & Honest Cost Disclosures

- **OpenLine Idea Layer**: `MIT` license (`LICENSE`). Requires only a modern web browser (`$0` software/API cost).
- **Local Open-Source Coding Stack (Optional)**:
  - [Ollama](https://github.com/ollama/ollama) (`MIT` license) runs local language models on your own computer.
  - [Aider](https://github.com/Aider-AI/aider) (`Apache-2.0` license) connects a terminal coding workflow to local or hosted models.
  - **Model & Hardware Requirements**: Running a capable 7B–14B coding model locally (e.g., `Qwen2.5-Coder-7B`, `Apache-2.0`) typically requires a desktop or laptop with **8–16 GB RAM/VRAM**, **~5–10 GB free disk storage**, and electricity. Model weights have their own separate licenses (Apache-2.0, MIT, or custom community terms) that must be checked before commercial use.
- **Optional Paid Services**: Using a hosted commercial coding assistant (ChatGPT, Claude, Gemini, Cursor, Copilot), renting cloud GPUs, buying a custom domain, or paying for web hosting is optional and incurs separate third-party fees.

## Honest Scope

12 curated business starting problems × 3 customer classes × 3 delivery formats = 108 structured combinations, each with 4 scope angles (432 deterministic variants). There is **no AI model** inside this page. It has not discovered new markets, customers, validated demand, or measured profits. Ideas are unverified starting hypotheses, not validated business opportunities or promised income.

Existing OpenLine repositories linked from exported briefs (`openline-energy`, `openline-energy-autopilot`, `mandate-ledger`, `openline-connect`, `openline-living-projects`) are optional research references, not drop-in production dependencies. Inspect their current README, license, commit, and security limitations before reuse.

## What Was Verified

- `node --test` suite: **20/20 PASS, 0 fail, 0 skip** (engine contract, customer contract, 6-sector brief-vs-manual-template comparison, and 6 exported-brief prototype trial suites across Public records `IL-3-0`, Food allergen `IL-8-0`, Security `IL-11-0`, Home energy `IL-1-0`, Accessibility `IL-4-0`, and Education minor-privacy `IL-6-0`).
- Real headless Chromium verification across `320×640`, `390×844`, and `1280×850` viewports: all 12 sectors, live `$125` budget interpolation, invalid-budget `-50` fail-closed behavior, and file download verified with 0 console errors and 0 horizontal overflow.
- Competent conventional baseline comparison: an ordinary 4-field manual template scores `1/7`, whereas a competent expert-authored manual specification achieves **`7/7 PARITY`** with Idea Layer's exported brief. The test scores required sections, not human performance. An arithmetic illustration of 350–450 words at 35–45 words per minute is roughly 8–13 minutes; no timed user study establishes time saved. It does not prove market demand or outperform an expert's specification.

## Try the Public Challenge

Ask your own AI assistant to inspect this repository. Paste it this prompt:

```
Inspect this OpenLine Idea Layer repository. Explain what it actually does, show me three businesses I could prototype using free or open-source tools, and choose one I could test cheaply. Identify what works today, what still needs building, and what evidence would show whether anyone wants it. Don't invent revenue or demand.
```

It works with ordinary AI assistants, not only premium coding agents. Everything it finds is a starting hypothesis, not a validated business. See `PUBLIC_CHALLENGE.md` for the full challenge.

## For Developers (Optional)

```sh
# Run the complete 20-test suite (Node 18+)
node --test tests/*.test.mjs trials/compare_briefs_vs_manual_template.test.mjs trials/trial_*/test.mjs

# Rebuild the deployable single-file index.html from modular source
node build.mjs

# Verify file integrity
sha256sum -c SHA256SUMS.txt
```

## License

MIT. See `LICENSE`.
