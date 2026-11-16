# ClearCovenant — Plain-Language Installation & User Guide

## 1. What ClearCovenant Does for You
ClearCovenant helps you understand your HOA or condo rules, check whether a fine or assessment follows state law, compare contractor bids, and keep a permanent, portable copy of your records—on your own computer, for free, with zero engineering jargon.

## 2. Quick 30-Second Installation (macOS, Linux, or Windows WSL2)

Requires **Python 3.11+** (no paid AI keys or internet connection required):

```bash
# 1. Unpack the installable product archive
mkdir -p ~/clearcovenant_app
unzip -q OPENLINE_NEIGHBORHOOD_001_INSTALLABLE_SOURCE.zip -d ~/clearcovenant_app
cd ~/clearcovenant_app/src_009

# 2. Start ClearCovenant on your computer
python3 genie_server.py --host 127.0.0.1 --port 8795 --no-model --state-dir ./my_hoa_records
```

## 3. Open in Your Web Browser (Desktop or Mobile)
Open **`http://127.0.0.1:8795/neighborhood`** (or `http://127.0.0.1:8795/be_neighborly`):

1. **Choose Your Role Tab**:
   - **1. Homeowner Companion**: Use on your own without waiting for your board. Your private notes and account numbers stay strictly on your machine.
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

## 4. Reproducible Verification & Clean Rollback Commands

```bash
cd ~/clearcovenant_app/src_009

# Run the standalone Neighborhood dogfooding, screenshot & portability verifier
python3 run_neighborhood_001.py

# Run the Neighborhood unit, privacy, adversarial & Chromium browser test suite
python3 -m unittest discover -s tests -p "test_neighborhood_001.py" -v

# Run the full 174-test suite across all OpenLine 009 + Five Products + Neighborhood modules
python3 -m unittest discover -s tests -p "test_*.py"

# Run the 24 independent security and browser checks
python3 muse_independent_checks.py

# Roll back bit-for-bit to the untouched Five-Product Release Candidate baseline (b9debb4b...)
patch -R -p1 < ../OPENLINE_NEIGHBORHOOD_001.patch
```
