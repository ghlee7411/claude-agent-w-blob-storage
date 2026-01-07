# 사용 예제 모음

## 기본 사용 예제

### 1. 단순 문서 저장

```python
from agent import KnowledgeBaseAgent

agent = KnowledgeBaseAgent()

# 문서 저장
response = agent.run("""
    다음 내용을 docs/meeting_notes.txt 파일에 저장해줘:
    
    2024년 1월 7일 팀 미팅
    - 새로운 기능 개발 계획 논의
    - Q1 목표 설정
    - 다음 주 월요일 재논의
""")
print(response)
```

### 2. 파일 읽기

```python
response = agent.run("docs/meeting_notes.txt 파일의 내용을 읽어줘")
print(response)
```

### 3. 파일 목록 조회

```python
response = agent.run("docs 디렉토리에 있는 모든 파일을 보여줘")
print(response)
```

## 지식 베이스 구축 예제

### 기술 문서 저장

```python
# 여러 기술 문서 저장
tech_docs = {
    "tech/python.txt": """
        Python은 1991년 Guido van Rossum이 만든 고수준 프로그래밍 언어입니다.
        간결하고 읽기 쉬운 문법이 특징이며, 다양한 분야에서 활용됩니다.
        
        주요 특징:
        - 인터프리터 언어
        - 동적 타이핑
        - 객체 지향, 함수형, 절차적 프로그래밍 지원
        - 풍부한 표준 라이브러리
        
        주요 용도:
        - 웹 개발 (Django, Flask, FastAPI)
        - 데이터 과학 (NumPy, Pandas, Scikit-learn)
        - 머신러닝 (TensorFlow, PyTorch)
        - 자동화 및 스크립팅
    """,
    
    "tech/javascript.txt": """
        JavaScript는 웹 브라우저에서 실행되는 스크립트 언어입니다.
        Brendan Eich가 1995년 Netscape에서 개발했습니다.
        
        주요 특징:
        - 프로토타입 기반 객체 지향
        - 일급 함수 (First-class functions)
        - 이벤트 기반 비동기 프로그래밍
        - 동적 타이핑
        
        주요 용도:
        - 프론트엔드 개발 (React, Vue, Angular)
        - 백엔드 개발 (Node.js, Express)
        - 모바일 앱 (React Native)
        - 데스크톱 앱 (Electron)
    """,
    
    "tech/go.txt": """
        Go는 Google에서 개발한 오픈소스 프로그래밍 언어입니다.
        2009년 Robert Griesemer, Rob Pike, Ken Thompson이 설계했습니다.
        
        주요 특징:
        - 정적 타이핑, 컴파일 언어
        - 가비지 컬렉션
        - 고루틴을 통한 동시성 지원
        - 빠른 컴파일 속도
        - 간결한 문법
        
        주요 용도:
        - 마이크로서비스
        - 클라우드 인프라 도구
        - 네트워크 서버
        - 명령줄 도구
    """
}

# 각 문서 저장
for file_path, content in tech_docs.items():
    response = agent.run(f"다음 내용을 {file_path}에 저장해줘: {content}")
    print(f"✓ {file_path} 저장 완료")
```

## 검색 및 조회 예제

### 키워드 검색

```python
# 특정 키워드가 포함된 문서 찾기
response = agent.run("'머신러닝'이라는 단어가 포함된 파일을 찾아줘")
print(response)

response = agent.run("'웹 개발'과 관련된 문서를 검색해줘")
print(response)
```

### 문서 기반 질문 답변

```python
# 저장된 문서를 읽고 질문에 답하기
response = agent.run("""
    저장된 Python 문서를 읽고 다음 질문에 답해줘:
    Python의 주요 특징은 무엇이고, 어떤 분야에서 주로 사용되나요?
""")
print(response)

response = agent.run("""
    JavaScript와 Python의 차이점을 저장된 문서를 기반으로 설명해줘
""")
print(response)
```

### 요약 생성

```python
response = agent.run("""
    tech 디렉토리의 모든 문서를 읽고 각 프로그래밍 언어의 
    주요 특징을 한 줄로 요약해줘
""")
print(response)
```

## 문서 업데이트 예제

### 내용 추가

```python
# 기존 문서에 내용 추가
response = agent.run("""
    tech/python.txt 파일에 다음 내용을 추가해줘:
    
    최근 동향:
    - Python 3.12 릴리스 (2023년 10월)
    - 성능 개선 지속
    - Type hints 사용 증가
    - AI/ML 분야 지배적 위치 유지
""")
print(response)
```

### 문서 갱신

```python
# 문서 내용 읽고 업데이트
response = agent.run("""
    tech/go.txt 파일을 읽고, Go 1.21의 새로운 기능에 대한 
    정보를 추가해줘:
    
    Go 1.21 새로운 기능 (2023년 8월):
    - 프로파일 가이드 최적화 (PGO)
    - 새로운 내장 함수: clear, min, max
    - 표준 라이브러리 개선
""")
print(response)
```

## 고급 사용 예제

### 구조화된 데이터 관리

```python
# JSON 형식으로 데이터 저장
import json

project_info = {
    "name": "Claude Agent Project",
    "version": "1.0.0",
    "description": "Knowledge base management system",
    "technologies": ["Python", "Claude API", "File Storage"],
    "team": ["Developer 1", "Developer 2"]
}

response = agent.run(f"""
    다음 JSON 데이터를 projects/info.json 파일에 저장해줘:
    {json.dumps(project_info, ensure_ascii=False, indent=2)}
""")
print(response)
```

### 카테고리별 문서 관리

```python
# 여러 카테고리로 문서 구성
categories = {
    "tutorials/beginner": [
        ("python_basics.txt", "Python 기초 튜토리얼"),
        ("setup_guide.txt", "개발 환경 설정 가이드")
    ],
    "tutorials/advanced": [
        ("async_programming.txt", "비동기 프로그래밍"),
        ("design_patterns.txt", "디자인 패턴")
    ],
    "reference": [
        ("api_docs.txt", "API 문서"),
        ("glossary.txt", "용어집")
    ]
}

for category, files in categories.items():
    for filename, description in files:
        file_path = f"{category}/{filename}"
        response = agent.run(f"""
            {file_path} 파일에 '{description}'에 대한 문서를 생성해줘
        """)
        print(f"✓ {file_path} 생성")
```

### 멀티턴 대화 예제

```python
# 여러 단계에 걸쳐 작업 수행
agent = KnowledgeBaseAgent()

# 1단계: 정보 수집
response = agent.run("현재 저장된 Python 관련 문서를 모두 찾아줘")
print("Step 1:", response)

# 2단계: 내용 분석
response = agent.run("찾은 문서들을 읽고 Python의 장단점을 정리해줘")
print("Step 2:", response)

# 3단계: 요약 저장
response = agent.run("""
    방금 정리한 Python의 장단점을 summaries/python_pros_cons.txt에 저장해줘
""")
print("Step 3:", response)
```

## 실전 시나리오

### 시나리오 1: 회의록 관리

```python
# 회의록 저장 및 관리
agent = KnowledgeBaseAgent()

# 회의록 저장
response = agent.run("""
    meetings/2024-01-07_weekly.txt 파일에 다음 회의록을 저장해줘:
    
    주간 팀 미팅
    일시: 2024년 1월 7일 10:00
    참석: 김철수, 이영희, 박민수
    
    안건:
    1. 프로젝트 진행 상황 공유
       - 백엔드 API 개발 완료 (김철수)
       - 프론트엔드 UI 디자인 진행 중 (이영희)
       - 테스트 케이스 작성 시작 (박민수)
    
    2. 이슈 및 해결 방안
       - 데이터베이스 성능 문제 발견
       - 인덱스 추가로 해결 예정
    
    3. 다음 주 계획
       - UI 개발 완료 목표
       - 통합 테스트 시작
       - 코드 리뷰 세션 진행
    
    액션 아이템:
    - [김철수] 데이터베이스 인덱스 추가 (~ 1/10)
    - [이영희] UI 개발 완료 (~ 1/12)
    - [박민수] 테스트 케이스 50개 작성 (~ 1/12)
""")

# 액션 아이템 검색
response = agent.run("모든 회의록에서 '액션 아이템'을 포함하는 부분을 찾아줘")
print(response)
```

### 시나리오 2: 기술 문서 버전 관리

```python
# 문서 버전 관리
from datetime import datetime

current_date = datetime.now().strftime("%Y-%m-%d")

response = agent.run(f"""
    API 문서의 새 버전을 저장해줘:
    
    파일명: api_docs/v2.0_{current_date}.txt
    
    내용:
    API Documentation v2.0
    
    Breaking Changes:
    - /api/users 엔드포인트 응답 형식 변경
    - 인증 헤더 형식 업데이트
    
    New Features:
    - /api/search 엔드포인트 추가
    - 페이지네이션 지원
    - 필터링 옵션 추가
    
    Deprecated:
    - /api/old-users (2024-03-01에 제거 예정)
""")
```

### 시나리오 3: FAQ 관리

```python
# FAQ 데이터베이스 구축
faqs = [
    {
        "question": "Claude Agent란 무엇인가요?",
        "answer": "Claude Agent는 Anthropic의 Claude AI를 사용하여 자동화된 작업을 수행하는 시스템입니다."
    },
    {
        "question": "파일은 어디에 저장되나요?",
        "answer": "기본적으로 ./storage 디렉토리에 저장됩니다. 설정을 통해 변경 가능합니다."
    },
    {
        "question": "Blob Storage로 어떻게 마이그레이션하나요?",
        "answer": "MIGRATION_GUIDE.md 문서를 참고하세요. Azure Blob Storage나 AWS S3로 쉽게 전환할 수 있습니다."
    }
]

for i, faq in enumerate(faqs, 1):
    response = agent.run(f"""
        faq/q{i:02d}.txt 파일에 다음 내용을 저장해줘:
        
        Q: {faq['question']}
        A: {faq['answer']}
    """)
    print(f"✓ FAQ {i} 저장 완료")

# FAQ 검색
response = agent.run("'마이그레이션'과 관련된 FAQ를 찾아줘")
print(response)
```

## 대화형 사용 예제

```python
# 대화형 모드에서 사용할 수 있는 명령어 예제

"""
You: 현재 저장된 모든 파일의 목록을 보여줘

You: tech 디렉토리의 파일만 보여줘

You: Python에 대한 새 문서를 만들어줘

You: 방금 만든 문서에 예제 코드를 추가해줘

You: 'machine learning'이라는 단어가 포함된 모든 문서를 찾아줘

You: 각 문서의 첫 100자만 보여줘

You: 가장 최근에 수정된 파일 3개를 알려줘

You: meetings 디렉토리의 모든 회의록을 하나로 합쳐줘

You: quit
"""
```

## 에러 처리 예제

```python
# 에러 처리를 포함한 강건한 코드

def safe_agent_operation(agent, message):
    """에러 처리를 포함한 안전한 작업"""
    try:
        response = agent.run(message)
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 사용 예
agent = KnowledgeBaseAgent()
result = safe_agent_operation(agent, "파일 목록을 보여줘")

if result["success"]:
    print(result["response"])
else:
    print(f"오류 발생: {result['error']}")
```

## 배치 처리 예제

```python
# 여러 파일을 한 번에 처리

documents = [
    "article1.txt",
    "article2.txt", 
    "article3.txt"
]

summaries = []
for doc in documents:
    response = agent.run(f"{doc} 파일을 읽고 한 문장으로 요약해줘")
    summaries.append(response)

# 모든 요약을 하나의 파일로 저장
all_summaries = "\n\n".join(summaries)
response = agent.run(f"""
    다음 요약들을 summaries/all_summaries.txt에 저장해줘:
    {all_summaries}
""")
```

## 템플릿 활용 예제

```python
# 문서 템플릿 사용

template = """
제목: {title}
작성자: {author}
날짜: {date}

## 개요
{overview}

## 상세 내용
{details}

## 참고 자료
{references}
"""

doc_data = {
    "title": "Python 비동기 프로그래밍",
    "author": "김개발",
    "date": "2024-01-07",
    "overview": "Python의 asyncio를 사용한 비동기 프로그래밍 소개",
    "details": "async/await 키워드를 사용하여...",
    "references": "- Python 공식 문서\n- Real Python 튜토리얼"
}

content = template.format(**doc_data)
response = agent.run(f"tutorials/async_python.txt에 다음 내용을 저장해줘: {content}")
```

이 예제들은 Claude Agent를 활용하여 다양한 문서 관리 작업을 수행하는 방법을 보여줍니다. 실제 사용 시에는 프로젝트의 요구사항에 맞게 수정하여 사용하세요.