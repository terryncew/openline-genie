# ClearCovenant — Plain-Language Installation & User Guide

## 1. What ClearCovenant Does for You
ClearCovenant helps you understand your HOA or condo rules, check whether a fine or assessment follows state law, compare contractor bids, and keep a permanent, portable copy of your records—on your own computer, for free, with zero engineering jargon.

## 2. Quick Installation (macOS, Linux, or Windows WSL2)

Requires **Python 3.11+** (no paid AI keys needed; the first install downloads two packages, so it needs network access once):

```bash
# 1. Get the ClearCovenant source files onto your computer and enter the folder
#    (the folder that contains genie_server.py)
cd clearcovenant

# 2. Create a private Python environment and install the two needed packages
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Start ClearCovenant on your computer
.venv/bin/python genie_server.py --host 127.0.0.1 --port 8795 --no-model --state-dir ./my_hoa_records
```

ClearCovenant runs only on your own computer. It has no login: anyone who can open the page on your computer can see your records, so do not share the address with anyone else, and do not expose the port (8795) beyond your computer.

## 3. Open in Your Web Browser (Desktop or Mobile)
Open **`http://127.0.0.1:8795/neighborhood`**:

1. **Choose Your Role Tab**:
   - **1. Homeowner Companion**: Use on your own without waiting for your board. Your private notes and account numbers stay on your own computer. Anyone who can open this page on your computer can see them, so keep the computer to yourself.
   - **2. Volunteer Board Desk**: Compare vendor bids, check reserve study math, and write clear, rule-cited explanations for residents.
   - **3. Community Commons & Transition**: Share redacted neighborhood solutions and export complete association records when switching management companies.
2. **Upload Your HOA Documents or Pick a Sample Scenario**:
   - Choose any of the **12 real-world HOA scenarios** in Step 1, or paste a section from your CC&Rs, bylaws, board rules, or violation notice and click **Add Document to Packet & Preview**.
3. **Ask a Question & Prepare Your Response**:
   - Type your question in Step 2, enter any notice/postmark dates or fine amounts, and click **Check Rules & Draft Response**.
   - If your uploaded documents don't cover the topic, ClearCovenant will honestly tell you: **"The documents don’t establish an answer."** and draft a records request for the missing rules.
4. **Save to Your Official Record & Export Anytime**:
   - Click **Save to Official Record** in the yellow preview banner to commit a change, or **Discard Draft** to cancel.
   - Check the approval box in Step 3 and click **Lock My Approved Response Packet** when you are ready to print or email your letter.
   - Click **Download Portable HTML Record** or **Export Portable Record Bundle (JSON)** in Step 6 to take your records anywhere.

## 4. Reproducible Verification

```bash
cd clearcovenant

# Run the Neighborhood checks: 12 sample HOA cases, privacy checks,
# hostile-upload checks, and the server, save-and-reload, and recovery checks
.venv/bin/python -m pytest tests/test_neighborhood_001.py -q

# Run the full test suite for this source tree (measured counts are recorded
# in the qualification log; browser checks need Chrome, which this
# computer may not have, and are reported as not verified when absent)
.venv/bin/python -m pytest tests/ -q
```

Your records live in the folder you gave with `--state-dir` (`./my_hoa_records` above). Delete that folder to start over; your saved records go with it.
