# Architecture Documentation

## 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                    User / Application                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              KnowledgeBaseAgent (agent.py)              │
│  - Message handling                                     │
│  - Tool orchestration                                   │
│  - Claude API integration                               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│         Storage Tools Interface (storage_tools.py)      │
│  - read_file()                                          │
│  - write_file()                                         │
│  - list_files()                                         │
│  - delete_file()                                        │
│  - search_files()                                       │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌──────────────┐          ┌──────────────────┐
│ File System  │          │  Blob Storage    │
│  (Current)   │          │    (Future)      │
│              │          │  - Azure Blob    │
│ ./storage/   │          │  - AWS S3        │
└──────────────┘          └──────────────────┘
```

## 컴포넌트 상세 설명

### 1. KnowledgeBaseAgent (agent.py)

**책임**:
- Claude API와의 통신 관리
- 사용자 메시지 처리
- 도구 호출 조율
- 대화 컨텍스트 관리

**주요 메서드**:
- `__init__()`: 에이전트 초기화, API 클라이언트 설정
- `run()`: 단일 사용자 메시지 처리
- `run_interactive()`: 대화형 모드 실행
- `_process_tool_call()`: 도구 호출 처리 및 결과 반환

**워크플로우**:
```
1. 사용자 메시지 수신
2. Claude API에 메시지 전송 (도구 정의 포함)
3. Claude가 도구 사용 결정 시:
   a. 도구 이름 및 파라미터 추출
   b. _process_tool_call() 호출
   c. 결과를 Claude에게 반환
4. Claude의 최종 응답 반환
```

### 2. FileSystemStorage (storage_tools.py)

**책임**:
- 파일 시스템 기반 저장소 관리
- CRUD 작업 구현
- 파일 검색 기능

**인터페이스 설계 원칙**:
- 모든 메서드는 `Dict[str, Any]` 반환
- 항상 `success` 키 포함
- 실패 시 `error` 키로 오류 메시지 제공
- 성공 시 관련 데이터 포함

**반환 형식 예시**:
```python
# 성공
{
    "success": True,
    "content": "file content",
    "file_path": "path/to/file.txt",
    "size": 1024
}

# 실패
{
    "success": False,
    "error": "File not found: path/to/file.txt",
    "content": None
}
```

### 3. Tool Definitions (storage_tools.py)

**도구 스키마**:
Claude Agent SDK가 이해할 수 있는 JSON 스키마 형식으로 도구 정의

```python
{
    "name": "tool_name",
    "description": "What the tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param_name"]
    }
}
```

## 데이터 흐름

### 파일 쓰기 예시

```
User: "Python 정보를 tech/python.txt에 저장해줘"
  │
  ▼
Agent.run("Python 정보를 tech/python.txt에 저장해줘")
  │
  ▼
Claude API Call with tools
  │
  ▼
Claude decides to use "write_file" tool
  │
  ▼
Agent._process_tool_call("write_file", {
    "file_path": "tech/python.txt",
    "content": "Python is...",
    "mode": "w"
})
  │
  ▼
FileSystemStorage.write_file(...)
  │
  ▼
File written to ./storage/tech/python.txt
  │
  ▼
Result returned to Claude
  │
  ▼
Claude generates response
  │
  ▼
Response returned to user
```

### 파일 검색 예시

```
User: "programming이 포함된 파일을 찾아줘"
  │
  ▼
Agent.run(...)
  │
  ▼
Claude decides to use "search_files" tool
  │
  ▼
FileSystemStorage.search_files("programming")
  │
  ▼
Recursively search ./storage/
  │
  ▼
Return matching files with line numbers
  │
  ▼
Claude formats results for user
  │
  ▼
User sees list of matching files
```

## 확장성 고려사항

### 1. Storage Backend 추상화

현재 구현은 향후 쉽게 교체 가능하도록 설계:

```python
# 현재
class FileSystemStorage:
    def read_file(...) -> Dict[str, Any]: ...
    def write_file(...) -> Dict[str, Any]: ...

# 향후 - 동일한 인터페이스
class BlobStorage:
    def read_file(...) -> Dict[str, Any]: ...
    def write_file(...) -> Dict[str, Any]: ...
```

### 2. 다중 에이전트 지원

**파일 시스템 (현재)**:
- 프로세스 레벨 파일 잠금 사용
- 단일 머신에서 여러 에이전트 실행 가능
- 제한된 동시성

**Blob Storage (향후)**:
- ETag 기반 낙관적 동시성 제어
- Lease 기반 잠금
- 분산 환경 지원
- 높은 동시성

### 3. 성능 최적화 전략

#### 캐싱 레이어
```python
┌─────────────┐
│   Agent     │
└──────┬──────┘
       │
┌──────▼──────┐
│ Cache Layer │ (Optional)
└──────┬──────┘
       │
┌──────▼──────┐
│   Storage   │
└─────────────┘
```

#### 배치 작업
```python
# 단일 작업
for file in files:
    storage.read_file(file)

# 배치 작업 (향후)
storage.batch_read_files(files)
```

### 4. 메타데이터 관리

향후 구현 계획:

```python
{
    "file_path": "tech/python.txt",
    "content": "...",
    "metadata": {
        "created_at": "2024-01-07T10:00:00Z",
        "updated_at": "2024-01-07T11:00:00Z",
        "created_by": "agent_1",
        "tags": ["python", "programming"],
        "version": 2
    }
}
```

## 보안 고려사항

### 1. API 키 관리
- 환경 변수로 관리
- `.env` 파일 사용 (`.gitignore`에 포함)
- 코드에 하드코딩 금지

### 2. 파일 접근 제어
- 지정된 storage 디렉토리 외부 접근 방지
- Path traversal 공격 방지 (`../` 처리)
- 파일 크기 제한 (향후)

### 3. 입력 검증
- 파일 경로 검증
- 파일 이름 검증
- 내용 크기 제한 (향후)

## 테스트 전략

### 1. 단위 테스트 (test_storage.py)
- 각 storage 메서드 개별 테스트
- 성공/실패 케이스
- 엣지 케이스 (빈 파일, 큰 파일, 특수 문자 등)

### 2. 통합 테스트 (examples.py)
- 전체 워크플로우 테스트
- 실제 Claude API 사용
- 여러 도구의 조합

### 3. 성능 테스트 (향후)
- 대량 파일 처리
- 동시 접근
- 메모리 사용량

## 모니터링 및 로깅

### 현재 구현
- 기본 Python 출력
- 성공/실패 상태 반환

### 향후 개선
```python
import logging

logger = logging.getLogger(__name__)

def read_file(self, file_path: str):
    logger.info(f"Reading file: {file_path}")
    try:
        # ... operation
        logger.info(f"Successfully read: {file_path}")
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
```

### 메트릭 (향후)
- 파일 읽기/쓰기 횟수
- 평균 응답 시간
- 오류율
- 저장소 사용량

## 배포 고려사항

### 로컬 개발
```bash
python agent.py
```

### 컨테이너 배포 (향후)
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "agent.py"]
```

### 환경 변수
```bash
ANTHROPIC_API_KEY=xxx
STORAGE_TYPE=filesystem
STORAGE_PATH=/data/storage
```

## 유지보수 가이드

### 코드 스타일
- PEP 8 준수
- Type hints 사용
- Docstrings 작성

### 버전 관리
- Semantic Versioning
- CHANGELOG 유지
- Migration guides 제공

### 의존성 관리
- requirements.txt 업데이트
- 보안 취약점 모니터링
- 정기적인 업데이트

## 향후 로드맵

### Phase 1: 기본 기능 (완료)
- [x] 파일 시스템 스토리지
- [x] CRUD 작업
- [x] 검색 기능
- [x] Claude Agent 통합

### Phase 2: 고급 기능
- [ ] 메타데이터 관리
- [ ] 버전 관리
- [ ] 태그 시스템
- [ ] 전문 검색 (full-text search)

### Phase 3: Blob Storage 통합
- [ ] Azure Blob Storage
- [ ] AWS S3
- [ ] 마이그레이션 도구
- [ ] 하이브리드 모드

### Phase 4: 엔터프라이즈 기능
- [ ] 접근 제어
- [ ] 감사 로그
- [ ] 백업/복구
- [ ] 멀티 테넌시

## 참고 자료

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents)
- [Azure Blob Storage](https://docs.microsoft.com/azure/storage/blobs/)
- [AWS S3](https://aws.amazon.com/s3/)