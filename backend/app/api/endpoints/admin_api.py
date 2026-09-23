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

from typing import Optional

class TagCreateRequest(BaseModel):
    device_id: str
    name: str
    breed: Optional[str] = None
    location: Optional[str] = None
    weight: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None

class TagUpdateRequest(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    location: Optional[str] = None
    weight: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None

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

@router.get("/tags")
def get_tags(db: Session = Depends(get_db)):
    """Fetch all registered cow tags/devices from TagRegistry."""
    tags = db.query(TagRegistry).order_by(TagRegistry.id.asc()).all()
    items = []
    for t in tags:
        items.append({
            "id": t.id,
            "device_id": t.device_id,
            "name": t.name,
            "breed": t.breed,
            "location": t.location,
            "weight": t.weight,
            "notes": t.notes,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None
        })
    return {"success": True, "tags": items}

@router.post("/tags")
def create_or_upsert_tag(request: TagCreateRequest, db: Session = Depends(get_db)):
    """Create or update a cow tag in TagRegistry (works for both Render DB and AWS devices)."""
    dev_str = str(request.device_id).strip()
    tag = db.query(TagRegistry).filter(TagRegistry.device_id == dev_str).first()
    notes_val = request.notes or request.description

    if tag:
        tag.name = request.name
        if request.breed is not None:
            tag.breed = request.breed
        if request.location is not None:
            tag.location = request.location
        if request.weight is not None:
            tag.weight = request.weight
        if notes_val is not None:
            tag.notes = notes_val
        action = "updated"
    else:
        tag = TagRegistry(
            device_id=dev_str,
            name=request.name,
            breed=request.breed,
            location=request.location,
            weight=request.weight,
            notes=notes_val
        )
        db.add(tag)
        action = "registered"

    db.commit()
    db.refresh(tag)

    # Invalidate AWS metadata & herd overview cache immediately
    try:
        from app.services.aws_service import AwsTelemetryService
        AwsTelemetryService.clear_cache()
    except Exception:
        pass

    return {
        "success": True, 
        "message": f"Tag {dev_str} successfully {action}!",
        "tag": {
            "id": tag.id,
            "device_id": tag.device_id,
            "name": tag.name,
            "breed": tag.breed,
            "location": tag.location,
            "weight": tag.weight,
            "notes": tag.notes
        }
    }

@router.put("/tags/{identifier}")
def update_tag(identifier: str, request: TagUpdateRequest, db: Session = Depends(get_db)):
    """Update a cow tag by primary key ID or device_id."""
    tag = None
    if str(identifier).isdigit():
        tag = db.query(TagRegistry).filter(TagRegistry.id == int(identifier)).first()
    if not tag:
        tag = db.query(TagRegistry).filter(TagRegistry.device_id == str(identifier)).first()

    if not tag:
        # Auto-create if not existing
        dev_str = str(identifier).strip()
        tag = TagRegistry(
            device_id=dev_str,
            name=request.name or f"Device #{dev_str}",
            breed=request.breed,
            location=request.location,
            weight=request.weight,
            notes=request.notes or request.description
        )
        db.add(tag)
    else:
        if request.name is not None:
            tag.name = request.name
        if request.breed is not None:
            tag.breed = request.breed
        if request.location is not None:
            tag.location = request.location
        if request.weight is not None:
            tag.weight = request.weight
        notes_val = request.notes or request.description
        if notes_val is not None:
            tag.notes = notes_val

    db.commit()
    db.refresh(tag)

    # Invalidate AWS metadata & herd overview cache
    try:
        from app.services.aws_service import AwsTelemetryService
        AwsTelemetryService.clear_cache()
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Tag {tag.device_id} updated successfully!",
        "tag": {
            "id": tag.id,
            "device_id": tag.device_id,
            "name": tag.name,
            "breed": tag.breed,
            "location": tag.location,
            "weight": tag.weight,
            "notes": tag.notes
        }
    }

@router.delete("/tags/{identifier}")
def delete_tag(identifier: str, db: Session = Depends(get_db)):
    """Delete a tag by ID or device_id."""
    tag = None
    if str(identifier).isdigit():
        tag = db.query(TagRegistry).filter(TagRegistry.id == int(identifier)).first()
    if not tag:
        tag = db.query(TagRegistry).filter(TagRegistry.device_id == str(identifier)).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found in TagRegistry")
    
    db.delete(tag)
    db.commit()

    try:
        from app.services.aws_service import AwsTelemetryService
        AwsTelemetryService.clear_cache()
    except Exception:
        pass

    return {"success": True, "message": "Tag deleted successfully"}

