from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.tag_registry import TagRegistry
import bcrypt

router = APIRouter()

class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str

class TagCreateRequest(BaseModel):
    device_id: str
    name: str
    breed: str = None
    location: str = None
    description: str = None

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"success": True, "users": [{"id": u.id, "username": u.username, "email": u.email, "is_active": u.is_active} for u in users]}

@router.post("/users")
def create_user(request: UserCreateRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter((User.username == request.username) | (User.email == request.email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    hashed_password = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"success": True, "message": "User created successfully"}

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"success": True, "message": "User deleted successfully"}

@router.post("/tags")
def create_tag(request: TagCreateRequest, db: Session = Depends(get_db)):
    existing_tag = db.query(TagRegistry).filter(TagRegistry.device_id == request.device_id).first()
    if existing_tag:
        raise HTTPException(status_code=400, detail="Device ID already registered")
    
    new_tag = TagRegistry(
        device_id=request.device_id,
        name=request.name,
        breed=request.breed,
        location=request.location,
        notes=request.description
    )
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)
    return {"success": True, "message": "Tag registered successfully"}

@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(TagRegistry).filter(TagRegistry.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return {"success": True, "message": "Tag deleted successfully"}
