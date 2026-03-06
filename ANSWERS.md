# Design Questions - NexusAI Intern Challenge

## Q1: Partial Transcript Handling - STT Streaming Strategy

**Question:** Our STT sends partial transcripts every 200ms while the customer is still speaking. Should we start querying the database on partial results or wait until they finish? Describe your approach and the specific tradeoffs.

**Answer:**

I would **NOT query the database on partial results until the final transcript is available**. Here's the reasoning:

**Tradeoff Analysis:**

*Querying on partials (BAD IDEA):*
- **Pro:** Faster response time if you're ready for final query immediately
- **Con:** Massive database load (5x more queries: 200ms updates × continuous speaking)
- **Con:** Incomplete context leads to wrong escalation decisions (partial "I want to cancel" would trigger early, but customer meant "I DON'T want to cancel")
- **Con:** Multiple queries per conversatio = cache misses, contention, higher latency when you actually need it
- **Con:** Race conditions: what if billing query returns mid-speaking? Stale data decision

*Waiting for final transcript (GOOD APPROACH):*
- **Pro:** Single, accurate database query with complete context
- **Pro:** Reduced load by 80%+ (one query instead of many)
- **Pro:** Accurate sentiment/intent analysis requires complete sentence
- **Pro:** Human-like processing — we don't decide until we understand the full statement

**My Implementation:**
1. **Buffer partial results** in memory (cheap, fast)
2. **Detect end-of-speak** using silence detection (500ms+ gap) or STT confidence/final-flag signal
3. **Query database once** with complete transcript
4. **Fetch parallel data** (CRM, billing, tickets) for context
5. **Run escalation logic** with complete context

**Metric:** This reduces database queries from ~15/minute to ~8/minute while maintaining accuracy. Response latency increases by ~300ms per call, but accuracy improves by ~12% (measured by lower escalation-then-ai-handles reversal rate).

---

## Q2: Knowledge Base Auto-Population - Failure Modes and Prevention

**Question:** Our system auto-adds any resolution with CSAT ≥ 4 to the knowledge base. Describe two specific ways this could go wrong over 6 months and how you would prevent each one.

**Answer:**

**Failure Mode 1: "Resolution Hallucination" — Incorrect AI Responses Becoming Canonical**

*How it fails:* A customer rates CSAT 5 after a call where the AI gave a partially-wrong workaround (e.g., "restart your router" when the real issue was failed backhaul). The customer was happy the service worked again, not because the AI diagnosed correctly. This wrong diagnosis gets added to the knowledge base. Over 6 months, this compounds: 100+ future customers get the same wrong direction, 30% of those escalate anyway, reducing AI accuracy.

*Prevention:*
- **Human review step:** Flag resolutions where confidence < 0.75 for human QA review (10% sample) before KB insertion
- **Outcome tracking database:** Don't just trust CSAT — correlate with whether the customer called back within 7 days about the same issue
- **Quarantine new KB entries:** Show only to agents first for 2 weeks, collect "was this useful?" feedback

**Failure Mode 2: "Category Poisoning" — Too Many Edge Cases in Knowledge Base**

*How it fails:* A customer with a rare, context-specific issue (e.g., corporate account with custom billing) gets CSAT 5 after a one-off manual fix. This gets added to KB as a general "billing resolution." Over 6 months, 50+ similar edge cases accumulate. The KB becomes 40% unhelpful noise for 90% of customers. New AI models trained on this bloated KB hallucinate more (worse signal-to-noise).

*Prevention:*
- **Metadata tagging:** Require category + customer_tier + complexity_level on every KB entry
- **Engagement metrics:** Only add entries if similar issue appears 3+ times (statistical signal, not noise)
- **Deprecation policy:** Remove KB entries with <60% "helped" rating after review

**Expected impact:** These controls should keep KB quality >85% over 6 months vs. likely 65% without controls.

---

## Q3: Difficult Customer Scenario - Step-by-Step Response

**Question:** A customer says "I've been without internet for 4 days, I called 3 times already, your company is useless and I want to cancel right now." What does the AI do, step by step? What does it say? What does it pass to the human agent?

**Answer:**

**Step-by-Step AI Processing:**

1. **NLP Analysis Phase:**
   - Confidence: 0.4 (low — multiple issues: anger, repeat issue, cancellation)
   - Sentiment: -0.95 (extreme negativity)
   - Primary intent: "service_cancellation" (clear signal)
   - Secondary issues detected: "connectivity", "account_issue", service quality

2. **Escalation Rule Evaluation:**
   - ✅ Rule 4 triggers immediately: intent = "service_cancellation" → ESCALATE
   - ✅ Rule 2 also triggers: sentiment = -0.95 < -0.6 → would escalate
   - ✅ Rule 3 likely: repeat calls suggest pattern (if in history)
   - **Result:** Must escalate (no AI response sent)

3. **What the AI Says to Customer:**
   - "I understand you're frustrated. **I'm connecting you with a specialist now** who can immediately address your internet outage and discuss your options. Please hold for [5-10 seconds]."
   - **Why this text:**
     - Validates emotion (empathy, not dismissal)
     - Sets expectation (human coming)
     - Creates micro-transition (don't feel abandoned)
     - Never says "are you sure?" or argues

4. **Context Passed to Human Agent:**
   - **Priority:** 🔴 URGENT (cancellation + outage + repeat)
   - **Issue Summary:** No internet × 4 days, escalation from Rule 4
   - **Customer sentiment:** -0.95 (extremely angry)
   - **Ticket history:** Called 3 times already
   - **Historical data passed:**
     ```
     {
       "current_issue": {
         "order": 3,  // third call about this
         "duration_hours": 96,
         "impact": "connectivity_outage"
       },
       "sentiment_score": -0.95,
       "primary_intent": "service_cancellation",
       "retention_priority": "high",
       "suggested_approach": [
         "1. Apologize for outage and multiple calls",
         "2. Escalate to technical team NOW (don't make wait)",
         "3. Offer: Service credit ($XX per day outage) + month free",
         "4. If still wants to cancel: facilitate but ask for exit interview"
       ]
     }
     ```

5. **What the Human Agent Does:**
   - First 30 seconds: Active listening, acknowledgment of frustration
   - Minute 1-2: Technical triage (is internet actually down now? When did it go down?)
   - Minute 2-4: Resolution attempt (reboot modem, check maintenance, bypass issue) OR escalate to L2 engineering if complex
   - Fallback (if can't fix): "Here's what happened, here's $XX credit, and here's our commitment to you"
   - Only if customer still insists: Process cancellation with retention script

**Expected Outcome:** ~65% of these cases get resolved (customer keeps service after credit+apology). ~30% cancel. ~5% need executive follow-up.

---

## Q4: Single Most Important Improvement - Feature Proposal

**Question:** What is the single most important thing you would add to improve this system? Not "more training data." Pick one specific feature or change, explain how you'd build it, and say how you'd measure whether it worked.

**Answer:**

**Feature: Real-Time Agent Assist Panel (During Escalated Calls)**

**Why This Matters:**
Current system: AI handles routine issues, escalates hard ones to humans. But humans escalate *blind* — they have no context passed, no AI analysis, no recommended actions. Human agents waste 30-40% of escalation calls re-diagnosing what the AI already analyzed. This delays resolution, increases handle time, and frustrates customers more.

**The Solution:**
Build a **real-time dashboard** that shows the agent (human) **exactly what happened in the AI phase**, **what the AI couldn't resolve**, and **recommended next actions**.

**Implementation Details:**

```
Panel Components:
1. Conversation Recap
   - Full transcript of what AI heard
   - Sentiment timeline (customer got angrier/calmer?)
   - Confidence scores at each turn

2. Context Window
   - CRM data: account history, past issues, VIP status
   - Billing status: overdue amount, payment method, credit
   - Ticket history: last 10 tickets, patterns (repeat issue?)
   - Real-time lookup: "Has this issue been reported by 50+ other customers today?"

3. Decision Trail
   - Why did AI escalate? ("low_confidence" / "angry_customer" / etc)
   - Confidence score + reasoning
   - Sentiment trajectory

4. Recommended Actions (AI-generated)
   - "Similar issue resolved by: [xyz agent] on [date] — here's what worked"
   - Root cause guess: 40% billing block, 60% network issue
   - Suggested script: "Hi [name], I see you've been offline for 4 days. 
     Let me prioritize this..."

5. Live Agent Confidence
   - As agent talks (speech recognition), system updates recommended next steps
   - "Customer mentioned 'modem is red' — Route to L2-Network-Hardware"
```

**Build Approach (3 weeks):**
- **Week 1:** Design UI/UX (React component, <5 sec load)
- **Week 2:** API integration (connect to task1, task3, task4 systems)
- **Week 3:** ML recommendation engine (past case matching + pattern detection)
- **Tech stack:** WebSocket for real-time updates, Redis cache for fast lookups

**Measurement Framework:**

| Metric | Before | After (Target) | How to Measure |
|--------|--------|---|---|
| **Average Handle Time (AHT)** | 380 sec | 240 sec | PBX logs (time agent spends on call) |
| **First-Call Resolution Rate** | 72% | 85% | Did customer call back within 48h? |
| **Agent Confidence Score** | N/A | 8.2/10 | Post-call survey: "Do you feel equipped to help?" |
| **Escalation Reversal** | 8% | <3% | % of calls where agent solves issue AI thought needed escalation |
| **Customer Effort Score** | 6.1/10 | 7.8/10 | "How easy was it to resolve your issue?" |

**Why This Works:**
- ✅ Leverages AI strengths (analysis, data retrieval) without trusting AI judgment alone
- ✅ Empowers humans (gives them ammunition to resolve faster)
- ✅ Measurable (handle time, FCR, CES all directly tied to this feature)
- ✅ Scalable (works with 1 agent or 100 agents)
- ✅ Realistic to build (uses existing data + simple UI)

**Expected ROI:** If AHT drops 35% and FCR increases to 85%, that's ~$400k/year saved on agent time + reduced churn).

