import httpx

from config import settings


async def explain_volunteer(volunteer: dict, user_question: str | None = None) -> str:
    """
    Generate natural-language explanation via LLM.
    Falls back to template when LLM is not configured.
    """
    if not settings.llm_api_key:
        tier = volunteer.get("tier", "")
        return (
            f"【{tier}】{volunteer.get('school_name')} · {volunteer.get('group_name')}。"
            f"参考近年最低位次 {volunteer.get('ref_min_rank')}，"
            f"您的位次 {volunteer.get('student_rank')}。"
            f"计划人数 {volunteer.get('plan_count')}。"
            "（未配置 LLM，此为模板说明）"
        )

    # 部分 API（如仅支持 user/assistant 的兼容端点）不接受 role=system
    prompt = f"""【角色】你是广东省高考志愿填报顾问。只根据 evidence 解释，禁止编造分数或位次；不确定的须明确说明。

志愿数据：
{volunteer}

用户问题：{user_question or '请解释为什么归入该档位，以及主要风险。'}

要求：200字以内，口语化，注明数据年份与免责声明。"""

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:500] if e.response else str(e)
            raise RuntimeError(f"LLM 调用失败 ({e.response.status_code}): {detail}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"无法连接 LLM 服务，请检查 LLM_BASE_URL 与网络: {e}") from e
