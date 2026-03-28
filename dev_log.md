# Dev Log

## Current State
- Repo root: `C:\MCP_Server\next_mcp`
- Current branch: `codex/mcpqwen35_p`
- Working tree: clean
- Default Ollama model in code: `qwen3.5:9b`
- Latest full test run: `47 tests OK`
- Test command:
  ```powershell
  & 'C:\Users\orph3\AppData\Local\Programs\Python\Python314\python.exe' -m unittest discover -s tests -p 'test_*.py' -q
  ```

## Recent Commits
- `41c76b2` Add offline sanction benchmark coverage
- `d084584` Synchronize sanction response contracts
- `2877508` Refactor privacy sanction resolution
- `d4742de` 개인정보 벌칙 조문 추가로 출력
- `adad279` Restore qwen3.5:9b as the default Ollama model

## User Operating Rules
- Commit only when the user explicitly says to commit.
- Agent naming convention:
  - `김코난`: code review / structural validation
  - `김테스트`: test-focused validation
  - `법박사`: legal wording / statutory interpretation review
- Do not arbitrarily add more agent roles without user approval.

## What Was Added

### 1. 개인정보보호법 제재 연계
- Scope is intentionally limited to `개인정보 보호법` only.
- For sanction-oriented questions, answers can append `[제재 참고]`.
- Sanction linking is not hardcoded as a single sentence. It reverse-matches Chapter 10 sanction clauses against the grounded conduct article.
- Main files:
  - `src/privacy_sanction_resolver.py`
  - `src/retrieval_planner.py`
  - `src/answer_adapter.py`

### 2. Conservative sanction trigger
- Sanction info is **not** added to every answer.
- It is only surfaced when both conditions are met:
  - interpretation suggests illegality/sanction review
  - the user query explicitly contains sanction/legality terms such as `적법`, `위법`, `위반`, `과태료`, `벌금`, `징역`, `처벌`, `벌칙`, `제재`, `형사`, `고발`
- `책임` alone was intentionally excluded because it over-triggers on non-sanction contexts.

### 3. Response contract sync
- Visible sanction references are synchronized across:
  - answer body `[제재 참고]`
  - `citations.law_context.sanction_articles`
  - `answer_plan.sanction_reference`
- Hidden sanctions are filtered out from all three together.

### 4. Regression coverage added
- Sanction resolver unit tests:
  - `tests/test_privacy_sanction_resolver.py`
- Answer contract tests:
  - `tests/test_answer_adapter.py`
- NLIC raw shape regression tests:
  - `tests/test_nlic_shapes.py`
- Offline benchmark set:
  - `tests/test_offline_benchmark.py`

## Important Legal/Product Decisions
- `[제재 참고]` must remain conditional, not global.
- The answer should not say things like "이 조문을 어기면 바로 과태료 X원" as a blanket statement.
- Safer framing is: relevant sanction clauses can be reviewed in relation to the grounded conduct article, and actual application depends on facts and the exact violated paragraph/item.
- Current sanction candidate scan is still based on the following PIPA Chapter 10 articles:
  - `제70조`
  - `제71조`
  - `제72조`
  - `제73조`
  - `제75조`

## Known Environment Constraints
- This machine could not run the local Ollama models reliably due memory/performance limits.
- Small-model experiments were rolled back from code defaults.
- Live Ollama validation on this machine was not the target at the end; the code was prepared for a stronger machine.
- When resuming on a better PC, verify:
  - Ollama server reachable
  - target model available
  - `NLIC_OC` environment variable configured if live law.go.kr integration is required

## Recommended Resume Steps On Another PC
1. Pull branch `codex/mcpqwen35_p`.
2. Run the full unit test suite.
3. Verify Ollama runtime with the intended model on the new machine.
4. Run a live smoke test for:
   - `QuestionInterpreter`
   - end-to-end `EnginePipeline.process(...)`
   - sanction-oriented privacy questions
5. If live behavior differs from fallback behavior, expand benchmark cases before broadening feature scope.

## Suggested Next Work
- Expand sanction linkage only if needed, but keep it within `개인정보 보호법` unless the user asks otherwise.
- Consider making sanction resolver input/output more domain-typed later; it still moves dict-shaped article payloads around.
- If live Ollama works on the new PC, compare:
  - `routing_source`
  - direct basis accuracy
  - sanction visibility
  - false privacy matches on non-privacy queries

## Files Worth Reading First
- `src/pipeline.py`
- `src/question_interpreter.py`
- `src/policy_engine.py`
- `src/retrieval_planner.py`
- `src/privacy_sanction_resolver.py`
- `src/answer_adapter.py`
- `tests/test_pipeline.py`
- `tests/test_offline_benchmark.py`
