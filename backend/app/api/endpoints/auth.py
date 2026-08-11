from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.user import User
from app.admin import verify_password

router = APIRouter()

class LoginRequest(BaseModel):
    username_or_email: str
    password: str

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    search_term = request.username_or_email.lower().strip()
    
    user = db.query(User).filter(
        (func.lower(User.username) == search_term) | (func.lower(User.email) == search_term)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
        
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
        
    # Return a simple token payload. For a production app this should be a real JWT.
    # We are returning the user ID as a simple token to authenticate the frontend.
    return {
        "success": True,
        "token": f"user_token_{user.id}",
        "user_id": user.id,
        "username": user.username
    }
