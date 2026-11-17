import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import SESSION_COOKIE, CurrentAuth, session_user
from app.db import Database, DbSession
from app.errors import UnauthorizedError
from app.schemas.sync import PullResponse, PushRequest, PushResponse
from app.services import merge, pull
from app.services.events import EventHub

router = APIRouter(prefix="/sync", tags=["sync"])

HEARTBEAT_S = 25.0


def _hub(request: Request) -> EventHub:
    return request.app.state.events


@router.post("/push")
def push(body: PushRequest, request: Request, auth: CurrentAuth, db: DbSession) -> PushResponse:
    before = auth.user.seq
    response = merge.push(db, auth.user, body)
    if response.seq != before:
        _hub(request).publish(auth.user.id, response.seq)
    return response


@router.get("/pull")
def pull_changes(auth: CurrentAuth, db: DbSession, since: Annotated[int, Query(ge=0)] = 0) -> PullResponse:
    return pull.pull(db, auth.user, since)


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-Sent Events"}},
)
async def events(request: Request) -> StreamingResponse:
    """Sends `change` with the user's counter whenever it moves, and a heartbeat comment."""
    database: Database = request.app.state.db
    token = request.cookies.get(SESSION_COOKIE)
    found = await run_in_threadpool(session_user, database, token)
    if found is None:
        raise UnauthorizedError()
    user_id, seq = found
    hub = _hub(request)
    heartbeat: float = getattr(request.app.state, "sse_heartbeat_s", HEARTBEAT_S)

    async def stream() -> AsyncIterator[str]:
        listener = hub.subscribe(user_id)
        try:
            # The current counter first, so a client that missed changes while away pulls at once.
            yield f"event: change\ndata: {seq}\n\n"
            while not hub.closed:
                try:
                    await asyncio.wait_for(listener.wake.wait(), timeout=heartbeat)
                except TimeoutError:
                    # A revoked session or deactivated account ends the stream; the reconnect gets 401.
                    if await run_in_threadpool(session_user, database, token) is None:
                        return
                    yield ": heartbeat\n\n"
                    continue
                listener.wake.clear()
                if hub.closed:
                    return
                yield f"event: change\ndata: {listener.seq}\n\n"
        finally:
            hub.unsubscribe(listener)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
