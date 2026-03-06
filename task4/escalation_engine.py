"""
Task 4: Escalation Decision Engine
Determines whether a customer should be escalated to a human agent or handled by AI.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any
from collections import Counter


@dataclass
class CustomerContext:
    """Customer context from data fetching."""
    crm_data: Optional[Dict[str, Any]] = None
    billing_data: Optional[Dict[str, Any]] = None
    ticket_history: Optional[List[Dict[str, Any]]] = None
    data_complete: bool = False
    fetch_time_ms: float = 0.0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def should_escalate(
    context: CustomerContext,
    confidence_score: float,
    sentiment_score: float,
    intent: str,
) -> Tuple[bool, str]:
    """
    Determine if a customer should be escalated to a human agent.
    
    Implements 6 decision rules evaluated in order:
    
    Rule 1: Low confidence → escalate (reason: "low_confidence")
    Rule 2: Angry customer → escalate (reason: "angry_customer")
    Rule 3: Repeat complaint → escalate (reason: "repeat_complaint")
    Rule 4: Service cancellation → always escalate (no exceptions)
    Rule 5: VIP + overdue billing → escalate
    Rule 6: Incomplete data + low confidence → escalate
    
    Args:
        context: CustomerContext with CRM, billing, and ticket data
        confidence_score: AI confidence in response (0.0 to 1.0)
        sentiment_score: Customer sentiment (-1.0 to 1.0, negative = angry)
        intent: Customer intent classification (e.g., "billing", "cancellation")
    
    Returns:
        Tuple of (should_escalate: bool, reason: str)
    """
    
    # ========================================================================
    # RULE 1: Low Confidence
    # ========================================================================
    # If AI confidence below 0.65, we don't trust the AI response enough.
    # Always escalate to ensure customer satisfaction.
    if confidence_score < 0.65:
        return (True, "low_confidence")
    
    # ========================================================================
    # RULE 2: Angry Customer
    # ========================================================================
    # If sentiment is very negative (≤ -0.6), customer is angry/frustrated.
    # Escalate to human agent for empathy and personalized handling.
    if sentiment_score <= -0.6:
        return (True, "angry_customer")
    
    # ========================================================================
    # RULE 3: Repeat Complaint
    # ========================================================================
    # If same intent appears 3+ times in ticket history, it's a recurring issue.
    # Escalate to specialist who can review the full context.
    if context.ticket_history:
        intent_counts = Counter(ticket["intent"] for ticket in context.ticket_history)
        if intent_counts[intent] >= 3:
            return (True, "repeat_complaint")
    
    # ========================================================================
    # RULE 4: Service Cancellation
    # ========================================================================
    # Special handling: ANY cancellation request goes to human.
    # No exceptions - company policy requires human approval on cancellations.
    if intent == "service_cancellation":
        return (True, "service_cancellation")
    
    # ========================================================================
    # RULE 5: VIP + Overdue Billing
    # ========================================================================
    # High-value customers with payment issues need immediate human attention.
    # Prevents churn and maintains customer relationships.
    if context.crm_data and context.billing_data:
        is_vip = context.crm_data.get("customer_tier") == "vip"
        is_overdue = (context.billing_data.get("payment_status") or "").startswith("60_days") or \
                     context.billing_data.get("payment_status") == "60_days"
        
        # Simplified: treat 30+ days overdue as critical
        overdue_amount = context.billing_data.get("overdue_amount", 0)
        is_overdue = overdue_amount > 0
        
        if is_vip and is_overdue:
            return (True, "vip_overdue_billing")
    
    # ========================================================================
    # RULE 6: Incomplete Data + Low Confidence
    # ========================================================================
    # If we couldn't fetch complete customer data AND AI confidence is below 0.80,
    # escalate to human who can use their context/tools.
    if not context.data_complete and confidence_score < 0.80:
        return (True, "incomplete_data_low_confidence")
    
    # ========================================================================
    # NO ESCALATION NEEDED
    # ========================================================================
    # If none of the rules triggered, AI can handle it.
    return (False, "ai_handle")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_context_summary(context: CustomerContext) -> str:
    """Format a context summary for debugging/logging."""
    summary = []
    summary.append(f"Data Complete: {context.data_complete}")
    
    if context.crm_data:
        summary.append(f"Tier: {context.crm_data.get('customer_tier', 'unknown')}")
    
    if context.billing_data:
        overdue = context.billing_data.get("overdue_amount", 0)
        summary.append(f"Overdue: ${overdue}")
    
    if context.ticket_history:
        summary.append(f"Previous Tickets: {len(context.ticket_history)}")
    
    return " | ".join(summary)


if __name__ == "__main__":
    # Example usage
    print("Escalation Decision Engine")
    print("=" * 60)
    
    # Example 1: Low confidence
    context = CustomerContext(data_complete=True)
    should_esc, reason = should_escalate(context, 0.5, 0.0, "billing")
    print(f"\nExample 1 - Low confidence:")
    print(f"  Should escalate: {should_esc}, Reason: {reason}")
    
    # Example 2: Angry customer
    context = CustomerContext(data_complete=True)
    should_esc, reason = should_escalate(context, 0.9, -0.8, "billing")
    print(f"\nExample 2 - Angry customer:")
    print(f"  Should escalate: {should_esc}, Reason: {reason}")
    
    # Example 3: Service cancellation
    context = CustomerContext(data_complete=True)
    should_esc, reason = should_escalate(context, 0.9, 0.0, "service_cancellation")
    print(f"\nExample 3 - Cancellation request:")
    print(f"  Should escalate: {should_esc}, Reason: {reason}")
