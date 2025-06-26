from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from main.py
from main import (
    triage_agent,
    seat_booking_agent,
    flight_status_agent,
    cancellation_agent,
    create_initial_context,
    load_customer_context,
    AirlineAgentContext,
)

from agents import (
    Runner,
    ItemHelpers,
    MessageOutputItem,
    HandoffOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    InputGuardrailTripwireTriggered,
    Handoff,
    RunContextWrapper,
)

from database import db_client

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Models
# =========================

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    account_number: Optional[str] = None  # New field for customer identification

class MessageResponse(BaseModel):
    content: str
    agent: str

class AgentEvent(BaseModel):
    id: str
    type: str
    agent: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

class GuardrailCheck(BaseModel):
    id: str
    name: str
    input: str
    reasoning: str
    passed: bool
    timestamp: float

class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]
    agents: List[Dict[str, Any]]
    guardrails: List[GuardrailCheck] = []

# =========================
# In-memory store for conversation state (enhanced with Supabase persistence)
# =========================

class ConversationStore:
    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        pass

    def save(self, conversation_id: str, state: Dict[str, Any]):
        pass

class SupabaseConversationStore(ConversationStore):
    def __init__(self):
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    async def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        # Try memory cache first
        if conversation_id in self._memory_cache:
            return self._memory_cache[conversation_id]
        
        # Try database
        try:
            conversation = await db_client.load_conversation(conversation_id)
            if conversation:
                # Reconstruct the state format
                state = {
                    "input_items": conversation.get("history", []),
                    "context": AirlineAgentContext(**conversation.get("context", {})),
                    "current_agent": conversation.get("current_agent", "Triage Agent"),
                }
                self._memory_cache[conversation_id] = state
                return state
        except Exception as e:
            logger.error(f"Error loading conversation from database: {e}")
        
        return None

    async def save(self, conversation_id: str, state: Dict[str, Any]):
        # Save to memory cache
        self._memory_cache[conversation_id] = state
        
        # Save to database
        try:
            await db_client.save_conversation(
                session_id=conversation_id,
                history=state.get("input_items", []),
                context=state["context"].dict() if hasattr(state["context"], "dict") else state["context"],
                current_agent=state.get("current_agent", "Triage Agent")
            )
        except Exception as e:
            logger.error(f"Error saving conversation to database: {e}")

conversation_store = SupabaseConversationStore()

# =========================
# Helpers
# =========================

def get_agent_by_name(name: str):
    """Return the agent object by name."""
    agents = {
        triage_agent.name: triage_agent,
        seat_booking_agent.name: seat_booking_agent,
        flight_status_agent.name: flight_status_agent,
        cancellation_agent.name: cancellation_agent,
    }
    return agents.get(name, triage_agent)

def get_guardrail_name(g) -> str:
    """Extract a friendly guardrail name."""
    name_attr = getattr(g, "name", None)
    if isinstance(name_attr, str) and name_attr:
        return name_attr
    guard_fn = getattr(g, "guardrail_function", None)
    if guard_fn is not None and hasattr(guard_fn, "__name__"):
        return guard_fn.__name__.replace("_", " ").title()
    fn_name = getattr(g, "__name__", None)
    if isinstance(fn_name, str) and fn_name:
        return fn_name.replace("_", " ").title()
    return str(g)

def build_agents_list() -> List[Dict[str, Any]]:
    """Build a list of all available agents and their metadata."""
    def make_agent_dict(agent):
        return {
            "name": agent.name,
            "description": getattr(agent, "handoff_description", getattr(agent, "description", "")),
            "handoffs": [getattr(h, "agent_name", getattr(h, "name", "")) for h in getattr(agent, "handoffs", [])],
            "tools": [getattr(t, "name", getattr(t, "__name__", "")) for t in getattr(agent, "tools", [])],
            "input_guardrails": [get_guardrail_name(g) for g in getattr(agent, "input_guardrails", [])],
        }
    return [
        make_agent_dict(triage_agent),
        make_agent_dict(seat_booking_agent),
        make_agent_dict(flight_status_agent),
        make_agent_dict(cancellation_agent),
    ]

# =========================
# Main Chat Endpoint
# =========================

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Main chat endpoint for agent orchestration with Supabase integration.
    """
    try:
        logger.debug(f"Received request: {req}")
        
        # Initialize or retrieve conversation state
        is_new = not req.conversation_id or await conversation_store.get(req.conversation_id) is None
        
        if is_new:
            conversation_id = uuid4().hex
            
            # Load customer context if account number provided
            if req.account_number:
                ctx = await load_customer_context(req.account_number)
            else:
                ctx = create_initial_context()
            
            current_agent_name = triage_agent.name
            state = {
                "input_items": [],
                "context": ctx,
                "current_agent": current_agent_name,
            }
            
            if not req.message.strip():
                await conversation_store.save(conversation_id, state)
                return ChatResponse(
                    conversation_id=conversation_id,
                    current_agent=current_agent_name,
                    messages=[],
                    events=[],
                    context=ctx.dict(),
                    agents=build_agents_list(),
                    guardrails=[],
                )
        else:
            conversation_id = req.conversation_id  # type: ignore
            state = await conversation_store.get(conversation_id)
            if state is None:
                raise HTTPException(status_code=400, detail="Invalid conversation ID")

        current_agent = get_agent_by_name(state["current_agent"])
        state["input_items"].append({"content": req.message, "role": "user"})
        old_context = state["context"].dict().copy()
        guardrail_checks: List[GuardrailCheck] = []

        logger.debug(f"Running agent: {current_agent.name}, input_items: {state['input_items']}")
        context_wrapper = RunContextWrapper(context=state["context"])
        result = await Runner.run(
            current_agent,  # Agent as first argument
            state["input_items"],  # Input items as second argument
            context=context_wrapper  # Context as keyword argument
        )

        messages: List[MessageResponse] = []
        events: List[AgentEvent] = []

        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = ItemHelpers.text_message_output(item)
                messages.append(MessageResponse(content=text, agent=item.agent.name))
                events.append(AgentEvent(id=uuid4().hex, type="message", agent=item.agent.name, content=text))
            elif isinstance(item, HandoffOutputItem):
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="handoff",
                        agent=item.source_agent.name,
                        content=f"{item.source_agent.name} -> {item.target_agent.name}",
                        metadata={"source_agent": item.source_agent.name, "target_agent": item.target_agent.name},
                    )
                )
                ho = next((h for h in getattr(item.source_agent, "handoffs", []) if getattr(h, "agent_name", "") == item.target_agent.name), None)
                if ho and hasattr(ho, "on_invoke_handoff"):
                    fn = ho.on_invoke_handoff
                    cb_name = getattr(fn, "__name__", repr(fn))
                    events.append(AgentEvent(id=uuid4().hex, type="tool_call", agent=item.target_agent.name, content=cb_name))
                current_agent = item.target_agent
            elif isinstance(item, ToolCallItem):
                tool_name = getattr(item.raw_item, "name", "")
                raw_args = getattr(item.raw_item, "arguments", "")
                tool_args = raw_args if not isinstance(raw_args, str) else raw_args
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="tool_call",
                        agent=item.agent.name,
                        content=tool_name,
                        metadata={"tool_args": tool_args},
                    )
                )
                if tool_name == "display_seat_map":
                    messages.append(MessageResponse(content="DISPLAY_SEAT_MAP", agent=item.agent.name))
            elif isinstance(item, ToolCallOutputItem):
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="tool_output",
                        agent=item.agent.name,
                        content=str(item.output),
                        metadata={"tool_result": item.output},
                    )
                )

        new_context = state["context"].dict()
        changes = {k: new_context[k] for k in new_context if old_context.get(k) != new_context[k]}
        if changes:
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="context_update",
                    agent=current_agent.name,
                    content="",
                    metadata={"changes": changes},
                )
            )

        state["input_items"] = result.to_input_list()
        state["current_agent"] = current_agent.name
        await conversation_store.save(conversation_id, state)

        # Build guardrail results
        final_guardrails = [
            GuardrailCheck(
                id=uuid4().hex,
                name=get_guardrail_name(g),
                input=req.message,
                reasoning="",
                passed=True,
                timestamp=time.time() * 1000,
            )
            for g in current_agent.input_guardrails
        ]

        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=messages,
            events=events,
            context=new_context,
            agents=build_agents_list(),
            guardrails=final_guardrails,
        )

    except InputGuardrailTripwireTriggered as e:
        failed = e.guardrail_result.guardrail
        gr_input = req.message
        gr_timestamp = time.time() * 1000
        guardrail_checks = [
            GuardrailCheck(
                id=uuid4().hex,
                name=get_guardrail_name(g),
                input=gr_input,
                reasoning=(getattr(e.guardrail_result.output.output_info, "reasoning", "") if g == failed else ""),
                passed=(g != failed),
                timestamp=gr_timestamp,
            )
            for g in current_agent.input_guardrails
        ]
        refusal = "Sorry, I can only answer questions related to airline travel."
        state["input_items"].append({"role": "assistant", "content": refusal})
        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=[MessageResponse(content=refusal, agent=current_agent.name)],
            events=[],
            context=state["context"].dict(),
            agents=build_agents_list(),
            guardrails=guardrail_checks,
        )
    except Exception as e:
        logger.error(f"Unexpected error in chat_endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error. Please try again later.")

# =========================
# Additional Endpoints for Customer Management
# =========================

@app.get("/customer/{account_number}")
async def get_customer_info(account_number: str):
    """Get customer information and their bookings"""
    try:
        customer = await db_client.get_customer_by_account_number(account_number)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        bookings = await db_client.get_customer_bookings(account_number)
        
        return {
            "customer": customer,
            "bookings": bookings
        }
    except Exception as e:
        logger.error(f"Error fetching customer info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/booking/{confirmation_number}")
async def get_booking_info(confirmation_number: str):
    """Get booking information"""
    try:
        booking = await db_client.get_booking_by_confirmation(confirmation_number)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        return booking
    except Exception as e:
        logger.error(f"Error fetching booking info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")