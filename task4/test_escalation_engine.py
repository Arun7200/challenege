"""
Task 4: Escalation Decision Engine Tests
8 comprehensive test cases covering all 6 rules + 2 edge cases.
Run with: pytest task4/ -v
"""

import pytest
from task4.escalation_engine import should_escalate, CustomerContext


class TestEscalationRules:
    """Test suite for escalation decision rules."""
    
    # ========================================================================
    # RULE 1: Low Confidence
    # ========================================================================
    def test_rule_1_low_confidence_escalates(self):
        """
        RULE 1 TEST: Confidence < 0.65 must escalate.
        
        Why it matters: If AI confidence is low, the response quality is
        questionable. Better to escalate than give a bad answer that
        frustrates the customer further.
        
        Scenario: AI is only 50% confident about billing question.
        Expected: Escalate with reason 'low_confidence'.
        """
        context = CustomerContext(data_complete=True)
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.5,  # Below 0.65 threshold
            sentiment_score=0.0,   # Neutral
            intent="billing",
        )
        assert should_esc == True
        assert reason == "low_confidence"
    
    # ========================================================================
    # RULE 2: Angry Customer
    # ========================================================================
    def test_rule_2_angry_customer_escalates(self):
        """
        RULE 2 TEST: Sentiment ≤ -0.6 must escalate.
        
        Why it matters: Angry customers need human empathy and personalized
        handling. Automated responses often make them angrier. Human agents
        can apologize, take ownership, and resolve faster.
        
        Scenario: Customer sentiment analysis shows strong negativity.
        Expected: Escalate with reason 'angry_customer'.
        """
        context = CustomerContext(data_complete=True)
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.95,  # High confidence
            sentiment_score=-0.8,   # Very negative
            intent="billing",
        )
        assert should_esc == True
        assert reason == "angry_customer"
    
    # ========================================================================
    # RULE 3: Repeat Complaint
    # ========================================================================
    def test_rule_3_repeat_complaint_escalates(self):
        """
        RULE 3 TEST: Same intent 3+ times in history must escalate.
        
        Why it matters: If a customer has called 3+ times about the same
        issue, the problem is systemic. AI solution probably won't work.
        Human needs to investigate and implement permanent fix.
        
        Scenario: Customer had 3 tickets about "connectivity" issues.
        Expected: Escalate with reason 'repeat_complaint'.
        """
        # Create ticket history with 3 connectivity tickets
        context = CustomerContext(
            data_complete=True,
            ticket_history=[
                {"intent": "connectivity", "status": "resolved"},
                {"intent": "connectivity", "status": "resolved"},
                {"intent": "connectivity", "status": "escalated"},
                {"intent": "billing", "status": "resolved"},
            ]
        )
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.9,
            sentiment_score=0.0,
            intent="connectivity",  # Same intent recurring
        )
        assert should_esc == True
        assert reason == "repeat_complaint"
    
    # ========================================================================
    # RULE 4: Service Cancellation
    # ========================================================================
    def test_rule_4_cancellation_always_escalates(self):
        """
        RULE 4 TEST: Service cancellation intent ALWAYS escalates (no exceptions).
        
        Why it matters: Cancellations are loss events for the company.
        Company policy requires human agents to attempt retention, discuss
        alternatives, and properly document the reason for analytics.
        AI cannot do retention sales or override company policies.
        
        Scenario: Customer wants to cancel service.
        Note: Even with high confidence and positive sentiment!
        Expected: ALWAYS escalate with reason 'service_cancellation'.
        """
        context = CustomerContext(data_complete=True)
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.99,  # Even with perfect confidence
            sentiment_score=0.5,    # Even with positive sentiment
            intent="service_cancellation",  # The key: cancellation!
        )
        assert should_esc == True
        assert reason == "service_cancellation"
    
    # ========================================================================
    # RULE 5: VIP + Overdue Billing
    # ========================================================================
    def test_rule_5_vip_overdue_escalates(self):
        """
        RULE 5 TEST: VIP customer with overdue billing must escalate.
        
        Why it matters: High-value customers (VIP tier) have payment issues,
        we need immediate human intervention to prevent churn. These are
        our best customers - losing them is expensive.
        
        Scenario: VIP customer has $150 overdue balance.
        Expected: Escalate with reason 'vip_overdue_billing'.
        """
        context = CustomerContext(
            data_complete=True,
            crm_data={"customer_tier": "vip"},  # VIP customer
            billing_data={"overdue_amount": 150.0},  # Overdue balance
        )
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.9,
            sentiment_score=0.0,
            intent="billing",
        )
        assert should_esc == True
        assert reason == "vip_overdue_billing"
    
    # ========================================================================
    # RULE 6: Incomplete Data + Low Confidence
    # ========================================================================
    def test_rule_6_incomplete_data_low_confidence_escalates(self):
        """
        RULE 6 TEST: Incomplete data + confidence < 0.80 must escalate.
        
        Why it matters: If we couldn't fetch all customer data (CRM, billing,
        tickets failed) AND AI confidence is below 0.80, we're flying blind.
        Human agent can use their tools/context to handle better.
        
        Scenario: Billing system was down (data_complete=False) and AI
        confidence is only 0.75 (below 0.80 threshold).
        Expected: Escalate with reason 'incomplete_data_low_confidence'.
        """
        context = CustomerContext(
            data_complete=False,  # Some data fetch failed
            crm_data=None,        # CRM data not available
        )
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.75,  # Below 0.80 threshold
            sentiment_score=0.0,
            intent="billing",
        )
        assert should_esc == True
        assert reason == "incomplete_data_low_confidence"
    
    # ========================================================================
    # EDGE CASE 1: Rule Conflict - Cancellation vs High Confidence
    # ========================================================================
    def test_edge_case_1_cancellation_beats_confidence(self):
        """
        EDGE CASE 1: When multiple rules apply, which one wins?
        
        Scenario: Confidence is very high (0.95) but customer wants to cancel.
        Question: Should we AI-handle (high confidence) or escalate (cancellation)?
        
        Answer: Cancellation rule is BUSINESS RULE that overrides confidence.
        Rule 4 (cancellation) is evaluated BEFORE checking if confidence is OK.
        The implementation checks rules in order and returns on first match.
        
        Why this order matters: Cancellation is a special business case that
        takes priority over AI capability. Even a perfect AI response can't
        retain customers or process cancellation through AI.
        
        Expected: Escalate (RULE 4) with reason 'service_cancellation'.
        """
        context = CustomerContext(data_complete=True)
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.95,  # Very high confidence
            sentiment_score=0.5,    # Very positive sentiment
            intent="service_cancellation",  # But wants to cancel
        )
        assert should_esc == True
        assert reason == "service_cancellation"  # Cancellation rule wins
    
    # ========================================================================
    # EDGE CASE 2: No Escalation - Perfect Conditions
    # ========================================================================
    def test_edge_case_2_no_escalation_required(self):
        """
        EDGE CASE 2: When should AI handle WITHOUT escalation?
        
        Scenario: All conditions are good - AI is confident, customer is
        happy, data is complete, no repeat issues.
        
        Why this matters: The AI should handle the MAJORITY of cases.
        Only exceptional cases escalate. This test verifies the happy path.
        
        Conditions for AI to handle:
        - Confidence >= 0.65
        - Sentiment > -0.6
        - Intent is NOT 'service_cancellation'
        - No repeat complaints (or complete tickets not available)
        - All data available OR confidence >= 0.80
        
        Expected: AI can handle it (no escalation).
        """
        context = CustomerContext(
            data_complete=True,  # All data available
            ticket_history=[],   # No previous issues
            crm_data={"customer_tier": "standard"},
            billing_data={"overdue_amount": 0},
        )
        should_esc, reason = should_escalate(
            context,
            confidence_score=0.88,  # Good confidence
            sentiment_score=0.2,    # Positive sentiment
            intent="billing",       # Regular inquiry
        )
        assert should_esc == False
        assert reason == "ai_handle"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
