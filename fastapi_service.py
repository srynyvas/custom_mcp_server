#!/usr/bin/env python3
"""
FastAPI microservice for testing MCP API Server
This creates various endpoints that demonstrate different API patterns
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import json
from datetime import datetime
import uuid

# Initialize FastAPI app
app = FastAPI(
    title="MCP Test API",
    description="FastAPI microservice for testing MCP API Server integration",
    version="1.0.0"
)

# Security scheme for Bearer token
security = HTTPBearer()

# Sample data
USERS_DB = {
    "1": {"id": "1", "name": "John Doe", "email": "john@example.com", "role": "admin"},
    "2": {"id": "2", "name": "Jane Smith", "email": "jane@example.com", "role": "user"},
    "3": {"id": "3", "name": "Bob Johnson", "email": "bob@example.com", "role": "user"},
}

POSTS_DB = {
    "1": {"id": "1", "title": "First Post", "content": "This is the first post", "author_id": "1"},
    "2": {"id": "2", "title": "Second Post", "content": "This is the second post", "author_id": "2"},
    "3": {"id": "3", "title": "Third Post", "content": "This is the third post", "author_id": "1"},
}


# Pydantic models
class User(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    role: str = "user"


class Post(BaseModel):
    id: Optional[str] = None
    title: str
    content: str
    author_id: str


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class StatusResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# Authentication functions
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Bearer token"""
    valid_tokens = ["test-token-123", "admin-token-456", "user-token-789"]
    if credentials.credentials not in valid_tokens:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key"""
    valid_keys = ["test-api-key-456", "secret-key-123"]
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "MCP Test API Service",
        "version": "1.0.0",
        "endpoints": [
            "/users",
            "/posts",
            "/status",
            "/health",
            "/echo"
        ]
    }


# Health check
@app.get("/health", response_model=StatusResponse)
async def health_check():
    """Health check endpoint"""
    return StatusResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


# Status endpoint with query parameters
@app.get("/status")
async def get_status(
        include_stats: bool = Query(False, description="Include system statistics"),
        format: str = Query("json", description="Response format")
):
    """Get system status with optional parameters"""
    response = {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "uptime": "5 minutes",
    }

    if include_stats:
        response["stats"] = {
            "users_count": len(USERS_DB),
            "posts_count": len(POSTS_DB),
            "memory_usage": "45MB"
        }

    if format == "xml":
        # Simple XML response
        return {"xml": "<status>running</status>"}

    return response


# Echo endpoint for testing request data
@app.post("/echo")
async def echo_request(data: Dict[str, Any]):
    """Echo back the request data"""
    return {
        "echo": data,
        "received_at": datetime.now().isoformat(),
        "request_id": str(uuid.uuid4())
    }


# User endpoints
@app.get("/users", response_model=List[Dict])
async def get_users(
        limit: int = Query(10, description="Maximum number of users to return"),
        role: Optional[str] = Query(None, description="Filter by role")
):
    """Get list of users with optional filtering"""
    users = list(USERS_DB.values())

    if role:
        users = [u for u in users if u["role"] == role]

    return users[:limit]


@app.get("/users/{user_id}")
async def get_user(user_id: str = Path(..., description="User ID")):
    """Get user by ID"""
    if user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")
    return USERS_DB[user_id]


@app.post("/users", response_model=ApiResponse)
async def create_user(user: User):
    """Create a new user"""
    user.id = str(len(USERS_DB) + 1)
    USERS_DB[user.id] = user.dict()

    return ApiResponse(
        success=True,
        message="User created successfully",
        data=user.dict()
    )


@app.put("/users/{user_id}", response_model=ApiResponse)
async def update_user(user_id: str, user: User):
    """Update user by ID"""
    if user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")

    user.id = user_id
    USERS_DB[user_id] = user.dict()

    return ApiResponse(
        success=True,
        message="User updated successfully",
        data=user.dict()
    )


@app.delete("/users/{user_id}", response_model=ApiResponse)
async def delete_user(user_id: str):
    """Delete user by ID"""
    if user_id not in USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")

    deleted_user = USERS_DB.pop(user_id)

    return ApiResponse(
        success=True,
        message="User deleted successfully",
        data=deleted_user
    )


# Posts endpoints
@app.get("/posts")
async def get_posts(
        author_id: Optional[str] = Query(None, description="Filter by author ID"),
        limit: int = Query(10, description="Maximum number of posts")
):
    """Get list of posts"""
    posts = list(POSTS_DB.values())

    if author_id:
        posts = [p for p in posts if p["author_id"] == author_id]

    return posts[:limit]


@app.get("/posts/{post_id}")
async def get_post(post_id: str):
    """Get post by ID"""
    if post_id not in POSTS_DB:
        raise HTTPException(status_code=404, detail="Post not found")
    return POSTS_DB[post_id]


@app.post("/posts", response_model=ApiResponse)
async def create_post(post: Post):
    """Create a new post"""
    post.id = str(len(POSTS_DB) + 1)
    POSTS_DB[post.id] = post.dict()

    return ApiResponse(
        success=True,
        message="Post created successfully",
        data=post.dict()
    )


# Secured endpoints (require authentication)
@app.get("/secure/profile")
async def get_secure_profile(token: str = Depends(verify_token)):
    """Get user profile (requires Bearer token)"""
    return {
        "user": "authenticated_user",
        "token": token[:10] + "...",
        "permissions": ["read", "write"],
        "accessed_at": datetime.now().isoformat()
    }


@app.get("/secure/admin")
async def get_admin_data(token: str = Depends(verify_token)):
    """Get admin data (requires Bearer token)"""
    if not token.startswith("admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "admin_data": "sensitive information",
        "system_stats": {
            "active_users": 42,
            "total_requests": 1337,
            "system_load": "low"
        }
    }


@app.get("/api/protected")
async def get_protected_data(api_key: str = Depends(verify_api_key)):
    """Get protected data (requires API key)"""
    return {
        "protected_data": "secret information",
        "api_key": api_key[:8] + "...",
        "access_level": "premium"
    }


# Testing endpoints for different scenarios
@app.get("/test/error")
async def test_error():
    """Endpoint that returns an error (for testing error handling)"""
    raise HTTPException(status_code=500, detail="This is a test error")


@app.get("/test/slow")
async def test_slow_response():
    """Slow endpoint for testing timeouts"""
    import asyncio
    await asyncio.sleep(2)  # 2 second delay
    return {"message": "This response was delayed by 2 seconds"}


@app.post("/test/webhook")
async def test_webhook(payload: Dict[str, Any]):
    """Webhook endpoint for testing POST with complex data"""
    return {
        "received": payload,
        "processed_at": datetime.now().isoformat(),
        "webhook_id": str(uuid.uuid4()),
        "status": "processed"
    }


# Complex endpoint with multiple parameters
@app.get("/api/search")
async def search_data(
        query: str = Query(..., description="Search query"),
        category: Optional[str] = Query(None, description="Category filter"),
        page: int = Query(1, description="Page number", ge=1),
        per_page: int = Query(10, description="Items per page", ge=1, le=100),
        sort_by: str = Query("created", description="Sort field"),
        sort_order: str = Query("desc", description="Sort order", regex="^(asc|desc)$")
):
    """Complex search endpoint with multiple parameters"""

    # Simulate search results
    results = [
        {"id": i, "title": f"Result {i}", "category": category or "general", "score": 0.9 - (i * 0.1)}
        for i in range(1, per_page + 1)
    ]

    return {
        "query": query,
        "filters": {
            "category": category,
            "sort_by": sort_by,
            "sort_order": sort_order
        },
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_results": 100,
            "total_pages": 10
        },
        "results": results
    }


if __name__ == "__main__":
    print("🚀 Starting FastAPI Test Service...")
    print("📋 Available endpoints:")
    print("   - GET  /health           - Health check")
    print("   - GET  /users            - Get users list")
    print("   - GET  /users/{id}       - Get user by ID")
    print("   - POST /users            - Create user")
    print("   - GET  /posts            - Get posts list")
    print("   - POST /echo             - Echo request data")
    print("   - GET  /secure/profile   - Secured endpoint (Bearer token)")
    print("   - GET  /api/protected    - API key protected endpoint")
    print("   - GET  /api/search       - Complex search endpoint")
    print("   - GET  /test/error       - Error testing endpoint")
    print("")
    print("🔧 Test credentials:")
    print("   Bearer tokens: test-token-123, admin-token-456")
    print("   API keys: test-api-key-456, secret-key-123")
    print("")
    print("🌐 Service will be available at: http://localhost:8000")

    uvicorn.run(
        "fastapi_service:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
