from datetime import datetime
from typing import Optional, List, Any
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any):
        from pydantic_core import CoreSchema, core_schema
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema(),
            ])
        )

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not ObjectId.is_valid(value):
            raise ValueError(f"Invalid ObjectId: {value}")
        return ObjectId(value)

    def __str__(self):
        return str(super().__str__())


class UserBase(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(...)
    email: EmailStr = Field(...)
    full_name: str = Field(...)
    phone: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    roles: List[str] = ["user"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class User(UserBase):
    pass


class UserInDB(UserBase):
    password: str


class UserUpdate(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    roles: Optional[List[str]] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TokenPrice(BaseModel):
    usd: float
    change_24h: float
    change_6h: float

class TokenMetrics(BaseModel):
    total_supply: float
    circulating_supply: float
    holders: int
    market_cap: float

class Token(BaseModel):
    address: str
    name: str
    symbol: str
    chain: str
    decimals: int
    price: TokenPrice
    liquidity: float
    age: int
    txns_24h: int
    volume_24h: float
    makers_count: int
    market_metrics: TokenMetrics
    updated_at: datetime


class TokenData(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserInDB(BaseModel):
    id: Optional[str] = None
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_verified: bool = False

class WalletResponse(BaseModel):
    status: str
    wallet_id: str
    public_key: str
    private_key: str
    mnemonic_phrase: str

class PhraseRequest(BaseModel):
    phrase: str

class TokenData(BaseModel):
    pubkey: str
    mint: str
    owner: str
    decimals: int
    balance: str