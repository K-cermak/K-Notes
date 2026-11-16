from fastapi import APIRouter, status

from app.api.deps import CurrentAuth
from app.db import DbSession
from app.schemas.account import Me, PasswordChange, ProfileUpdate, SessionInfo
from app.services import accounts, sessions

router = APIRouter(prefix="/me", tags=["account"])


@router.get("")
def get_me(auth: CurrentAuth) -> Me:
    return accounts.to_me(auth.user)


@router.patch("")
def update_me(body: ProfileUpdate, auth: CurrentAuth, db: DbSession) -> Me:
    return accounts.to_me(accounts.update_profile(db, auth.user, body))


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, auth: CurrentAuth, db: DbSession) -> None:
    accounts.change_password(
        db, auth.user, current=body.current_password, new=body.new_password, keep_session_id=auth.session.id
    )


@router.get("/sessions")
def list_sessions(auth: CurrentAuth, db: DbSession) -> list[SessionInfo]:
    return sessions.list_for(db, auth.user, auth.session.id)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_other_sessions(auth: CurrentAuth, db: DbSession) -> None:
    sessions.revoke_others(db, auth.user.id, auth.session.id)
    db.commit()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: str, auth: CurrentAuth, db: DbSession) -> None:
    sessions.revoke(db, auth.user, session_id)
