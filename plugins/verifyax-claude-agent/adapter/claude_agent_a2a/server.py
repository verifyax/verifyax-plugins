"""A2A server that exposes a local Claude Code agent (via ClaudeCodeBackend) so
VerifyAX — or any A2A orchestrator — can drive and evaluate it.

The agent card at /.well-known/agent-card.json is public; the JSON-RPC endpoint
requires a bearer token (the key you register with VerifyAX). The advertised
card URL is derived from the request (honoring X-Forwarded-*) so it's correct
behind a tunnel with no restart.

Env:
  A2A_API_KEY        bearer token required on message/send (recommended)
  A2A_ALLOW_NO_AUTH  =1 to run with no inbound auth (local dev only)
  AGENT_NAME         card name (default "Claude Agent under evaluation")
  AGENT_DESCRIPTION  card description
  CLAUDE_PROJECT_DIR project dir the agent runs in (default: cwd)
  CLAUDE_MODEL       model (default claude-opus-4-8)
  CLAUDE_TOOLS       off | on (default off)
"""

from __future__ import annotations

import hmac
import logging
import os
import re

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.server.routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.utils import DEFAULT_RPC_URL, TransportProtocol
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from a2a.types.a2a_pb2 import AgentCard, Part
from google.protobuf.json_format import ParseDict

from .backend import ClaudeCodeBackend, ClaudeAgentError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+(:\d+)?$")

DEFAULT_NAME = "Claude Agent under evaluation"
DEFAULT_DESCRIPTION = (
    "A Claude Code agent exposed over A2A for evaluation. Delegates each turn to "
    "the local `claude` CLI running in the configured project (its CLAUDE.md and "
    "memory), and returns the reply."
)
DEFAULT_SKILL = {
    "id": "conversation",
    "name": "Conversation",
    "description": "Holds a multi-turn conversation as the configured Claude agent.",
    "tags": ["claude", "chat", "evaluation"],
    "examples": ["Explain your reasoning.", "Help me with this task."],
    "inputModes": ["text/plain"],
    "outputModes": ["text/plain"],
}


class ClaudeAgentExecutor(AgentExecutor):
    """Delegates each A2A task to the ClaudeCodeBackend."""

    def __init__(self, backend: ClaudeCodeBackend) -> None:
        self._backend = backend

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        user_text = context.get_user_input()
        if not user_text:
            await updater.failed(
                message=updater.new_agent_message([Part(text="No text input was provided.")])
            )
            return

        try:
            reply = await self._backend.send_and_wait(
                context_id=task.context_id, text=user_text
            )
        except ClaudeAgentError:
            logger.exception("Claude agent failed for context %s", task.context_id)
            await updater.failed(
                message=updater.new_agent_message(
                    [Part(text="The Claude agent is currently unavailable.")]
                )
            )
            return

        await updater.add_artifact([Part(text=reply)], name="claude-agent-reply")
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


class _BearerAuthMiddleware:
    def __init__(self, app, *, expected: str, public_paths: set[str]) -> None:
        self.app = app
        self._expected = expected
        self._public = public_paths

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") in self._public:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode("latin-1")
        presented = auth[7:] if auth[:7].lower() == "bearer " else ""
        # Compare as bytes: hmac.compare_digest raises TypeError on non-ASCII str,
        # which would surface as a 500. Guard so any bad token is a clean 401.
        try:
            ok = bool(presented) and hmac.compare_digest(
                presented.encode("utf-8"), self._expected.encode("utf-8")
            )
        except (TypeError, ValueError):
            ok = False
        if not ok:
            resp = JSONResponse(
                {"error": "unauthorized", "message": "Valid bearer token required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            return await resp(scope, receive, send)
        return await self.app(scope, receive, send)


def build_card(base_url: str, *, require_auth: bool) -> AgentCard:
    card: dict = {
        "name": os.environ.get("AGENT_NAME", DEFAULT_NAME),
        "description": os.environ.get("AGENT_DESCRIPTION", DEFAULT_DESCRIPTION),
        "version": "1.0.0",
        "supportedInterfaces": [
            {"url": base_url.rstrip("/") + DEFAULT_RPC_URL, "protocolBinding": TransportProtocol.JSONRPC}
        ],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [DEFAULT_SKILL],
    }
    if require_auth:
        card["securitySchemes"] = {
            "bearerAuth": {
                "httpAuthSecurityScheme": {
                    "scheme": "bearer",
                    "description": "Bearer token required on the JSON-RPC endpoint.",
                }
            }
        }
        card["securityRequirements"] = [{"schemes": {"bearerAuth": {"list": []}}}]
    return ParseDict(card, AgentCard())


def create_app(backend: ClaudeCodeBackend | None = None) -> Starlette:
    if backend is None:
        backend = ClaudeCodeBackend(
            project_dir=os.environ.get("CLAUDE_PROJECT_DIR"),
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-4-8"),
            tools=os.environ.get("CLAUDE_TOOLS", "off"),
            turn_timeout=float(os.environ.get("CLAUDE_TURN_TIMEOUT", "240")),
        )

    api_key = os.environ.get("A2A_API_KEY")
    if not api_key and not os.environ.get("A2A_ALLOW_NO_AUTH"):
        raise RuntimeError(
            "No inbound auth configured. Set A2A_API_KEY (the bearer VerifyAX will "
            "send), or A2A_ALLOW_NO_AUTH=1 for local dev only."
        )
    require_auth = bool(api_key)
    public_base_url = os.environ.get("PUBLIC_BASE_URL")

    executor = ClaudeAgentExecutor(backend)
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=build_card(public_base_url or "http://localhost:8080", require_auth=require_auth),
    )

    def derive_base(request: Request) -> str:
        if public_base_url:
            return public_base_url.rstrip("/")
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        if proto not in ("http", "https"):
            proto = request.url.scheme
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        if not _HOST_RE.match(host or ""):
            host = request.headers.get("host") or request.url.netloc
        return f"{proto}://{host}"

    async def agent_card(request: Request) -> JSONResponse:
        return JSONResponse(agent_card_to_dict(build_card(derive_base(request), require_auth=require_auth)))

    routes: list[Route] = [Route(AGENT_CARD_WELL_KNOWN_PATH, agent_card, methods=["GET"])]
    routes.extend(
        create_jsonrpc_routes(request_handler=handler, rpc_url=DEFAULT_RPC_URL, enable_v0_3_compat=True)
    )

    middleware: list[Middleware] = []
    if require_auth:
        middleware.append(
            Middleware(
                _BearerAuthMiddleware,
                expected=api_key,
                public_paths={AGENT_CARD_WELL_KNOWN_PATH},
            )
        )

    app = Starlette(routes=routes, middleware=middleware)
    logger.info(
        "Claude Agent A2A server ready (model=%s, tools=%s, auth=%s)",
        os.environ.get("CLAUDE_MODEL", "claude-opus-4-8"),
        os.environ.get("CLAUDE_TOOLS", "off"),
        "on" if require_auth else "OFF (dev)",
    )
    return app


app = None  # built by uvicorn factory below


def get_app() -> Starlette:
    return create_app()
