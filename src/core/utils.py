"""
Lab 11 — Helper Utilities
"""
from core.config import get_llm_provider, PROVIDER_OPENROUTER  # noqa: F401
from core.openai_runtime import OpenAIRunner


async def chat_with_agent(agent, runner, user_message: str, session_id=None):
    """Send a message to the agent and get the response.

    Works with OpenAIRunner (OpenAI Red / OpenRouter Blue) and Google ADK (Gemini Red).
    """
    provider = getattr(runner, "provider", None)
    if isinstance(runner, OpenAIRunner) or provider in ("openrouter", "openai"):
        text = await runner.chat(agent, user_message)
        return text, None

    from google.genai import types

    user_id = "student"
    app_name = runner.app_name

    session = None
    if session_id is not None:
        try:
            session = await runner.session_service.get_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
        except (ValueError, KeyError):
            pass

    if session is None:
        try:
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=user_id
            )
        except Exception:
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=user_id
            )

    import asyncio
    import time

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            sess_user = f"{user_id}_{int(time.time()*1000)}"
            try:
                session = await runner.session_service.create_session(
                    app_name=app_name, user_id=sess_user
                )
            except Exception:
                pass

            cur_sess_id = session.id if session is not None else sess_user

            async def _collect_events():
                text = ""
                async for event in runner.run_async(
                    user_id=sess_user, session_id=cur_sess_id, new_message=content
                ):
                    if hasattr(event, "content") and event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                text += part.text
                return text

            final_response = await asyncio.wait_for(_collect_events(), timeout=25.0)
            return final_response, session
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return f"Error: {e}", session

    return final_response, session
