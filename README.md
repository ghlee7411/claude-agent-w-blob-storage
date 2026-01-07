# Knowledge Base CLI with Claude Agent SDK

Claude Agent SDK를 사용하여 파일 기반 지식 베이스를 구축하고 관리하는 CLI 도구입니다.

## 개요

이 프로젝트는 문서를 입력받아 파일 기반의 지식 베이스를 구축하고, 이를 바탕으로 질의응답을 수행하는 시스템입니다. Claude Agent SDK의 `@tool` 데코레이터 패턴을 사용하여 구현되었습니다.

### 핵심 컨셉

- **Planning-with-files 패턴 변주**: 마크다운 파일을 "디스크 상의 워킹 메모리"로 활용
- **분산 메타데이터**: 동시성 환경을 위한 파일별 독립적 메타데이터
- **ETag 기반 낙관적 동시성**: Blob Storage 전환을 대비한 설계

### 주요 기능

- **Ingest 모드**: 문서 파일(.txt, .html, .md)을 지식 베이스에 통합
- **Analysis 모드**: 지식 베이스를 검색하여 질문에 답변
- **동시성 지원**: 여러 에이전트가 동시에 실행 가능한 구조

## 설치

### 요구사항

- Python 3.10 이상
- Anthropic API Key

### 설치 단계

```bash
# 저장소 클론
git clone https://github.com/ghlee7411/claude-agent-w-blob-storage.git
cd claude-agent-w-blob-storage

# 의존성 설치
pip install -r requirements.txt

# API 키 설정
export ANTHROPIC_API_KEY='your-api-key-here'

# 지식 베이스 초기화
python cli.py init
```

## 사용법

### CLI 명령어

```bash
# 지식 베이스 초기화
python cli.py init

# 문서 인제스트
python cli.py ingest ./docs/document.txt
python cli.py ingest ./docs/article.html

# 텍스트 직접 인제스트
python cli.py ingest-text "Python은 인터프리터 언어입니다." --source "manual-input"

# 질의응답
python cli.py ask "Python의 GIL이란 무엇인가요?"

# 지식 베이스 요약
python cli.py summary

# 특정 영역의 지식 갭 분석
python cli.py gaps "python"

# 지식 베이스 상태 확인
python cli.py status

# 토픽 목록 조회
python cli.py list
python cli.py list python  # 카테고리 필터

# 토픽 검색
python cli.py search "concurrency"

# 특정 토픽 읽기
python cli.py read python/gil

# 인덱스 재구축
python cli.py rebuild-index
```

### Python API 사용

```python
import asyncio
from agents import IngestAgent, AnalysisAgent

async def main():
    # Ingest Agent
    ingest = IngestAgent(storage_path="./knowledge_base")
    result = await ingest.ingest("./docs/python_guide.txt")
    print(result)

    # Analysis Agent
    analysis = AnalysisAgent(storage_path="./knowledge_base")
    answer = await analysis.ask("Python의 특징은 무엇인가요?")
    print(answer)

asyncio.run(main())
```

## 프로젝트 구조

```
claude-agent-w-blob-storage/
├── cli.py                    # Typer CLI 진입점
├── agents/
│   ├── __init__.py
│   ├── base_agent.py         # 베이스 에이전트 (Claude Agent SDK)
│   ├── ingest_agent.py       # 문서 인제스트 에이전트
│   └── analysis_agent.py     # 질의응답 에이전트
├── tools/
│   ├── __init__.py
│   ├── kb_tools.py           # 지식베이스 도구 (CRUD, 검색)
│   └── document_tools.py     # 문서 파싱 도구
├── storage/
│   ├── __init__.py
│   ├── base.py               # 스토리지 추상 인터페이스
│   └── filesystem.py         # 파일시스템 구현
├── knowledge_base/           # 지식 베이스 데이터
│   ├── topics/               # 토픽 파일 (.md + .meta.json)
│   ├── citations/            # 원본 문서 출처
│   ├── logs/                 # 작업 로그
│   └── _index/               # 인덱스 캐시
└── requirements.txt
```

## 지식 베이스 구조

### Topics (topics/)

각 토픽은 두 개의 파일로 구성:
- `{topic}.md`: 마크다운 내용
- `{topic}.meta.json`: 메타데이터 (키워드, 버전, ETag 등)

```
topics/
├── python/
│   ├── gil.md
│   ├── gil.meta.json
│   ├── asyncio.md
│   └── asyncio.meta.json
└── concepts/
    ├── concurrency.md
    └── concurrency.meta.json
```

### Citations (citations/)

원본 문서 추적:
```json
{
  "citation_id": "abc123",
  "source_document": "./docs/python_guide.txt",
  "contributed_topics": ["python/gil", "python/asyncio"],
  "summary": "Python 비동기 프로그래밍 가이드"
}
```

### Logs (logs/)

에이전트별 독립 로그 (동시성 충돌 방지):
```
logs/
├── agent-abc123_20240107_103000_def456.json
└── agent-xyz789_20240107_103001_ghi012.json
```

## 아키텍처

### 동시성 설계

- **분산 메타데이터**: 단일 index 파일 대신 각 토픽에 독립적 메타데이터
- **ETag 기반 동시성**: 파일 수정 시 ETag 검증으로 충돌 감지
- **UUID 기반 citation/log**: 고유 ID로 파일명 충돌 방지
- **인덱스 재구축 가능**: 메타데이터로부터 언제든 인덱스 재생성

### Blob Storage 전환 준비

현재 파일시스템 구현은 `storage/base.py`의 추상 인터페이스를 따르므로, Azure Blob이나 AWS S3로 쉽게 전환 가능:

```python
# 예: Azure Blob Storage 구현
class AzureBlobStorage(BaseStorage):
    async def read(self, path: str) -> StorageResult:
        # Azure Blob API 사용
        pass
```

## 개발 로드맵

- [x] Claude Agent SDK 통합 (@tool 데코레이터)
- [x] Typer CLI
- [x] 파일 시스템 스토리지
- [x] 분산 메타데이터 구조
- [x] ETag 기반 동시성 제어
- [ ] Azure Blob Storage 지원
- [ ] AWS S3 지원
- [ ] 웹 UI

## 라이선스

MIT License
