# Investment Intelligence Engine

## Goal

Build an autonomous AI-powered investment research system that runs Monday-Friday after market close.

The system should:

- Analyze stock markets deeply before making recommendations.
- Select:
  - 2 Small-Cap Stocks
  - 2 Large-Cap Stable Growth Stocks
- Generate a professional investment report.
- Send the report to my email automatically.
- Store all historical recommendations.
- Track recommendation performance.
- Maintain a private GitHub repository.
- Create Git commits for every successful run.

---

# Core Requirements

## Data Collection

Collect:

### Fundamental Data

- Revenue Growth
- EPS Growth
- ROE
- ROCE
- Debt/Equity
- P/E Ratio
- PEG Ratio
- Cash Flow
- Profit Margin

### Technical Data

- RSI
- MACD
- Moving Averages
- Volume Analysis
- Trend Strength
- Breakout Detection

### Market Sentiment

- News
- Earnings Reports
- Analyst Reports
- Social Sentiment

### Macro Analysis

- Inflation
- Interest Rates
- GDP Trends
- Sector Rotation

---

# Stock Selection

Every weekday select:

## Small Cap

Choose 2 stocks based on:

- Growth
- Earnings Quality
- Healthy Balance Sheet
- Positive Momentum

## Large Cap

Choose 2 stocks based on:

- Stable Growth
- Market Leadership
- Strong Cash Flow
- Long-Term Potential

---

# Deep Analysis

Before recommending a stock:

- Fundamental Analysis
- Technical Analysis
- Sector Analysis
- Competitor Analysis
- Risk Analysis
- Valuation Analysis

Generate:

- Bull Case
- Bear Case
- Risk Factors
- Catalysts
- Confidence Score

---

# Daily Report

Generate:

- Market Summary
- Sector Summary
- Recommended Stocks
- Portfolio Allocation
- Key Risks

Export:

- Markdown
- PDF
- HTML

Store in:

reports/daily/

---

# Email Automation

After report generation:

- Send daily email
- Attach report
- Include summary

---

# Performance Tracking

Track:

- Entry Price
- Current Price
- Return %
- Win Rate
- Sharpe Ratio
- Benchmark Comparison

Compare against:

- NIFTY 50
- SENSEX

---

# Automation

Run:

Monday-Friday

6:00 PM IST

Workflow:

1. Fetch Data
2. Analyze Market
3. Rank Stocks
4. Generate Report
5. Email Report
6. Save Results
7. Commit To GitHub

---

# Dashboard

Build dashboard using:

- Streamlit

Display:

- Recommendations
- Performance
- Portfolio Growth
- Historical Results

---

# Security

Use:

- Environment Variables
- GitHub Secrets
- Secure Credential Storage

Never hardcode API keys.

---

# Deliverables

1. Source Code
2. GitHub Repository
3. Automated Scheduler
4. Email System
5. Dashboard
6. Historical Database
7. Deployment Guide

First task:

Read this specification completely.

Do NOT write code yet.

Provide:

1. Architecture Design
2. Folder Structure
3. Database Schema
4. Required APIs
5. Required Environment Variables
6. Development Roadmap

Wait for approval before coding.