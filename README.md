# Knowledge Base CLI

**AI가 자율적으로 조직하는 유연한 지식 베이스 시스템**

Claude Agent SDK 기반의 파일 저장형 지식 관리 도구입니다. 문서를 입력하면 AI Agent가 내용을 분석해서 최적의 구조로 자동 조직화하고, 나중에 지능적으로 검색/분석할 수 있습니다.

## ✨ 핵심 특징

- 🧠 **AI 자율 조직화**: Agent가 카테고리, 토픽, 관계를 자동 결정
- 🎯 **완전 유연한 구조**: 고정 스키마 없음 - 어떤 지식이든 저장 가능
- ⚡ **3단계 스케일링**: 10k-100k-10M 토픽 규모별 최적화
- 🔒 **동시성 안전**: 여러 Agent 동시 작업 지원
- 🔄 **클라우드 준비**: Azure Blob/AWS S3 마이그레이션 가능

## 🚀 빠른 시작

```bash
# 1. 설치
git clone https://github.com/ghlee7411/claude-agent-w-blob-storage.git
cd claude-agent-w-blob-storage
uv sync

# 2. API 키 설정
echo "ANTHROPIC_API_KEY='your-key'" > .env

# 3. 초기화 & 사용
uv run python cli.py init
uv run python cli.py ingest ./samples/python_gil.txt
uv run python cli.py ask "Python GIL이란?"
```

## 📋 주요 명령어

| 카테고리 | 명령어 | 설명 |
|---------|--------|------|
| **문서 관리** | `ingest <file>` | 문서 추가 |
| | `ingest-text <text>` | 텍스트 직접 추가 |
| **질의응답** | `ask <question>` | 질문하기 |
| | `summary` | 전체 요약 |
| | `gaps <topic>` | 지식 갭 분석 |
| **검색** | `search <query>` | 키워드 검색 |
| | `list [category]` | 토픽 목록 |
| | `read <topic>` | 토픽 읽기 |
| **유지보수** | `rebuild-index` | 인덱스 재구축 |
| | `migrate-index-v2` | v1.0 → v2.0 |
| | `migrate-index-v3` | v2.0 → v3.0 (1M+ 토픽용) |

## 📂 지식 베이스 구조

```
knowledge_base/
├── topics/                 # 실제 지식 콘텐츠
│   ├── python/
│   │   ├── gil.md         # Markdown 내용
│   │   └── gil.meta.json  # 메타데이터 (키워드, 관계 등)
│   └── ...
├── citations/              # 원본 문서 추적
├── logs/                   # 작업 로그
└── _index/                 # 검색 인덱스 (버전별 구조 다름)
```

### 인덱스 버전별 구조 및 스케일

| 버전 | 구조 | 적합 규모 | I/O 예시 (키워드 검색) |
|------|------|-----------|----------------------|
| **v1.0** | 단일 파일 | ~1k 토픽 | 10MB |
| **v2.0** | Sharded | 10k-100k 토픽 | 220KB (98% ↓) |
| **v3.0** | 2-Tier | 1M-10M 토픽 | 70KB (99.3% ↓) |

#### v3.0 2-Tier Index 구조 (1M-10M 스케일)

```
_index/
├── summary.json              # 전체 통계 (50KB)
├── bloom.json                # Bloom filter (20KB)
└── shards/
    ├── keywords/             # 2-tier 키워드 인덱스
    │   ├── p-t.summary.json  # 키워드 목록만 (50KB)
    │   └── p-t/
    │       ├── python.json   # 개별 키워드 (20KB)
    │       └── ...
    ├── categories/           # 카테고리별
    │   ├── python.json       # (300KB)
    │   └── ...
    └── topics/               # 100개 shard
        ├── shard_00.json     # (3.5MB)
        └── ...
```

**워크플로우 (v3.0):**
```
"python" 검색
→ Bloom filter (20KB)
→ p-t.summary.json (50KB)
→ p-t/python.json (20KB)
→ 총: 90KB (v2.0 대비 99.8% 감소!)
```

## 🏗️ 아키텍처

```
CLI Layer (cli.py)
    ↓
Agent Layer (agents/)
    IngestAgent: 문서 → 지식 변환
    AnalysisAgent: 질문 → 답변 생성
    ↓
Tools Layer (tools/)
    KnowledgeBaseTools: CRUD, 검색
    IndexBuilder v2/v3: 인덱스 생성
    ↓
Storage Layer (storage/)
    FileSystemStorage (현재)
    AzureBlobStorage (계획)
    S3Storage (계획)
```

### 동시성 안전

- **Pessimistic File Locking**: fcntl 기반 배타적 잠금
- **분산 메타데이터**: 토픽별 독립 파일
- **UUID 기반 로그**: 충돌 방지
- **ETag 낙관적 잠금**: 변경 감지

## 📊 스케일별 전략 가이드

| 토픽 수 | 권장 버전 | 마이그레이션 | Agent Token 비용 |
|---------|----------|-------------|-----------------|
| < 10k | v1.0 또는 v2.0 | 불필요 | $0.30-$1.50 |
| 10k-100k | **v2.0** | `migrate-index-v2` | $0.16 |
| 100k-1M | v2.0 + Projection | v2.0 유지 | $0.01 |
| 1M-10M | **v3.0** | `migrate-index-v3` | $0.08 |
| 10M+ | 외부 검색 엔진 권장 | Elasticsearch/Meilisearch | $0.01 |

**성능 비교 (1M 토픽 기준):**
- v1.0: 키워드 검색 = 100MB I/O ❌
- v2.0: 키워드 검색 = 2MB I/O ⚠️
- v3.0: 키워드 검색 = 70KB I/O ✅

## 🎯 사용 예시

```bash
# 문서 인제스트 (AI가 자동 조직화)
uv run python cli.py ingest ./docs/api-guide.md

# 질문하기
uv run python cli.py ask "API 인증은 어떻게 하나요?"

# 키워드 검색
uv run python cli.py search "authentication"

# 카테고리별 토픽 보기
uv run python cli.py list api

# 특정 토픽 읽기
uv run python cli.py read api/authentication

# 통계 확인
uv run python cli.py status
```

## 🗺️ 로드맵

### ✅ 완료
- [x] Claude Agent SDK 통합
- [x] 파일 시스템 스토리지 + 잠금
- [x] v2.0 Sharded Index (10k-100k 스케일)
- [x] **v3.0 2-Tier Index (1M-10M 스케일)**
- [x] Bloom Filter 최적화
- [x] 출처 추적 & 로깅

### 🚧 진행 중
- [ ] Azure Blob Storage 구현
- [ ] AWS S3 Storage 구현

### 📋 계획
- [ ] 웹 UI (Streamlit)
- [ ] Vector embedding (의미 검색)
- [ ] 더 많은 문서 포맷 (.pdf, .docx)
- [ ] API 서버 모드 (FastAPI)

## 🛠️ 개발 가이드

### 환경 설정
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
echo "ANTHROPIC_API_KEY=your-key" > .env
```

### 프로젝트 구조
```
claude-agent-w-blob-storage/
├── cli.py                  # CLI 진입점
├── agents/                 # IngestAgent, AnalysisAgent
├── tools/                  # kb_tools.py, index_builder_v2/v3.py
├── storage/                # base.py, filesystem.py, bloom_filter.py
└── scripts/                # migrate_index_v2.py, migrate_index_v3.py
```

### 새로운 Storage 구현
```python
from storage.base import BaseStorage

class MyStorage(BaseStorage):
    async def read(self, path: str) -> StorageResult: ...
    async def write(self, path: str, content: str) -> StorageResult: ...
    async def acquire_lock(self, path: str) -> str: ...
    # ... BaseStorage의 모든 메서드 구현
```

## 📚 문서

- [SHARDED_INDEX_DESIGN.md](docs/SHARDED_INDEX_DESIGN.md) - v2.0 설계 문서
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - 전체 아키텍처 (예정)
- [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) - 클라우드 마이그레이션 (예정)

## 💡 핵심 개념

**왜 v3.0이 필요한가?**

1M+ 토픽에서 v2.0의 한계:
- Keyword shard: 48MB (Agent가 2.5M tokens = $36 소비)
- Topic shard: 350MB (Agent가 87M tokens = $262 소비)

v3.0 개선:
- Keyword 2-tier: 48MB → 70KB (99.8% 감소)
- Topic 100-shard: 350MB → 3.5MB (90% 감소)
- **Agent token 비용: $262 → $0.08** (99.97% 절감)

## 🤝 기여

Issues와 Pull Requests를 환영합니다!

## 📄 라이선스

MIT License

---

**Made with ❤️ using Claude Agent SDK**
