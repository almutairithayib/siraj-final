import uuid
import json
import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google.genai import types

from backend.app.config import settings
from backend.app.models.chat import ChatMessage
from backend.app.ai.system_prompt import get_system_prompt
from backend.app.ai.context_builder import build_context
from backend.app.ai.tools import SirajTools
from backend.app.ai.ai_provider import AIProvider, ProviderName, FALLBACK_MESSAGE_AR
from backend.app.ai.ai_cache import get_context_cache

logger = logging.getLogger("siraj.ai.agent_loop")

# Tools that perform write operations — fallback provider must NEVER call these
WRITE_TOOLS = frozenset({
    "add_transaction",
    "set_budget",
    "create_savings_plan",
    "create_spending_alert",
    "submit_financing_request",
    "submit_investment_request",
    "create_financial_goal",
})


async def run_agent_loop(
    session_id: uuid.UUID,
    user_message: str,
    user_id: uuid.UUID,
    db: AsyncSession
) -> AsyncGenerator[str, None]:
    """
    Main AI agent loop with multi-provider resilience.
    
    Flow:
      1. Build context (with caching)
      2. Load chat history
      3. Call AI provider (Gemini → OpenAI → fallback)
      4. Handle tool calls or stream final response
      5. Log all steps with structured metadata
    """
    provider = AIProvider()
    cache = get_context_cache(ttl_seconds=settings.AI_CONTEXT_CACHE_TTL)
    user_id_str = str(user_id)

    # 1. Build dynamic context with caching
    cached_context = cache.get(user_id_str)
    if cached_context is not None:
        context_str = cached_context
        logger.info("CONTEXT | source=cache | user_id=%s", user_id_str)
    else:
        context_str = await build_context(user_id, db)
        cache.set(user_id_str, context_str)
        logger.info("CONTEXT | source=database | user_id=%s", user_id_str)

    system_prompt = get_system_prompt(context_str)

    # 2. Load previous chat history from DB
    history_res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    history_msgs = history_res.scalars().all()

    # 3. Construct content list for Gemini format
    contents = []

    for msg in history_msgs:
        if msg.role == "user":
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=msg.content)]
            ))
        elif msg.role == "assistant":
            # If assistant message has saved content
            if msg.content:
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=msg.content)]
                ))
            # If assistant message has tool call metadata, reconstruct it
            if msg.tool_metadata and "function_calls" in msg.tool_metadata:
                calls = []
                for fc in msg.tool_metadata["function_calls"]:
                    calls.append(types.Part(
                        function_call=types.FunctionCall(
                            name=fc["name"],
                            args=fc["args"]
                        )
                    ))
                if calls:
                    contents.append(types.Content(role="model", parts=calls))
        elif msg.role == "tool":
            # Reconstruct tool response part
            if msg.tool_metadata and "function_response" in msg.tool_metadata:
                fr = msg.tool_metadata["function_response"]
                contents.append(types.Content(
                    role="tool",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=fr["name"],
                            response=fr["response"]
                        )
                    )]
                ))

    # Initialize tool helper
    tools_instance = SirajTools(user_id, db)

    genai_tools = [
        tools_instance.get_transactions,
        tools_instance.get_financial_summary,
        tools_instance.get_category_breakdown,
        tools_instance.get_budget_analysis,
        tools_instance.get_recurring_charges,
        tools_instance.add_transaction,
        tools_instance.set_budget,
        tools_instance.create_savings_plan,
        tools_instance.create_spending_alert,
        tools_instance.simulate_scenario,
        tools_instance.submit_financing_request,
        tools_instance.get_financing_status,
        tools_instance.get_investment_recommendations,
        tools_instance.submit_investment_request,
        tools_instance.create_financial_goal,
    ]

    tool_map = {f.__name__: f for f in genai_tools}

    # 4. Agent loop for tool calling
    loop_count = 0
    max_loops = 5

    while loop_count < max_loops:
        loop_count += 1
        logger.info(
            "AGENT_LOOP | iteration=%d/%d | session_id=%s | history_len=%d",
            loop_count, max_loops, str(session_id)[:8], len(contents),
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=genai_tools,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        )

        # Call model through provider chain
        result = await provider.generate_content(
            contents=contents,
            config=config,
            system_prompt=system_prompt,
            tools=genai_tools,
        )

        # Handle total provider failure — Arabic fallback
        if result.is_fallback:
            logger.critical(
                "AGENT_FALLBACK | session_id=%s | loop=%d | all_providers_failed",
                str(session_id)[:8], loop_count,
            )
            yield f"data: {json.dumps({'content': result.fallback_message}, ensure_ascii=False)}\n\n"

            # Save fallback message to DB
            fallback_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=result.fallback_message,
                tool_metadata={"fallback": True, "provider": "none"}
            )
            db.add(fallback_msg)
            await db.commit()
            break

        response = result.response

        # Log provider metadata
        logger.info(
            "PROVIDER_RESULT | provider=%s | latency_ms=%.0f | retries=%d | loop=%d",
            result.provider.value, result.latency_ms, result.retries, loop_count,
        )

        # Handle OpenAI response format (wrapped in OpenAIResponseWrapper)
        if result.provider == ProviderName.OPENAI:
            # OpenAI responses are wrapped — check for function calls
            if response.function_calls:
                # Safety check: block write tools from secondary provider
                blocked = [fc for fc in response.function_calls if fc.name in WRITE_TOOLS]
                if blocked:
                    blocked_names = [fc.name for fc in blocked]
                    logger.warning(
                        "WRITE_BLOCKED | provider=openai | blocked_tools=%s",
                        blocked_names,
                    )
                    safe_msg = (
                        "عذراً، لا أستطيع تنفيذ العمليات المالية في الوقت الحالي "
                        "بسبب صيانة مؤقتة. يمكنني الإجابة على استفساراتك المالية. "
                        "يرجى المحاولة مرة أخرى بعد قليل لتنفيذ العمليات."
                    )
                    yield f"data: {json.dumps({'content': safe_msg}, ensure_ascii=False)}\n\n"

                    fallback_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=safe_msg,
                        tool_metadata={"write_blocked": True, "provider": "openai"}
                    )
                    db.add(fallback_msg)
                    await db.commit()
                    break

                # Execute allowed tool calls from OpenAI
                model_parts = []
                tool_parts = []
                function_calls_meta = []

                for call in response.function_calls:
                    name = call.name
                    args = call.args

                    # Yield Arabic status
                    status_msg = _get_tool_status_msg(name)
                    yield f"data: {json.dumps({'status': status_msg}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.5)

                    # Execute tool
                    tool_func = tool_map.get(name)
                    if tool_func:
                        try:
                            tool_result = await tool_func(**args)
                        except Exception as e:
                            tool_result = {"status": "error", "message": str(e)}
                    else:
                        tool_result = {"status": "error", "message": f"Tool {name} not found."}

                    model_parts.append(types.Part(
                        function_call=types.FunctionCall(name=name, args=args)
                    ))
                    tool_parts.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=name, response={"result": tool_result}
                        )
                    ))
                    function_calls_meta.append({"name": name, "args": args})

                    # Save tool response
                    tool_msg = ChatMessage(
                        session_id=session_id,
                        role="tool",
                        content=None,
                        tool_metadata={"function_response": {"name": name, "response": tool_result}}
                    )
                    db.add(tool_msg)

                # Save model's tool calls
                model_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=None,
                    tool_metadata={"function_calls": function_calls_meta}
                )
                db.add(model_msg)
                await db.commit()

                # Invalidate context cache since tools may have changed data
                if any(fc.name in WRITE_TOOLS for fc in response.function_calls):
                    cache.invalidate(user_id_str)

                contents.append(types.Content(role="model", parts=model_parts))
                contents.append(types.Content(role="tool", parts=tool_parts))
                continue

            else:
                # OpenAI text response — stream it as a single chunk
                if response.text:
                    yield f"data: {json.dumps({'content': response.text}, ensure_ascii=False)}\n\n"

                    final_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=response.text,
                        tool_metadata={"provider": "openai"}
                    )
                    db.add(final_msg)
                    await db.commit()
                break

        # Handle Gemini response format (native)
        if response.function_calls:
            model_parts = []
            tool_parts = []
            function_calls_meta = []

            for call in response.function_calls:
                name = call.name
                args = call.args

                # Yield a friendly Arabic indicator to client
                status_msg = _get_tool_status_msg(name)
                yield f"data: {json.dumps({'status': status_msg}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.5)

                # Execute tool
                tool_func = tool_map.get(name)
                if tool_func:
                    try:
                        tool_result = await tool_func(**args)
                    except Exception as e:
                        tool_result = {"status": "error", "message": str(e)}
                else:
                    tool_result = {"status": "error", "message": f"Tool {name} not found."}

                # Reconstruct for GenAI history
                model_parts.append(types.Part(
                    function_call=types.FunctionCall(
                        name=name,
                        args=args
                    )
                ))

                tool_parts.append(types.Part(
                    function_response=types.FunctionResponse(
                        name=name,
                        response={"result": tool_result}
                    )
                ))

                function_calls_meta.append({
                    "name": name,
                    "args": args
                })

                # Save the tool response message into the database
                tool_msg = ChatMessage(
                    session_id=session_id,
                    role="tool",
                    content=None,
                    tool_metadata={"function_response": {"name": name, "response": tool_result}}
                )
                db.add(tool_msg)

            # Save the model's tool calls message to database
            model_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=None,
                tool_metadata={"function_calls": function_calls_meta}
            )
            db.add(model_msg)
            await db.commit()

            # Invalidate context cache if any write tools were called
            if any(call.name in WRITE_TOOLS for call in response.function_calls):
                cache.invalidate(user_id_str)
                logger.info("CACHE_INVALIDATED | reason=write_tool | user_id=%s", user_id_str)

            # Add to Gemini history contents
            contents.append(types.Content(role="model", parts=model_parts))
            contents.append(types.Content(role="tool", parts=tool_parts))

            # Continue the loop to let the model process the tool results
            continue

        else:
            # No function calls. Stream the final text response!
            streaming_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=genai_tools,
                temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            full_text = ""
            async for chunk_text in provider.generate_content_stream(
                contents=contents,
                config=streaming_config,
            ):
                full_text += chunk_text
                yield f"data: {json.dumps({'content': chunk_text}, ensure_ascii=False)}\n\n"

            # Save assistant's final message to database
            final_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_text,
                tool_metadata={"provider": "gemini"}
            )
            db.add(final_msg)
            await db.commit()

            logger.info(
                "AGENT_COMPLETE | session_id=%s | loops=%d | response_len=%d",
                str(session_id)[:8], loop_count, len(full_text),
            )

            # Exit loop
            break

    # Yield final done event
    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    # Log cache stats periodically
    stats = cache.stats
    logger.debug("CACHE_STATS | %s", json.dumps(stats))


def _get_tool_status_msg(tool_name: str) -> str:
    """Return a user-friendly Arabic status message for a given tool."""
    arabic_tool_names = {
        "get_transactions": "جاري مراجعة المعاملات المالية...",
        "get_financial_summary": "جاري حساب الملخص المالي...",
        "get_category_breakdown": "جاري تحليل فئات الإنفاق...",
        "get_budget_analysis": "جاري فحص الالتزام بالميزانية...",
        "get_recurring_charges": "جاري الكشف عن الفواتير والاشتراكات المتكررة...",
        "add_transaction": "جاري إضافة المعاملة الجديدة...",
        "set_budget": "جاري تحديث ميزانيتك...",
        "create_savings_plan": "جاري إنشاء حصالة الادخار...",
        "create_spending_alert": "جاري إعداد تنبيه الإنفاق...",
        "simulate_scenario": "جاري محاكاة السيناريو المالي...",
        "submit_financing_request": "جاري إرسال طلب التمويل الإسلامي...",
        "get_financing_status": "جاري التحقق من حالة طلبات التمويل...",
        "get_investment_recommendations": "جاري جلب الفرص الاستثمارية الملائمة...",
        "submit_investment_request": "جاري تقديم طلب الاستثمار المالي...",
        "create_financial_goal": "جاري جدولة الهدف المالي الموسمي..."
    }
    return arabic_tool_names.get(tool_name, f"جاري تنفيذ العملية: {tool_name}...")
