# FixLoop

**Your Personal Code Guard**

FixLoop is a **local-first autonomous debugging agent** that runs your code, fixes real runtime errors with minimal diffs, verifies the result, and learns locally — **without your code ever leaving your environment**.

FixLoop is built for serious developers who want **safe autonomy**, not black-box AI.

---

## Why FixLoop?

Most AI coding tools:
- generate code but **don’t run or verify it**
- require uploading private repositories to cloud services
- rewrite entire files, creating risk and distrust

FixLoop takes a different approach:

- ✅ Runs real commands  
- ✅ Applies **diff-only** patches  
- ✅ Re-runs and **verifies** results  
- ✅ Requires approval for risky changes  
- ✅ Learns locally from previous fixes  
- ✅ Keeps your code **fully under your control**

> FixLoop doesn’t replace developers — it works *with* them.

---

## Core Principles

FixLoop is designed around five non-negotiable principles:

1. Local-first by default  
2. Bring Your Own API Key (BYOK)  
3. Diff-only code changes  
4. Verification before success  
5. Human-in-the-loop for risk  

If any of these are removed, FixLoop loses its purpose.

---

## How It Works

FixLoop follows a strict engineering loop:

**Plan → Run → Error → Patch (diff-only) → Re-run → Verify → Learn**

- Executes your actual command  
- Captures real stack traces and logs  
- Generates the smallest possible patch  
- Re-runs your tests or verification step  
- Stores successful fixes locally for future reuse  

This is not a chatbot.  
This is an engineering workflow.

---

## Safety by Design

FixLoop enforces safety at every step:

- 🚫 Blocks large diffs automatically  
- 🚫 Prevents full-file rewrites  
- ⚠️ Requires approval for risky patches  
- 🔍 Shows diff before applying changes  
- ✅ Optional verification command support  

You stay in control — always.

---

## Local Memory (Learning Engine)

FixLoop includes a **local learning memory** powered by SQLite:

- Successful fixes are stored locally
- Similar future errors are recognized
- No cloud sync
- No telemetry
- No data sharing

Your experience improves **without leaking your code**.

---

## Installation

```bash
pip install fixloop

