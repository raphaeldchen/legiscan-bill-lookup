from pydantic import BaseModel
from typing import Optional, List

class SignupRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class CategoryCreate(BaseModel):
    name: str
    keywords: List[str] = []

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[List[str]] = None

class FilterRequest(BaseModel):
    category_ids: List[int]
