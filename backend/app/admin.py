from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from sqlalchemy.orm import Session
import bcrypt

from app.database import SessionLocal
from app.models.user import User
from app.models.tag_registry import TagRegistry
from app.models.datalogger import RawPacket, SensorPacket, DataloggerHeader
from app.models.ui_parameter import ActivityConfig
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        # Fallback: if it's stored as plain-text in the database for some reason
        return plain_password == hashed_password

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        db: Session = SessionLocal()
        try:
            # You can log in with username or email
            user = db.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if user and verify_password(password, user.hashed_password):
                # Save session
                request.session.update({"token": user.id})
                return True
        finally:
            db.close()
            
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        return True


# -- Model Views --

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_active, User.is_superuser]
    column_searchable_list = [User.username, User.email]
    column_sortable_list = [User.id, User.username]
    can_delete = False
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"


class TagRegistryAdmin(ModelView, model=TagRegistry):
    column_list = [TagRegistry.id, TagRegistry.device_id, TagRegistry.name, TagRegistry.breed, TagRegistry.location]
    column_searchable_list = [TagRegistry.device_id, TagRegistry.name, TagRegistry.notes]
    name = "Cow Tag"
    name_plural = "Cow Tags"
    icon = "fa-solid fa-cow"


class RawPacketAdmin(ModelView, model=RawPacket):
    column_list = [RawPacket.id, RawPacket.status, RawPacket.created_at, RawPacket.processed_at]
    column_sortable_list = [RawPacket.id, RawPacket.created_at]
    can_create = False
    can_edit = False
    name = "Raw BLE Packet"
    name_plural = "Raw BLE Packets"
    icon = "fa-solid fa-microchip"


class DataloggerHeaderAdmin(ModelView, model=DataloggerHeader):
    column_list = [DataloggerHeader.id, DataloggerHeader.device_id, DataloggerHeader.packet_id_num, DataloggerHeader.total_packets, DataloggerHeader.timestamp]
    column_searchable_list = [DataloggerHeader.device_id]
    can_create = False
    name = "Data Header"
    name_plural = "Data Headers"
    icon = "fa-solid fa-database"

class ActivityConfigAdmin(ModelView, model=ActivityConfig):
    column_list = [ActivityConfig.id, ActivityConfig.code, ActivityConfig.name, ActivityConfig.color, ActivityConfig.category]
    column_searchable_list = [ActivityConfig.code, ActivityConfig.name]
    name = "Activity Config"
    name_plural = "Activity Configs"
    icon = "fa-solid fa-palette"
