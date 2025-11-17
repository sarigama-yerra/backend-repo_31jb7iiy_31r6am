import os
import hashlib
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import create_document, get_documents, db
from schemas import User as UserSchema, BlogPost as BlogPostSchema, ContactMessage as ContactMessageSchema

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "SaaS Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# -----------------
# Auth Endpoints
# -----------------
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    name: Optional[str] = None
    email: EmailStr


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    # Check if user exists
    existing = get_documents("user", {"email": payload.email}, limit=1)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = UserSchema(
        name=payload.name,
        email=payload.email,
        password_hash=_hash_password(payload.password),
        is_active=True,
    )
    _id = create_document("user", user)
    token = str(uuid.uuid4())
    return AuthResponse(token=token, name=user.name, email=user.email)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    users = get_documents("user", {"email": payload.email}, limit=1)
    if not users:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_doc = users[0]
    if user_doc.get("password_hash") != _hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = str(uuid.uuid4())
    return AuthResponse(token=token, name=user_doc.get("name"), email=user_doc.get("email"))


# -----------------
# Blog Endpoints
# -----------------
class BlogItem(BaseModel):
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    tags: List[str] = []
    author: Optional[str] = None


@app.get("/api/blogs", response_model=List[BlogItem])
def list_blogs():
    docs = get_documents("blogpost", {}, limit=20)
    if not docs:
        # Seed a few demo posts if none exist
        samples = [
            BlogPostSchema(
                title="Launching our next‑gen platform",
                slug="launching-next-gen-platform",
                excerpt="How we built a blazing fast, secure, and scalable foundation.",
                content="We are excited to unveil our next‑gen SaaS platform...",
                tags=["announcement", "platform"],
                author="Team",
                published=True,
            ),
            BlogPostSchema(
                title="Designing with 3D: Tips & Tricks",
                slug="designing-with-3d",
                excerpt="Bring depth and motion into your product storytelling.",
                content="3D in the browser is more accessible than ever...",
                tags=["design", "3d"],
                author="Design",
                published=True,
            ),
            BlogPostSchema(
                title="Security best practices for startups",
                slug="security-best-practices",
                excerpt="Practical guidance to keep your users safe.",
                content="Security is a journey. In this post we cover...",
                tags=["security"],
                author="Security",
                published=True,
            ),
        ]
        for s in samples:
            create_document("blogpost", s)
        docs = get_documents("blogpost", {}, limit=20)

    # Map documents to response
    items: List[BlogItem] = []
    for d in docs:
        items.append(
            BlogItem(
                title=d.get("title"),
                slug=d.get("slug"),
                excerpt=d.get("excerpt"),
                content=d.get("content", ""),
                tags=d.get("tags", []),
                author=d.get("author"),
            )
        )
    return items


# -----------------
# Contact Endpoint
# -----------------
class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str

class ContactResponse(BaseModel):
    status: str


@app.post("/api/contact", response_model=ContactResponse)
def contact(payload: ContactRequest):
    msg = ContactMessageSchema(name=payload.name, email=payload.email, message=payload.message)
    create_document("contactmessage", msg)
    return ContactResponse(status="received")


# Optional: expose schemas for admin viewers
@app.get("/schema")
def get_schema_info():
    return {
        "collections": [
            {
                "name": "user",
                "fields": ["name", "email", "password_hash", "is_active"],
            },
            {
                "name": "blogpost",
                "fields": ["title", "slug", "excerpt", "content", "tags", "author", "published"],
            },
            {
                "name": "contactmessage",
                "fields": ["name", "email", "message"],
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
