import asyncio
import re
from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime
import os

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class MessageResponse:
    
    response_text: str
    confidence: float  # 0 to 1
    suggested_action: str
    channel_formatted_response: str
    error: Optional[str] = None


# System prompts optimized for telecom support
SYSTEM_PROMPTS = {
    "voice": """You are a professional telecom customer support agent handling voice calls.
Your role is to:
- Diagnose technical issues quickly and accurately
- Provide clear, concise solutions (NO MORE THAN 2 SENTENCES)
- Detect customer frustration and escalate when needed
- Be authoritative but empathetic

Examples of good responses:
- "Your service was affected by a network outage from 2-3 PM. We've restored service now."
- "I'm escalating you to a specialist who can review billing credits."

CRITICAL: Keep voice responses under 2 sentences. Be direct and actionable.""",

    "chat": """You are a telecom customer support agent handling chat conversations.
Your role is to:
- Provide thorough, detailed explanations
- Guide customers through troubleshooting steps
- Be friendly and document-friendly (chat logs are reviewed)
- Format responses with clear structure

You can use:
- Numbered lists for steps
- Bullet points for options
- Separate paragraphs for clarity

Remember: Chat customers have time to read; be helpful and complete.""",

    "whatsapp": """You are a telecom customer support agent handling WhatsApp messages.
Your role is to:
- Keep responses SHORT and scannable (mobile users)
- Use emojis sparingly but naturally
- Build on previous context from this conversation
- Be friendly and personal

Format:
- Keep paragraphs to 2-3 sentences max
- Use line breaks between thoughts
- Make key info easy to spot

Examples:
- "Your bill: $89.99 due by March 15 ✓"
- "Try restarting your router in 30 seconds."
""",
}


async def handle_message(
    customer_message: str,
    customer_id: str,
    channel: Literal["voice", "whatsapp", "chat"],
) -> MessageResponse:
    """
    Handle a customer message and return a structured AI response.
    
    Args:
        customer_message: The customer's input text
        customer_id: Unique identifier for the customer
        channel: Communication channel - "voice", "whatsapp", or "chat"
    
    Returns:
        MessageResponse dataclass with response_text, confidence, suggested_action,
        channel_formatted_response, and optional error field
    
    Handles three error cases:
    1. API timeout after 10 seconds
    2. API rate limit - retries once after 2 seconds
    3. Empty/whitespace-only input - returns error without API call
    """
    
    # Error Case 3: Empty or whitespace-only input
    if not customer_message or not customer_message.strip():
        return MessageResponse(
            response_text="",
            confidence=0.0,
            suggested_action="user_input_empty",
            channel_formatted_response="",
            error="Customer message is empty or contains only whitespace",
        )
    
    customer_message = customer_message.strip()
    
    # Validate channel
    if channel not in ["voice", "whatsapp", "chat"]:
        return MessageResponse(
            response_text="",
            confidence=0.0,
            suggested_action="invalid_channel",
            channel_formatted_response="",
            error=f"Invalid channel: {channel}. Must be 'voice', 'whatsapp', or 'chat'",
        )
    
    # Determine which API to use
    api_provider = "anthropic" if HAS_ANTHROPIC else "openai"
    
    if not HAS_ANTHROPIC and not HAS_OPENAI:
        return MessageResponse(
            response_text="",
            confidence=0.0,
            suggested_action="api_not_available",
            channel_formatted_response="",
            error="No API provider available. Install anthropic or openai.",
        )
    
    try:
        if api_provider == "anthropic":
            return await _handle_with_anthropic(
                customer_message, customer_id, channel
            )
        else:
            return await _handle_with_openai(customer_message, customer_id, channel)
    
    except asyncio.TimeoutError:
        # Error Case 1: API timeout
        return MessageResponse(
            response_text="",
            confidence=0.0,
            suggested_action="escalate_timeout",
            channel_formatted_response="",
            error="API request timed out after 10 seconds",
        )
    
    except Exception as e:
        # Unexpected error
        return MessageResponse(
            response_text="",
            confidence=0.0,
            suggested_action="escalate_error",
            channel_formatted_response="",
            error=f"Unexpected error: {str(e)}",
        )


async def _handle_with_anthropic(
    customer_message: str, customer_id: str, channel: str
) -> MessageResponse:
    """Handle message using Anthropic Claude API."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    system_prompt = SYSTEM_PROMPTS.get(channel, SYSTEM_PROMPTS["chat"])
    
    retry_count = 0
    max_retries = 1
    
    while retry_count <= max_retries:
        try:
            # Wrap in timeout - 10 seconds
            message = await asyncio.wait_for(
                asyncio.to_thread(
                    client.messages.create,
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=150 if channel == "voice" else 500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": customer_message}],
                ),
                timeout=10.0,
            )
            
            response_text = message.content[0].text
            
            # Calculate confidence based on stop reason
            confidence = 0.95 if message.stop_reason == "end_turn" else 0.75
            
            # Format for channel
            channel_response = _format_for_channel(response_text, channel)
            
            # Detect intent for suggested_action
            suggested_action = _detect_intent(customer_message)
            
            return MessageResponse(
                response_text=response_text,
                confidence=confidence,
                suggested_action=suggested_action,
                channel_formatted_response=channel_response,
                error=None,
            )
        
        except asyncio.TimeoutError:
            raise
        
        except APIError as e:
            # Error Case 2: Rate limit
            if "rate_limit" in str(e).lower() and retry_count < max_retries:
                retry_count += 1
                await asyncio.sleep(2)  # Wait 2 seconds before retry
                continue
            else:
                raise


async def _handle_with_openai(
    customer_message: str, customer_id: str, channel: str
) -> MessageResponse:
    """Handle message using OpenAI API."""
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    system_prompt = SYSTEM_PROMPTS.get(channel, SYSTEM_PROMPTS["chat"])
    
    retry_count = 0
    max_retries = 1
    
    while retry_count <= max_retries:
        try:
            # Wrap in timeout - 10 seconds
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    openai.ChatCompletion.create,
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": customer_message},
                    ],
                    temperature=0.7,
                    max_tokens=150 if channel == "voice" else 500,
                ),
                timeout=10.0,
            )
            
            response_text = response["choices"][0]["message"]["content"]
            confidence = 0.9
            
            channel_response = _format_for_channel(response_text, channel)
            suggested_action = _detect_intent(customer_message)
            
            return MessageResponse(
                response_text=response_text,
                confidence=confidence,
                suggested_action=suggested_action,
                channel_formatted_response=channel_response,
                error=None,
            )
        
        except asyncio.TimeoutError:
            raise
        
        except openai.error.RateLimitError as e:
            # Error Case 2: Rate limit with retry
            if retry_count < max_retries:
                retry_count += 1
                await asyncio.sleep(2)  # Wait 2 seconds
                continue
            else:
                raise


def _format_for_channel(response_text: str, channel: str) -> str:
    """Format AI response for specific channel requirements."""
    if channel == "voice":
        # Voice: enforce 2-sentence max
        sentences = re.split(r'(?<=[.!?])\s+', response_text)
        return ' '.join(sentences[:2])
    
    elif channel == "whatsapp":
        # WhatsApp: break long lines for mobile
        lines = response_text.split('\n')
        formatted_lines = []
        for line in lines:
            if len(line) > 80:
                # Smart wrap at word boundary
                words = line.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= 80:
                        current += word + " "
                    else:
                        if current:
                            formatted_lines.append(current.strip())
                        current = word + " "
                if current:
                    formatted_lines.append(current.strip())
            else:
                formatted_lines.append(line)
        return '\n'.join(formatted_lines)
    
    else:  # chat
        return response_text


def _detect_intent(message: str) -> str:
    """Detect customer intent from message."""
    message_lower = message.lower()
    
    intents = [
        ("service_cancellation", ["cancel", "stop", "quit", "terminate"]),
        ("billing_question", ["bill", "charge", "cost", "payment", "invoice"]),
        ("technical_issue", ["not working", "broken", "error", "issue", "problem", "slow", "down"]),
        ("account_inquiry", ["account", "profile", "settings", "information"]),
        ("complaint", ["complaint", "unhappy", "disappointed", "terrible", "awful"]),
        ("general_inquiry", ["help", "question", "how", "what", "when"]),
    ]
    
    for intent, keywords in intents:
        if any(keyword in message_lower for keyword in keywords):
            return intent
    
    return "general_inquiry"


# For backwards compatibility with imports that expect APIError
try:
    from anthropic import APIError
except ImportError:
    class APIError(Exception):
        pass


if __name__ == "__main__":
    # Example usage
    async def main():
        # Test with different messages
        test_messages = [
            ("I can't connect to the internet", "CUST001", "chat"),
            ("", "CUST002", "voice"),
            ("My bill is too high", "CUST003", "whatsapp"),
        ]
        
        for message, cust_id, channel in test_messages:
            print(f"\nTesting: '{message}' on {channel}")
            response = await handle_message(message, cust_id, channel)
            print(f"Response: {response.response_text}")
            print(f"Confidence: {response.confidence}")
            print(f"Error: {response.error}")
            print("-" * 50)
    
    asyncio.run(main())
