from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
import app.auth as auth
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# NOTE: there is intentionally no public /auth/register endpoint. Accounts
# can only be created by an admin, via POST /admin/users. This matches the
# requirement that normal users can't just sign themselves up.


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    # role + department go into the token itself so the frontend can adapt
    # the UI immediately after login without a second API call.
    token = auth.create_access_token(
        data={"sub": user.username, "role": user.role, "department": user.department}
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
