from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from app.db.database import connect_db, close_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router

from app.api.conversations import router as converstions_router


# curl -N \
#   -X POST \
#   http://127.0.0.1:8000/api/conversations/a7295f53-88c9-4b94-acf4-ac80f18e340f/ask \
#   -H "Content-Type: application/json" \
#   -d '{
#     "message": "My name is Raj."
#   }'
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(title="AI Chat Runtime", lifespan=lifespan)
# 1. Define the domains allowed to access your API
origins = [
    "http://localhost:3000",  # Common React/Next.js local port
    "http://localhost:5173",  # Common Vite/Vue local port
    "https://yourfrontend.com",  # Production domain
]

# 2. Add the CORS middleware to your FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Whitelist of domains
    allow_credentials=True,  # Allow cookies and authentication headers
    allow_methods=["*"],  # Allow all standard HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.get("/")
async def root():
    return "Hello World"


app.include_router(chat_router, prefix="/api")
app.include_router(
    converstions_router,
    prefix="/api",
)
