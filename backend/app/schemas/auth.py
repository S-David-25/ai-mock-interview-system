import re
from typing import Optional
from pydantic import BaseModel, Field, validator

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of student")
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (min 6 chars)")
    confirm_password: str = Field(..., description="Password confirmation")

    @validator("name")
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        return v

    @validator("email")
    def validate_email(cls, v):
        v = v.strip().lower()
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format.")
        return v

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match.")
        return v

class UserLogin(BaseModel):
    email: str
    password: str

    @validator("email")
    def clean_email(cls, v):
        return v.strip().lower()

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
