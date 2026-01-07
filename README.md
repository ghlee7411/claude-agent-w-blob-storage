# Claude Agent with Blob Storage

Claude Agent SDK를 사용하여 텍스트 데이터를 저장하고 관리하는 지식 베이스 시스템입니다.

## 개요

이 프로젝트는 Claude Agent SDK를 활용하여 입력으로 전달받는 텍스트 데이터를 저장하고 관리하는 기능을 제공합니다. 현재는 파일 시스템을 사용하여 구현되어 있으며, 향후 Azure Blob Storage나 AWS S3와 같은 클라우드 스토리지로 쉽게 마이그레이션할 수 있도록 설계되었습니다.

### 주요 기능

- **파일 읽기/쓰기**: 텍스트 문서를 저장소에 읽고 쓰기
- **파일 검색**: 특정 텍스트를 포함하는 문서 검색
- **파일 목록 조회**: 저장된 문서 목록 확인
- **문서 업데이트**: 기존 문서에 내용 추가 또는 수정
- **지식 베이스 구축**: 지속적으로 입력되는 문서를 통해 거대한 지식 베이스 구축

## 설치

### 요구사항

- Python 3.8 이상
- Anthropic API Key

### 설치 단계

1. 저장소 클론:
```bash
git clone https://github.com/ghlee7411/claude-agent-w-blob-storage.git
cd claude-agent-w-blob-storage
```

2. 의존성 설치:
```bash
pip install -r requirements.txt
```

3. API 키 설정:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

## 사용법

### 기본 사용법

#### 1. 대화형 모드

```bash
python agent.py
```

대화형 모드에서는 에이전트와 자유롭게 대화하며 지식 베이스를 관리할 수 있습니다:

```
You: tech_info/python.txt 파일에 Python에 대한 정보를 저장해줘
Agent: [파일 저장 결과]

You: 저장된 파일 목록을 보여줘
Agent: [파일 목록]
```

#### 2. 명령줄 모드

```bash
python agent.py "파일 목록을 보여줘"
```

#### 3. 예제 실행

```bash
python examples.py
```

예제 스크립트는 다음과 같은 기능을 시연합니다:
- 기본 파일 저장 작업
- 지식 베이스 구축
- 검색 및 쿼리
- 기존 지식 업데이트

### Python 코드에서 사용

```python
from agent import KnowledgeBaseAgent

# 에이전트 초기화
agent = KnowledgeBaseAgent(
    api_key="your-api-key",
    storage_path="./storage"
)

# 에이전트 실행
response = agent.run("Python에 대한 정보를 tech_info/python.txt에 저장해줘")
print(response)
```

## 프로젝트 구조

```
claude-agent-w-blob-storage/
├── agent.py              # 메인 에이전트 구현
├── storage_tools.py      # 파일 시스템 스토리지 도구
├── examples.py           # 사용 예제
├── requirements.txt      # Python 의존성
├── README.md            # 프로젝트 문서
├── .gitignore           # Git 제외 파일
└── storage/             # 데이터 저장 디렉토리 (자동 생성)
```

## 스토리지 도구

### 제공되는 도구

1. **read_file**: 파일 읽기
2. **write_file**: 파일 쓰기 (덮어쓰기 또는 추가)
3. **list_files**: 디렉토리의 파일 목록 조회
4. **delete_file**: 파일 삭제
5. **search_files**: 텍스트 검색

### 도구 사용 예시

에이전트는 자연어 명령을 통해 이러한 도구를 자동으로 사용합니다:

- "documents/article.txt 파일을 읽어줘"
- "새로운 정보를 knowledge/python.txt에 저장해줘"
- "programming이라는 단어가 포함된 파일을 찾아줘"
- "tech_info 디렉토리에 있는 모든 파일을 보여줘"

## Blob Storage로 마이그레이션

현재 구현은 파일 시스템을 사용하지만, 향후 클라우드 blob storage로 쉽게 마이그레이션할 수 있도록 설계되었습니다.

### 마이그레이션 계획

1. **storage_tools.py 수정**: `FileSystemStorage` 클래스를 `BlobStorage` 클래스로 교체
2. **동일한 인터페이스 유지**: 모든 메서드가 동일한 입력/출력 형식을 유지
3. **에이전트 코드 변경 최소화**: agent.py는 수정 없이 또는 최소한의 수정으로 작동

### Azure Blob Storage 예시

```python
# 향후 구현 예시
from azure.storage.blob import BlobServiceClient

class BlobStorage:
    def __init__(self, connection_string: str, container_name: str):
        self.client = BlobServiceClient.from_connection_string(connection_string)
        self.container = self.client.get_container_client(container_name)
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        # Azure Blob Storage에서 읽기
        pass
    
    def write_file(self, file_path: str, content: str, mode: str = "w") -> Dict[str, Any]:
        # Azure Blob Storage에 쓰기
        pass
    
    # ... 나머지 메서드들
```

## 다중 에이전트 환경

이 시스템은 여러 에이전트 세션이 공통된 스토리지를 공유하도록 설계되었습니다:

- **공유 스토리지**: 모든 에이전트가 동일한 storage 디렉토리/blob container 사용
- **동시성 지원**: 파일 시스템 기반이므로 기본적인 파일 잠금 메커니즘 활용
- **확장성**: Blob storage로 마이그레이션 시 더 나은 동시성 및 확장성 제공

## 보안 고려사항

- API 키는 환경 변수로 관리
- 민감한 데이터는 .gitignore에 포함
- storage/ 디렉토리는 버전 관리에서 제외

## 개발 로드맵

- [x] 파일 시스템 기반 스토리지 구현
- [x] Claude Agent SDK 통합
- [x] 기본 CRUD 작업
- [x] 검색 기능
- [x] 예제 및 문서화
- [ ] Azure Blob Storage 지원
- [ ] AWS S3 지원
- [ ] 동시성 제어 강화
- [ ] 메타데이터 관리
- [ ] 버전 관리 기능

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

이슈 및 풀 리퀘스트를 환영합니다!
