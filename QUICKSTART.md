# Quick Start Guide

## 빠른 시작 가이드

### 1. 설치

```bash
# 저장소 클론
git clone https://github.com/ghlee7411/claude-agent-w-blob-storage.git
cd claude-agent-w-blob-storage

# 의존성 설치
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

또는 `.env` 파일 생성:

```bash
cp .env.example .env
# .env 파일을 편집하여 API 키 입력
```

### 3. 테스트 실행

```bash
python test_storage.py
```

### 4. 예제 실행

#### A. 대화형 모드

```bash
python agent.py
```

대화 예시:
```
You: Python에 대한 정보를 tech/python.txt 파일에 저장해줘. Python은 1991년에 Guido van Rossum이 만든 프로그래밍 언어야.

Agent: [파일을 저장하고 결과를 알려줌]

You: 저장된 파일 목록을 보여줘

Agent: [파일 목록을 보여줌]

You: quit
```

#### B. 단일 명령 모드

```bash
python agent.py "저장된 모든 파일의 목록을 보여줘"
```

#### C. 예제 스크립트 실행

```bash
python examples.py
```

### 5. 주요 사용 예시

#### 문서 저장

```python
from agent import KnowledgeBaseAgent

agent = KnowledgeBaseAgent()
response = agent.run("""
    다음 내용을 documents/python_intro.txt에 저장해줘:
    
    Python은 간결하고 읽기 쉬운 문법을 가진 프로그래밍 언어입니다.
    데이터 과학, 웹 개발, 자동화 등 다양한 분야에서 사용됩니다.
""")
print(response)
```

#### 문서 검색

```python
response = agent.run("Python이라는 단어가 포함된 파일을 찾아줘")
print(response)
```

#### 문서 업데이트

```python
response = agent.run("""
    documents/python_intro.txt 파일에 다음 내용을 추가해줘:
    
    주요 프레임워크로는 Django, Flask, FastAPI 등이 있습니다.
""")
print(response)
```

#### 문서 조회 및 질문

```python
response = agent.run("저장된 Python 문서를 읽고 Python의 주요 특징을 요약해줘")
print(response)
```

### 6. 파일 구조

생성되는 파일 구조:

```
claude-agent-w-blob-storage/
├── storage/                    # 데이터 저장 디렉토리
│   ├── documents/
│   │   └── python_intro.txt
│   └── tech/
│       └── python.txt
├── agent.py                    # 메인 에이전트
├── storage_tools.py           # 스토리지 도구
├── examples.py                # 예제 스크립트
└── test_storage.py           # 테스트
```

### 7. 문제 해결

#### API 키 오류

```
Error: ANTHROPIC_API_KEY environment variable not set
```

해결: `export ANTHROPIC_API_KEY='your-key'` 실행

#### 모듈 없음 오류

```
ModuleNotFoundError: No module named 'anthropic'
```

해결: `pip install -r requirements.txt` 실행

#### 권한 오류

```
PermissionError: [Errno 13] Permission denied: './storage'
```

해결: 디렉토리 권한 확인 또는 다른 경로 사용

### 8. 고급 사용법

#### 커스텀 스토리지 경로

```python
agent = KnowledgeBaseAgent(
    api_key="your-key",
    storage_path="/path/to/custom/storage"
)
```

#### 다른 Claude 모델 사용

```python
agent = KnowledgeBaseAgent(
    api_key="your-key",
    model="claude-3-opus-20240229"  # 더 강력한 모델
)
```

### 9. 다음 단계

- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)를 참고하여 Blob Storage로 마이그레이션
- 다중 에이전트 환경 구축
- 커스텀 도구 추가
- 메타데이터 관리 기능 추가

### 10. 도움말

- 전체 문서: [README.md](README.md)
- 마이그레이션 가이드: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- 이슈 리포트: GitHub Issues