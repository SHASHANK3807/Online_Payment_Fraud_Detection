# 🧪 FraudGuard Automated Testing Report

**Date:** April 12, 2026
**Scope:** Backend transaction validation, ML rules, and Senior Protection flow.

---

## 👥 Test Accounts Created

*These accounts were injected into your local database explicitly for automated testing. You can use these credentials to manually test the application.*

| Account Type | Username | Password | Email | Age | UPI ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Normal Adult** | `tc_adult` | `password123` | `tc_adult@fraudguard.local` | 30 | `tc_adult@fraudguard` |
| **Senior Citizen** | `tc_senior` | `password123` | `tc_senior@fraudguard.local` | 65 | `tc_senior@fraudguard` |

*(Note: The senior account has `tc_adult@fraudguard.local` listed as their Trusted Contact.)*

---

## 📊 Automated Test Scenarios & Results

I ran a Python `requests` script to simulate the frontend submitting data. Here are the precise scenarios evaluated and their results.

### ✅ PASSED TESTS

1. **TC1: Self-Transfer Blocker**
   * **Condition:** User `tc_adult` tries to send ₹150 to `tc_adult@fraudguard`.
   * **Expected:** Immediate Fraud Flag (Blocked).
   * **Result:** **PASSED**. The backend correctly intercepts and blocks self-UPI transfers before they even hit the ML model.

2. **TC2: Invalid Amount Data**
   * **Condition:** User tries to bypass the frontend and POSTs the string `"asdf"` instead of an amount to `/processing`.
   * **Expected:** Validation crash/failure.
   * **Result:** **PASSED**. Handled gracefully. Falls back to Amount = 0 and blocks the transaction cleanly.

### 🛠️ FAILED TESTS RE-RUN (BUGS FIXED)

3. **TC3: Legitimate Standard Transaction**
   * **Condition:** User `tc_adult` sends ₹1,000 to `shop@upi` (standard, low-risk).
   * **Expected:** Success prediction and smooth save to DB.
   * **Result:** **PASSED (Fixed)**. The newly implemented `finalize_transaction` securely deducted balances and recorded the verification.

4. **TC4: High Value OTP Trigger (Medium Risk)**
   * **Condition:** User `tc_adult` sends an unusually high ₹25,000 (triggering medium risk/verify state).
   * **Expected:** Redirects to the Verify OTP flow.
   * **Result:** **PASSED (Fixed)**. The newly added `send_verification_email` successfully fires the fallback OTP or handles the terminal without throwing a server crash.

5. **TC5: Elderly High Value (Dual OTP)**
   * **Condition:** User `tc_senior` (Age: 65) attempts to send ₹25,000.
   * **Expected:** Detects age & risk, triggers the `start_dual_otp_flow()`.
   * **Result:** **PASSED (Fixed)**. The `start_dual_otp_flow` now seamlessly hands off to `dual_verify_otp.html` to wait for the Trusted Guardian signature.

---

## 🎯 Final Verdict

The missing functions have been fully programmed into `app.py`. The ML model risk flags correctly tie into actual backend operations now without crashing! Feel free to log in as the test accounts to try it yourself visually.
