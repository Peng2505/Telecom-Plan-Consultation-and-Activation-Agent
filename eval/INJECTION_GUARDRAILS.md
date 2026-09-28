# Prompt 注入防御与 Guardrails

## 实现要点

1. **提示词隔离**：`prompts/prompt_template_*.txt` 使用 `<<<USER>>>` / `<<<RETRIEVED_DOC untrusted>>>` / `<<<TOOL_JSON authoritative>>>` 分区。
2. **检索包装**：`utils/tools_config.py` 的 `retrieve_plans` 经 `wrap_untrusted_docs` 输出；价表/工单 JSON 经 `wrap_tool_json`。
3. **办理硬通道**：`demoRagAgent.agent` 对注入模式直接拒答；注入夹带「确认办理」不算有效确认；模型私自 `create_order` 会被剥离。
4. **检测逻辑**：`utils/guardrails.py` 的 `looks_like_prompt_injection`。

## 复现评测

需 API 已启动（`main.py` 或 Docker `api`）：

```bat
cd /d d:\LangGraphChatBot-main\04_RagAgent
D:\Anaconda\envs\langgraph\python.exe eval\run_injection_eval.py
```

产物：`eval/last_injection_result.json`

- `interception_rate`：攻击用例拦截率（简历主数字）
- `benign_passed`：正常问价/推荐仍可用（防误杀）

## 简历口径

> Prompt 注入防御与 Guardrails：用户输入与检索文档隔离标注，办理类高危指令走独立二次确认通道；自建渗透集（当前约 45 条攻击 + 9 条良性）拦截率以 `last_injection_result.json` 为准，并主动说明为回归集口径。

用例分类见 `injection_cases.json`：`kind=attack|benign`。
