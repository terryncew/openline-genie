# OpenLine Idea Layer — Public Challenge

Don't believe the announcement? Ask your AI. Let it inspect the code and tell you what's possible.

## The challenge

Give your AI assistant (any ordinary assistant, not only a premium coding agent) this prompt:

```
Inspect this OpenLine Idea Layer repository. Explain what it actually does, show me three businesses I could prototype using free or open-source tools, and choose one I could test cheaply. Identify what works today, what still needs building, and what evidence would show whether anyone wants it. Don't invent revenue or demand.
```

## What your AI can check

- Open `index.html` in a browser, or serve the folder locally. No install, no account, no API key, no telemetry.
- Pick one of the 12 curated starting problems, or tap **Surprise me with another**.
- Click **Copy this idea for my AI** or **Save agent brief** to get a Markdown build brief for a coding agent.
- Or from a terminal with Node 18+ (zero npm packages required):

```sh
node export_brief.mjs --list
node export_brief.mjs --sector 0 --audience individuals --format service --budget 0
```

## What it is, honestly

OpenLine Idea Layer is a free, single-file, deterministic hypothesis composer. It has no AI model inside it. Every idea is an unverified starting hypothesis, not a validated business opportunity or promised income. Each brief states its hard safety boundary, its cheapest real-world demand test, and a stop rule before you spend money or pitch anyone.

Running local open-source coding models (for example Ollama + Aider) is optional and requires a computer with enough RAM/VRAM (typically 8–16 GB) and disk space (~5–10 GB). Hosted commercial AI assistants, cloud GPUs, custom domains, and paid hosting are optional and carry separate fees.

## Verify it yourself

```sh
node --test tests/*.test.mjs trials/compare_briefs_vs_manual_template.test.mjs trials/trial_*/test.mjs
node build.mjs
sha256sum -c SHA256SUMS.txt
```

MIT License. See `LICENSE`.
