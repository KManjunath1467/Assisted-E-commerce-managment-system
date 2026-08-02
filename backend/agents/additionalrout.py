import re
import logging
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("DesktopRouter")


# ============================================================
# STATE
# ============================================================

class AgentState(TypedDict, total=False):

    user_input: str

    normalized_input: str

    intent: str

    application: str

    confidence: float

    authenticated: bool

    authorized: bool

    action: str

    parameters: dict

    result: str

    response: str

    error: str


# ============================================================
# APPLICATION REGISTRY
# ============================================================

APPLICATIONS = {

    "browser": {
        "name": "Google Chrome",
        "keywords": [
            "browser",
            "chrome",
            "website",
            "web",
            "google",
            "search"
        ]
    },

    "vscode": {
        "name": "Visual Studio Code",
        "keywords": [
            "code",
            "coding",
            "python",
            "java",
            "program",
            "vscode",
            "visual studio"
        ]
    },

    "file_manager": {
        "name": "File Explorer",
        "keywords": [
            "file",
            "folder",
            "document",
            "directory",
            "pdf",
            "move",
            "copy",
            "delete"
        ]
    },

    "calculator": {
        "name": "Calculator",
        "keywords": [
            "calculate",
            "calculator",
            "addition",
            "multiply",
            "divide",
            "equation"
        ]
    },

    "terminal": {
        "name": "Terminal",
        "keywords": [
            "terminal",
            "command",
            "shell",
            "run command",
            "execute"
        ]
    },

    "spotify": {
        "name": "Spotify",
        "keywords": [
            "music",
            "song",
            "spotify",
            "play",
            "pause",
            "album"
        ]
    },

    "email": {
        "name": "Email",
        "keywords": [
            "email",
            "mail",
            "gmail",
            "send mail",
            "message"
        ]
    }
}


# ============================================================
# NODE 1
# INPUT NORMALIZATION
# ============================================================

def normalize_input(state: AgentState):

    text = state["user_input"]

    text = text.strip().lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    logger.info(
        "Normalized input: %s",
        text
    )

    return {
        "normalized_input": text
    }


# ============================================================
# NODE 2
# AUTHENTICATION
# ============================================================

def authenticate(state: AgentState):

    # Example of an offline authentication check.

    authenticated = True

    logger.info(
        "Authentication: %s",
        authenticated
    )

    return {
        "authenticated": authenticated
    }


# ============================================================
# NODE 3
# APPLICATION DETECTION
# ============================================================

def detect_application(state: AgentState):

    text = state[
        "normalized_input"
    ]

    scores = {}

    for application, details in APPLICATIONS.items():

        score = 0

        for keyword in details["keywords"]:

            if keyword in text:

                score += 1

        scores[application] = score


    if not scores:

        return {
            "application": "unknown",
            "confidence": 0.0
        }


    selected = max(
        scores,
        key=scores.get
    )

    highest_score = scores[selected]

    total_score = sum(
        scores.values()
    )

    if total_score == 0:

        confidence = 0.0

    else:

        confidence = (
            highest_score /
            total_score
        )


    logger.info(
        "Application=%s confidence=%.2f",
        selected,
        confidence
    )

    return {

        "application":
            selected,

        "confidence":
            confidence
    }


# ============================================================
# NODE 4
# INTENT CLASSIFICATION
# ============================================================

def classify_intent(state: AgentState):

    text = state[
        "normalized_input"
    ]

    intent = "unknown"

    if any(
        word in text
        for word in [
            "open",
            "launch",
            "start"
        ]
    ):

        intent = "open_application"

    elif any(
        word in text
        for word in [
            "close",
            "exit",
            "quit"
        ]
    ):

        intent = "close_application"

    elif any(
        word in text
        for word in [
            "search",
            "find"
        ]
    ):

        intent = "search"

    elif any(
        word in text
        for word in [
            "play",
            "pause"
        ]
    ):

        intent = "media_control"

    elif any(
        word in text
        for word in [
            "send",
            "write"
        ]
    ):

        intent = "communication"

    elif any(
        word in text
        for word in [
            "calculate",
            "compute"
        ]
    ):

        intent = "calculation"

    elif any(
        word in text
        for word in [
            "run",
            "execute"
        ]
    ):

        intent = "command_execution"

    elif any(
        word in text
        for word in [
            "open file",
            "find file",
            "delete file",
            "move file"
        ]
    ):

        intent = "file_operation"


    logger.info(
        "Detected intent: %s",
        intent
    )

    return {
        "intent": intent
    }


# ============================================================
# NODE 5
# AUTHORIZATION
# ============================================================

def authorize(state: AgentState):

    if not state.get(
        "authenticated",
        False
    ):

        return {
            "authorized": False
        }


    restricted_intents = {

        "command_execution",

        "file_operation",

        "communication"
    }


    intent = state.get(
        "intent",
        "unknown"
    )


    if intent in restricted_intents:

        # Additional authorization could be
        # performed here.

        authorized = True

    else:

        authorized = True


    logger.info(
        "Authorization: %s",
        authorized
    )

    return {
        "authorized": authorized
    }


# ============================================================
# NODE 6
# EXTRACT ACTION PARAMETERS
# ============================================================

def extract_parameters(
    state: AgentState
):

    text = state[
        "normalized_input"
    ]

    application = state[
        "application"
    ]

    parameters = {}


    if application == "browser":

        match = re.search(
            r"(?:search|google)\s+(.+)",
            text
        )

        if match:

            parameters["query"] = (
                match.group(1)
            )


    elif application == "file_manager":

        match = re.search(
            r"(?:find|open)\s+(?:file\s+)?(.+)",
            text
        )

        if match:

            parameters["filename"] = (
                match.group(1)
            )


    elif application == "spotify":

        match = re.search(
            r"play\s+(.+)",
            text
        )

        if match:

            parameters["song"] = (
                match.group(1)
            )


    elif application == "vscode":

        match = re.search(
            r"(?:open|edit)\s+(.+)",
            text
        )

        if match:

            parameters["project"] = (
                match.group(1)
            )


    elif application == "email":

        match = re.search(
            r"send\s+(?:an\s+)?email\s+to\s+(.+)",
            text
        )

        if match:

            parameters["recipient"] = (
                match.group(1)
            )


    logger.info(
        "Extracted parameters: %s",
        parameters
    )

    return {
        "parameters": parameters
    }


# ============================================================
# ROUTER
# ============================================================

def application_router(
    state: AgentState
) -> str:

    application = state.get(
        "application",
        "unknown"
    )

    confidence = state.get(
        "confidence",
        0.0
    )


    if confidence < 0.25:

        return "fallback"


    routes = {

        "browser":
            "browser",

        "vscode":
            "vscode",

        "file_manager":
            "file_manager",

        "calculator":
            "calculator",

        "terminal":
            "terminal",

        "spotify":
            "spotify",

        "email":
            "email"
    }


    return routes.get(
        application,
        "fallback"
    )


# ============================================================
# APPLICATION NODE: BROWSER
# ============================================================

def browser_node(
    state: AgentState
):

    query = state.get(
        "parameters",
        {}
    ).get(
        "query"
    )

    if query:

        result = (
            f"Opening Chrome and "
            f"searching for '{query}'"
        )

    else:

        result = (
            "Opening Google Chrome"
        )

    logger.info(
        "Browser action executed"
    )

    return {
        "result": result
    }


# ============================================================
# APPLICATION NODE: VSCODE
# ============================================================

def vscode_node(
    state: AgentState
):

    project = state.get(
        "parameters",
        {}
    ).get(
        "project"
    )

    if project:

        result = (
            f"Opening project '{project}' "
            f"in Visual Studio Code"
        )

    else:

        result = (
            "Opening Visual Studio Code"
        )

    return {
        "result": result
    }


# ============================================================
# APPLICATION NODE: FILE MANAGER
# ============================================================

def file_manager_node(
    state: AgentState
):

    filename = state.get(
        "parameters",
        {}
    ).get(
        "filename"
    )

    if filename:

        result = (
            f"Searching File Explorer "
            f"for '{filename}'"
        )

    else:

        result = (
            "Opening File Explorer"
        )

    return {
        "result": result
    }


# ============================================================
# APPLICATION NODE: CALCULATOR
# ============================================================

def calculator_node(
    state: AgentState
):

    text = state[
        "normalized_input"
    ]

    result = (
        f"Calculator launched "
        f"for expression: {text}"
    )

    return {
        "result": result
    }


# ============================================================
# APPLICATION NODE: TERMINAL
# ============================================================

def terminal_node(
    state: AgentState
):

    text = state[
        "normalized_input"
    ]

    result = (
        f"Terminal command requested: {text}"
    )

    return {
        "result": result
    }


# ============================================================
# APPLICATION NODE: SPOTIFY
# ============================================================

def spotify_node(
    state: AgentState
):

    song = state.get(
        "parameters",
        {}
    ).get(
        "song"
    )

    if song:

        result = (
            f"Opening Spotify and "
            f"playing '{song}'"
        )

    else:

        result = (
            "Opening Spotify"
        )

    return {
        "result": result
    }


# ============================================================
# APPLICATION NODE: EMAIL
# ============================================================

def email_node(
    state: AgentState
):

    recipient = state.get(
        "parameters",
        {}
    ).get(
        "recipient"
    )

    if recipient:

        result = (
            f"Preparing email for "
            f"{recipient}"
        )

    else:

        result = (
            "Opening email application"
        )

    return {
        "result": result
    }


# ============================================================
# FALLBACK NODE
# ============================================================

def fallback_node(
    state: AgentState
):

    logger.warning(
        "No suitable application detected"
    )

    return {
        "result":
            "I could not determine which "
            "application should handle this request."
    }


# ============================================================
# FINAL RESPONSE NODE
# ============================================================

def response_node(
    state: AgentState
):

    result = state.get(
        "result",
        ""
    )

    application = state.get(
        "application",
        "unknown"
    )

    response = (
        f"Application selected: "
        f"{application}\n"
        f"Result: {result}"
    )

    return {
        "response": response
    }


# ============================================================
# BLOCKED NODE
# ============================================================

def blocked_node(
    state: AgentState
):

    return {
        "response":
            "Request rejected because "
            "authentication or authorization failed."
    }


# ============================================================
# AUTHENTICATION ROUTER
# ============================================================

def authentication_router(
    state: AgentState
) -> Literal[
    "classify",
    "blocked"
]:

    if state.get(
        "authenticated",
        False
    ):

        return "classify"

    return "blocked"


# ============================================================
# AUTHORIZATION ROUTER
# ============================================================

def authorization_router(
    state: AgentState
) -> Literal[
    "parameters",
    "blocked"
]:

    if state.get(
        "authorized",
        False
    ):

        return "parameters"

    return "blocked"


# ============================================================
# BUILD GRAPH
# ============================================================

builder = StateGraph(
    AgentState
)


# ============================================================
# REGISTER NODES
# ============================================================

builder.add_node(
    "normalize",
    normalize_input
)

builder.add_node(
    "authenticate",
    authenticate
)

builder.add_node(
    "classify",
    classify_intent
)

builder.add_node(
    "detect_application",
    detect_application
)

builder.add_node(
    "authorize",
    authorize
)

builder.add_node(
    "parameters",
    extract_parameters
)

builder.add_node(
    "browser",
    browser_node
)

builder.add_node(
    "vscode",
    vscode_node
)

builder.add_node(
    "file_manager",
    file_manager_node
)

builder.add_node(
    "calculator",
    calculator_node
)

builder.add_node(
    "terminal",
    terminal_node
)

builder.add_node(
    "spotify",
    spotify_node
)

builder.add_node(
    "email",
    email_node
)

builder.add_node(
    "fallback",
    fallback_node
)

builder.add_node(
    "blocked",
    blocked_node
)

builder.add_node(
    "response",
    response_node
)


# ============================================================
# GRAPH EDGES
# ============================================================

builder.add_edge(
    START,
    "normalize"
)

builder.add_edge(
    "normalize",
    "authenticate"
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
    "detect_application"
)

builder.add_edge(
    "detect_application",
    "authorize"
)


# ============================================================
# AUTHORIZATION ROUTING
# ============================================================

builder.add_conditional_edges(

    "authorize",

    authorization_router,

    {
        "parameters":
            "parameters",

        "blocked":
            "blocked"
    }
)


# ============================================================
# APPLICATION ROUTING
# ============================================================

builder.add_conditional_edges(

    "parameters",

    application_router,

    {
        "browser":
            "browser",

        "vscode":
            "vscode",

        "file_manager":
            "file_manager",

        "calculator":
            "calculator",

        "terminal":
            "terminal",

        "spotify":
            "spotify",

        "email":
            "email",

        "fallback":
            "fallback"
    }
)


# ============================================================
# APPLICATION NODES → RESPONSE
# ============================================================

builder.add_edge(
    "browser",
    "response"
)

builder.add_edge(
    "vscode",
    "response"
)

builder.add_edge(
    "file_manager",
    "response"
)

builder.add_edge(
    "calculator",
    "response"
)

builder.add_edge(
    "terminal",
    "response"
)

builder.add_edge(
    "spotify",
    "response"
)

builder.add_edge(
    "email",
    "response"
)

builder.add_edge(
    "fallback",
    "response"
)


# ============================================================
# TERMINATION
# ============================================================

builder.add_edge(
    "response",
    END
)

builder.add_edge(
    "blocked",
    END
)


# ============================================================
# COMPILE
# ============================================================

agent = builder.compile()


# ============================================================
# EXECUTION FUNCTION
# ============================================================

def run_agent(
    user_input: str
):

    initial_state = {

        "user_input":
            user_input,

        "authenticated":
            False,

        "authorized":
            False,

        "confidence":
            0.0,

        "parameters":
            {}
    }


    result = agent.invoke(
        initial_state
    )


    return result


# ============================================================
# TEST CASES
# ============================================================

if __name__ == "__main__":

    commands = [

        "open chrome",

        "search google for LangGraph",

        "open my Python project",

        "find my resume.pdf",

        "calculate 25 multiplied by 4",

        "open terminal",

        "play Believer",

        "send an email to John",

        "open something unknown"
    ]


    for command in commands:

        print("\n" + "=" * 70)

        print(
            "USER:",
            command
        )

        result = run_agent(
            command
        )

        print(
            "AGENT:",
            result.get(
                "response"
            )
        )
