from typing import TypedDict
from langgraph.graph import StateGraph, START, END


# -----------------------------------------
# 1. Define the state
# -----------------------------------------

class AgentState(TypedDict):
    message: str
    result: str


# -----------------------------------------
# 2. Create nodes
# -----------------------------------------

def input_node(state: AgentState):
    print("Input node running...")

    return {
        "message": state["message"]
    }


def process_node(state: AgentState):
    print("Processing node running...")

    message = state["message"]

    result = message.upper()

    return {
        "result": result
    }


def output_node(state: AgentState):
    print("Output node running...")

    print("Final result:", state["result"])

    return state


# -----------------------------------------
# 3. Create the graph
# -----------------------------------------

graph = StateGraph(AgentState)


# -----------------------------------------
# 4. Add nodes
# -----------------------------------------

graph.add_node(
    "input",
    input_node
)

graph.add_node(
    "process",
    process_node
)

graph.add_node(
    "output",
    output_node
)


# -----------------------------------------
# 5. Add edges
# -----------------------------------------

graph.add_edge(
    START,
    "input"
)

graph.add_edge(
    "input",
    "process"
)

graph.add_edge(import os
import re
import uuid
import logging
from typing import TypedDict, Literal, Annotated
from datetime import datetime

from langgraph.graph import (
    StateGraph,
    START,
    END
)

from langgraph.checkpoint.memory import MemorySaver


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("OfflineAgent")


# ============================================================
# AGENT STATE
# ============================================================

class AgentState(TypedDict, total=False):

    session_id: str

    user_id: str

    user_input: str

    normalized_input: str

    intent: str

    confidence: float

    authentication_status: bool

    authorization_status: bool

    injection_detected: bool

    risk_score: int

    selected_tool: str

    tool_result: str

    llm_response: str

    final_response: str

    error: str

    retry_count: int

    execution_time: float


# ============================================================
# SECURITY CONFIGURATION
# ============================================================

SUSPICIOUS_PATTERNS = [

    r"ignore\s+previous\s+instructions",

    r"ignore\s+all\s+instructions",

    r"reveal\s+system\s+prompt",

    r"show\s+your\s+instructions",

    r"bypass\s+authentication",

    r"disable\s+security",

    r"override\s+system",

    r"developer\s+message",

    r"<system>",

    r"<developer>",

    r"jailbreak"
]


# ============================================================
# NODE 1: INPUT PREPROCESSING
# ============================================================

def preprocess_input(state: AgentState):

    start = datetime.now()

    user_input = state.get(
        "user_input",
        ""
    )

    normalized = user_input.strip()

    normalized = re.sub(
        r"\s+",
        " ",
        normalized
    )

    normalized = normalized.lower()

    logger.info(
        "Input preprocessing completed"
    )

    return {
        "normalized_input": normalized,
        "execution_time":
            (datetime.now() - start).total_seconds()
    }


# ============================================================
# NODE 2: PROMPT INJECTION DETECTION
# ============================================================

def security_scan(state: AgentState):

    text = state.get(
        "normalized_input",
        ""
    )

    risk_score = 0

    matched_patterns = []

    for pattern in SUSPICIOUS_PATTERNS:

        if re.search(pattern, text):

            risk_score += 20

            matched_patterns.append(
                pattern
            )

    risk_score = min(
        risk_score,
        100
    )

    injection_detected = (
        risk_score >= 40
    )

    logger.info(
        "Security scan score=%s",
        risk_score
    )

    return {
        "risk_score": risk_score,
        "injection_detected":
            injection_detected
    }


# ============================================================
# NODE 3: AUTHENTICATION
# ============================================================

def authenticate_user(state: AgentState):

    user_id = state.get(
        "user_id"
    )

    session_id = state.get(
        "session_id"
    )

    authenticated = (
        user_id is not None
        and session_id is not None
    )

    logger.info(
        "Authentication status=%s",
        authenticated
    )

    return {
        "authentication_status":
            authenticated
    }


# ============================================================
# NODE 4: INTENT CLASSIFICATION
# ============================================================

def classify_intent(state: AgentState):

    text = state.get(
        "normalized_input",
        ""
    )

    intent = "unknown"
    confidence = 0.50

    if any(
        word in text
        for word in [
            "open",
            "find",
            "file",
            "document"
        ]
    ):

        intent = "file_operation"
        confidence = 0.91

    elif any(
        word in text
        for word in [
            "calculate",
            "compute",
            "math"
        ]
    ):

        intent = "calculation"
        confidence = 0.94

    elif any(
        word in text
        for word in [
            "remember",
            "memory",
            "recall"
        ]
    ):

        intent = "memory"
        confidence = 0.87

    elif any(
        word in text
        for word in [
            "search",
            "lookup"
        ]
    ):

        intent = "search"
        confidence = 0.89

    elif any(
        word in text
        for word in [
            "hello",
            "hi",
            "hey"
        ]
    ):

        intent = "conversation"
        confidence = 0.98

    logger.info(
        "Intent=%s confidence=%s",
        intent,
        confidence
    )

    return {
        "intent": intent,
        "confidence": confidence
    }


# ============================================================
# NODE 5: AUTHORIZATION
# ============================================================

def authorize_request(state: AgentState):

    intent = state.get(
        "intent",
        "unknown"
    )

    authenticated = state.get(
        "authentication_status",
        False
    )

    if not authenticated:

        return {
            "authorization_status": False
        }

    restricted_operations = {
        "file_operation"
    }

    if intent in restricted_operations:

        logger.info(
            "Restricted operation requested"
        )

        return {
            "authorization_status": True
        }

    return {
        "authorization_status": True
    }


# ============================================================
# NODE 6: TOOL SELECTION
# ============================================================

def select_tool(state: AgentState):

    intent = state.get(
        "intent",
        "unknown"
    )

    tool_map = {

        "file_operation":
            "file_manager",

        "calculation":
            "calculator",

        "memory":
            "memory_engine",

        "search":
            "local_search",

        "conversation":
            "llm",

        "unknown":
            "fallback"
    }

    selected_tool = tool_map.get(
        intent,
        "fallback"
    )

    logger.info(
        "Selected tool=%s",
        selected_tool
    )

    return {
        "selected_tool": selected_tool
    }


# ============================================================
# NODE 7: FILE TOOL
# ============================================================

def file_tool(state: AgentState):

    query = state.get(
        "normalized_input",
        ""
    )

    logger.info(
        "Executing file tool"
    )

    return {
        "tool_result":
            f"File search executed for: {query}"
    }


# ============================================================
# NODE 8: CALCULATOR TOOL
# ============================================================

def calculator_tool(state: AgentState):

    logger.info(
        "Executing calculator"
    )

    return {
        "tool_result":
            "Calculation completed locally."
    }


# ============================================================
# NODE 9: MEMORY TOOL
# ============================================================

def memory_tool(state: AgentState):

    logger.info(
        "Executing memory engine"
    )

    return {
        "tool_result":
            "Memory operation completed."
    }


# ============================================================
# NODE 10: LOCAL SEARCH
# ============================================================

def local_search_tool(state: AgentState):

    query = state.get(
        "normalized_input",
        ""
    )

    return {
        "tool_result":
            f"Local search performed for: {query}"
    }


# ============================================================
# NODE 11: LLM PROCESSING
# ============================================================

def llm_node(state: AgentState):

    user_input = state.get(
        "user_input",
        ""
    )

    logger.info(
        "Sending request to local LLM"
    )

    # Replace this section with Ollama,
    # llama.cpp, or another local model.

    response = (
        "Local LLM response generated for: "
        + user_input
    )

    return {
        "llm_response": response
    }


# ============================================================
# NODE 12: TOOL RESULT PROCESSOR
# ============================================================

def process_tool_result(state: AgentState):

    result = state.get(
        "tool_result",
        ""
    )

    if not result:

        return {
            "error":
                "Tool returned empty result"
        }

    return {
        "llm_response":
            f"Processed tool result: {result}"
    }


# ============================================================
# NODE 13: FINAL RESPONSE
# ============================================================

def generate_final_response(state: AgentState):

    if state.get("error"):

        return {
            "final_response":
                "An error occurred while processing the request."
        }

    response = state.get(
        "llm_response",
        ""
    )

    if not response:

        response = (
            state.get(
                "tool_result",
                "No response generated."
            )
        )

    return {
        "final_response": response
    }


# ============================================================
# ROUTER: SECURITY
# ============================================================

def security_router(
    state: AgentState
) -> Literal[
    "blocked",
    "authenticate"
]:

    if state.get(
        "injection_detected",
        False
    ):

        return "blocked"

    return "authenticate"


# ============================================================
# NODE: BLOCK REQUEST
# ============================================================

def blocked_node(state: AgentState):

    logger.warning(
        "Potential prompt injection blocked"
    )

    return {
        "final_response":
            "Request blocked by security policy."
    }


# ============================================================
# ROUTER: AUTHENTICATION
# ============================================================

def authentication_router(
    state: AgentState
) -> Literal[
    "classify",
    "blocked"
]:

    if state.get(
        "authentication_status",
        False
    ):

        return "classify"

    return "blocked"


# ============================================================
# ROUTER: AUTHORIZATION
# ============================================================

def authorization_router(
    state: AgentState
) -> Literal[
    "tool_selection",
    "blocked"
]:

    if state.get(
        "authorization_status",
        False
    ):

        return "tool_selection"

    return "blocked"


# ============================================================
# ROUTER: TOOL
# ============================================================

def tool_router(
    state: AgentState
) -> str:

    tool = state.get(
        "selected_tool",
        "fallback"
    )

    routes = {

        "file_manager":
            "file_tool",

        "calculator":
            "calculator_tool",

        "memory_engine":
            "memory_tool",

        "local_search":
            "search_tool",

        "llm":
            "llm",

        "fallback":
            "llm"
    }

    return routes.get(
        tool,
        "llm"
    )


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(
    AgentState
)


# ============================================================
# REGISTER NODES
# ============================================================

builder.add_node(
    "preprocess",
    preprocess_input
)

builder.add_node(
    "security_scan",
    security_scan
)

builder.add_node(
    "authenticate",
    authenticate_user
)

builder.add_node(
    "classify",
    classify_intent
)

builder.add_node(
    "authorize",
    authorize_request
)

builder.add_node(
    "tool_selection",
    select_tool
)

builder.add_node(
    "file_tool",
    file_tool
)

builder.add_node(
    "calculator_tool",
    calculator_tool
)

builder.add_node(
    "memory_tool",
    memory_tool
)

builder.add_node(
    "search_tool",
    local_search_tool
)

builder.add_node(
    "llm",
    llm_node
)

builder.add_node(
    "process_tool",
    process_tool_result
)

builder.add_node(
    "blocked",
    blocked_node
)

builder.add_node(
    "final_response",
    generate_final_response
)


# ============================================================
# START → PREPROCESS
# ============================================================

builder.add_edge(
    START,
    "preprocess"
)


# ============================================================
# PREPROCESS → SECURITY
# ============================================================

builder.add_edge(
    "preprocess",
    "security_scan"
)


# ============================================================
# SECURITY CONDITIONAL ROUTING
# ============================================================

builder.add_conditional_edges(

    "security_scan",

    security_router,

    {
        "blocked":
            "blocked",

        "authenticate":
            "authenticate"
    }
)


# ============================================================
# AUTHENTICATION ROUTING
# ============================================================

builder.add_conditional_edges(

    "authenticate",

    authentication_router,

    {
        "classify":
            "classify",

        "blocked":
            "blocked"
    }
)


# ============================================================
# CLASSIFICATION
# ============================================================

builder.add_edge(
    "classify",
    "authorize"
)


# ============================================================
# AUTHORIZATION
# ============================================================

builder.add_conditional_edges(

    "authorize",

    authorization_router,

    {
        "tool_selection":
            "tool_selection",

        "blocked":
            "blocked"
    }
)


# ============================================================
# TOOL SELECTION
# ============================================================

builder.add_conditional_edges(

    "tool_selection",

    tool_router,

    {
        "file_tool":
            "file_tool",

        "calculator_tool":
            "calculator_tool",

        "memory_tool":
            "memory_tool",

        "search_tool":
            "search_tool",

        "llm":
            "llm"
    }
)


# ============================================================
# TOOL NODES → RESULT PROCESSOR
# ============================================================

builder.add_edge(
    "file_tool",
    "process_tool"
)

builder.add_edge(
    "calculator_tool",
    "process_tool"
)

builder.add_edge(
    "memory_tool",
    "process_tool"
)

builder.add_edge(
    "search_tool",
    "process_tool"
)


# ============================================================
# LLM → FINAL RESPONSE
# ============================================================

builder.add_edge(
    "llm",
    "final_response"
)


# ============================================================
# TOOL RESULT → FINAL RESPONSE
# ============================================================

builder.add_edge(
    "process_tool",
    "final_response"
)


# ============================================================
# BLOCKED → END
# ============================================================

builder.add_edge(
    "blocked",
    END
)


# ============================================================
# FINAL RESPONSE → END
# ============================================================

builder.add_edge(
    "final_response",
    END
)


# ============================================================
# CHECKPOINT / MEMORY
# ============================================================

memory = MemorySaver()


app = builder.compile(
    checkpointer=memory
)


# ============================================================
# EXECUTION FUNCTION
# ============================================================

def run_agent(
    user_input: str,
    user_id: str
):

    session_id = str(
        uuid.uuid4()
    )

    initial_state = {

        "session_id":
            session_id,

        "user_id":
            user_id,

        "user_input":
            user_input,

        "retry_count":
            0
    }

    config = {

        "configurable": {

            "thread_id":
                session_id
        }
    }

    result = app.invoke(
        initial_state,
        config=config
    )

    return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    result = run_agent(
        "Find my project file",
        "user_001"
    )

    print("\n==============================")
    print("FINAL RESPONSE")
    print("==============================")

    print(
        result.get(
            "final_response"
        )
    )
    "process",
    "output"
)

graph.add_edge(
    "output",
    END
)




app = graph.compile()



result = app.invoke({
    "message": "hello langgraph",
    "result": ""
})

print("\nFinal state:")
print(result)
