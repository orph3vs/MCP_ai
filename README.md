# next_mcp

독립 실행형 MCP 서버 재설계 프로젝트다. 기존 v1 런타임에 의존하지 않고, 질문 해석은 Ollama(`qwen3.5:9b` 기본값)로 수행하며 direct basis 확정은 deterministic policy와 실제 법령 검증으로 처리한다.

## 핵심 구조

1. 입력 정규화
2. Ollama 질문 해석
3. JSON/schema 검증
4. policy/profile 보정
5. 법령군 확정
6. direct basis 검증
7. related article fetch
8. answer payload 조립

## 기본 설정

- Ollama endpoint: `http://127.0.0.1:11434`
- Ollama model: `qwen3.5:9b`
- 법령 API: `NLIC_OC` 환경변수 필요

## 엔트리포인트

- 저장소 루트에서 실행:
  - stdio: `python -m src.mcp_stdio_server`
  - HTTP: `python -m src.mcp_http_server`
  - tests: `python -m unittest discover -s tests -p 'test_*.py' -q`
- 별도 `PYTHONPATH` 설정 없이 저장소 루트 기준 실행을 지원한다.

## 주의

- Ollama 실패 시에는 새 프로젝트 내부의 규칙 fallback으로만 전환한다.
- 기존 `src.request_pipeline`은 런타임에 사용하지 않는다.
