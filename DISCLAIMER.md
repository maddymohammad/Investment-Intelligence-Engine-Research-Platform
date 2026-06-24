# Investment Intelligence Engine — Disclaimer & System Boundary Policy

## Purpose

This system is a **research, analysis, and decision-support platform** for Indian equity markets (NSE/BSE).

It is **not** a trading system, robo-advisor, or automated portfolio manager.

---

## What This System Does

| Capability | Allowed |
|---|---|
| Collect market data (prices, fundamentals, macro) | ✅ Yes |
| Analyse stocks and compute scores | ✅ Yes |
| Generate research reports (PDF, HTML, Markdown) | ✅ Yes |
| Score opportunities and rank candidates | ✅ Yes |
| Track paper (hypothetical) portfolios | ✅ Yes |
| Simulate historical performance | ✅ Yes |
| Send email reports | ✅ Yes |
| Maintain historical recommendation records | ✅ Yes |
| Commit reports to a private GitHub repository | ✅ Yes |

---

## What This System Must Never Do

| Prohibited Action | Status |
|---|---|
| Place buy or sell orders | ❌ Prohibited |
| Connect to Groww, Zerodha, Upstox, Angel One, or any brokerage | ❌ Prohibited |
| Connect to any trading API or order management system | ❌ Prohibited |
| Hold or transfer real money | ❌ Prohibited |
| Execute trades on behalf of the user | ❌ Prohibited |
| Manage a real brokerage account | ❌ Prohibited |
| Access Demat account information | ❌ Prohibited |

Any code that attempts any of the above is a **critical policy violation** and must be removed immediately.

---

## Responsibility

All output from this system — reports, scores, rankings, allocations — is for **informational and research purposes only**.

> Actual investment decisions and order execution are **always performed manually by the user**.

The system provides analysis. The human makes the decision. The human places the order — through their own brokerage, at their own discretion, at a time of their choosing.

---

## No Financial Advice

This system does not provide financial advice. Its output does not constitute a solicitation or recommendation to buy, sell, or hold any security. Past simulated performance does not guarantee future results.

---

*This policy is enforced at the code level in `src/safeguards.py`.*
