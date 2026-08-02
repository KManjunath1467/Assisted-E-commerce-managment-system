import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

app = FastAPI(title="GenAI Authentication API")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# ---------------------------------------------------------
# TEMPORARY USER DATABASE
# ---------------------------------------------------------

users_db = {
    "manjunath": {
        "username": "manjunath",
        "password": pwd_context.hash("password123"),
        "role": "user"
    },
    "admin": {
        "username": "admin",
        "password": pwd_context.hash("admin123"),
        "role": "admin"
    }
}

# ---------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class AIRequest(BaseModel):
    prompt: str
    max_tokens: int = 200


class AIResponse(BaseModel):
    response: str
    user: str


# ---------------------------------------------------------
# PASSWORD FUNCTIONS
# ---------------------------------------------------------

def verify_password(
    plain_password: str,
    hashed_password: str
):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def authenticate_user(
    username: str,
    password: str
):
    user = users_db.get(username)

    if not user:
        return None

    if not verify_password(
        password,
        user["password"]
    ):
        return None

    return user


# ---------------------------------------------------------
# JWT TOKEN CREATION
# ---------------------------------------------------------

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
):
    payload = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=15
        )

    payload.update({
        "exp": expire
    })

    encoded_token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_token


# ---------------------------------------------------------
# LOGIN ENDPOINT
# ---------------------------------------------------------

@app.post("/login")
def login(request: LoginRequest):

    user = authenticate_user(
        request.username,
        request.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"]
        },
        expires_delta=timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ---------------------------------------------------------
# GET CURRENT USER
# ---------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = users_db.get(username)

    if user is None:
        raise credentials_exception

    return user


# ---------------------------------------------------------
# GENAI SERVICE
# ---------------------------------------------------------

class GenAIService:

    def __init__(self):
        self.model_name = "local-llm"

    def generate_response(
        self,
        prompt: str,
        max_tokens: int
    ):

        # -------------------------------------------------
        # This is where the actual GenAI model is called.
        #
        # Example:
        #
        # response = client.chat.completions.create(...)
        #
        # or:
        #
        # requests.post("http://localhost:11434/api/generate")
        #
        # -------------------------------------------------

        generated_text = (
            "AI generated response for: "
            + prompt
        )

        return generated_text


genai_service = GenAIService()


# ---------------------------------------------------------
# PROTECTED GENAI ENDPOINT
# ---------------------------------------------------------

@app.post(
    "/ai/generate",
    response_model=AIResponse
)
def generate_ai_response(
    request: AIRequest,
    current_user: dict = Depends(get_current_user)
):

    # Authentication happens BEFORE this function
    # continues because of get_current_user().

    generated_response = (
        genai_service.generate_response(
            request.prompt,
            request.max_tokens
        )
    )

    return AIResponse(
        response=generated_response,
        user=current_user["username"]
    )


# ---------------------------------------------------------
# USER PROFILE
# ---------------------------------------------------------

@app.get("/profile")
def profile(
    current_user: dict = Depends(get_current_user)
):

    return {
        "username": current_user["username"],
        "role": current_user["role"]
    }


# ---------------------------------------------------------
# ADMIN ENDPOINT
# ---------------------------------------------------------

@app.get("/admin")
def admin_panel(
    current_user: dict = Depends(get_current_user)
):

    if current_user["role"] != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return {
        "message": "Welcome to admin panel"
    }


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/")
def home():

    return {
        "message": "GenAI Authentication API is running"
    }


# ---------------------------------------------------------
# APPLICATION START
# ---------------------------------------------------------

# Run using:
#
# uvicorn main:app --reload
#
# API:
#
# POST /login
# POST /ai/generate
# GET  /profile
# GET  /admin
#
# ---------------------------------------------------------
