# Sharded Index Design

## 목적

기존 단일 파일 인덱스 구조의 문제점을 해결하고, 대규모 지식 베이스(10k-100k 토픽)에서도 효율적으로 동작하도록 개선합니다.

## 문제점 분석

### 현재 구조 (v1.0)
```
_index/
├── topics_index.json           # 4MB (10k 토픽 기준)
└── inverted_index.json         # 10MB (10k 토픽 기준)
```

**문제점:**
1. **Token 낭비**: Agent가 검색할 때마다 전체 10MB 인덱스 로드
2. **메모리 비효율**: 여러 Agent 실행 시 각각 10MB씩 캐싱
3. **네트워크 비용**: 클라우드 스토리지 마이그레이션 시 10MB 다운로드
4. **확장성 한계**: 100k 토픽 시 50-100MB 인덱스 파일

## 새로운 구조 (v2.0) - Sharded Index

### 디렉토리 구조

```
_index/
├── summary.json                # ~50KB - 전체 통계만
├── bloom.json                  # ~20KB - Bloom filter (빠른 존재 확인)
└── shards/
    ├── keywords/               # 키워드 역색인 (알파벳별 분할)
    │   ├── a-e.json           # 'a'~'e'로 시작하는 키워드
    │   ├── f-j.json
    │   ├── k-o.json
    │   ├── p-t.json
    │   └── u-z.json
    │
    ├── categories/             # 카테고리별 토픽 목록
    │   ├── python.json
    │   ├── javascript.json
    │   ├── concepts.json
    │   └── ...
    │
    └── topics/                 # 토픽 메타데이터 (해시 기반 분할)
        ├── shard_0.json       # hash(topic_id) % 10 == 0
        ├── shard_1.json
        ├── shard_2.json
        ...
        └── shard_9.json
```

### 파일 내용 예시

#### `summary.json` (~50KB)
```json
{
  "version": "2.0.0",
  "index_type": "sharded",
  "total_topics": 10000,
  "total_keywords": 5234,
  "total_categories": 15,
  "categories": ["python", "javascript", "concepts", "api", "database"],
  "last_rebuilt": "2024-01-07T10:00:00Z",
  "shard_config": {
    "keyword_shards": ["a-e", "f-j", "k-o", "p-t", "u-z"],
    "topic_shards": 10
  }
}
```

#### `bloom.json` (~20KB)
```json
{
  "version": "1.0",
  "size": 10000,
  "hash_count": 7,
  "false_positive_rate": 0.01,
  "filters": {
    "keywords": {
      "bit_array": [0, 1, 0, 1, 1, 0, ...],
      "count": 5234
    },
    "categories": {
      "bit_array": [0, 0, 1, 0, ...],
      "count": 15
    }
  }
}
```

#### `shards/keywords/p-t.json` (~200KB)
```json
{
  "shard_id": "p-t",
  "keyword_count": 1047,
  "keywords": {
    "python": ["python/gil", "python/asyncio", "python/threading"],
    "performance": ["concepts/performance", "database/optimization"],
    "promise": ["javascript/promises", "javascript/async-await"],
    "postgresql": ["database/postgresql", "database/sql"],
    ...
  },
  "titles": {
    "python": ["python/gil", "python/types"],
    "performance": ["concepts/performance"],
    ...
  }
}
```

#### `shards/categories/python.json` (~300KB)
```json
{
  "category": "python",
  "topic_count": 245,
  "topics": {
    "python/gil": {
      "title": "Python GIL (Global Interpreter Lock)",
      "keywords": ["python", "gil", "concurrency", "threading"],
      "related_topics": ["python/asyncio", "python/multiprocessing"],
      "last_modified": "2024-01-07T10:30:00Z"
    },
    "python/asyncio": {
      "title": "Python Asyncio",
      "keywords": ["python", "asyncio", "async", "concurrency"],
      "related_topics": ["python/gil", "concepts/concurrency"],
      "last_modified": "2024-01-06T15:20:00Z"
    },
    ...
  }
}
```

#### `shards/topics/shard_0.json` (~400KB)
```json
{
  "shard_id": 0,
  "topic_count": 1000,
  "topics": {
    "python/gil": {
      "title": "Python GIL (Global Interpreter Lock)",
      "keywords": ["python", "gil", "concurrency", "threading"],
      "related_topics": ["python/asyncio", "python/multiprocessing"],
      "category": "python",
      "last_modified": "2024-01-07T10:30:00Z",
      "last_modified_by": "agent-abc123"
    },
    ...
  }
}
```

## 검색 워크플로우

### 시나리오 1: 키워드 검색 ("python")

**기존 방식 (v1.0):**
1. `inverted_index.json` 읽기 (10MB)
2. `keywords["python"]` 조회
3. 결과 반환
- **총 I/O: 10MB**

**새로운 방식 (v2.0):**
1. `bloom.json` 읽기 (20KB) → "python" 존재 확인 ✓
2. `shards/keywords/p-t.json` 읽기 (200KB)
3. `keywords["python"]` 조회
4. 결과 반환
- **총 I/O: 220KB (98% 감소)**

### 시나리오 2: 카테고리 목록 ("python 카테고리 토픽들")

**기존 방식 (v1.0):**
1. `topics_index.json` 읽기 (4MB)
2. 전체 순회하며 `topic_id.startswith("python/")`로 필터링
3. 결과 반환
- **총 I/O: 4MB**

**새로운 방식 (v2.0):**
1. `summary.json` 읽기 (50KB) → 카테고리 목록 확인
2. `shards/categories/python.json` 읽기 (300KB)
3. 결과 반환
- **총 I/O: 350KB (91% 감소)**

### 시나리오 3: 특정 토픽 메타데이터 조회 ("python/gil")

**기존 방식 (v1.0):**
1. `topics_index.json` 읽기 (4MB)
2. `topics["python/gil"]` 조회
3. 결과 반환
- **총 I/O: 4MB**

**새로운 방식 (v2.0):**
1. `hash("python/gil") % 10 = 3` 계산
2. `shards/topics/shard_3.json` 읽기 (400KB)
3. `topics["python/gil"]` 조회
4. 결과 반환
- **총 I/O: 400KB (90% 감소)**

## Bloom Filter 상세

### 목적
불필요한 shard 읽기를 방지하기 위한 빠른 필터링.

### 동작 원리
```python
# 키워드 "python" 존재 확인
if bloom_filter.might_contain("python"):
    # shard 읽기 (false positive 1% 확률)
    shard = read_keyword_shard("p-t")
else:
    # 확실히 없음 - shard 읽기 생략
    return []
```

### 설정
- **Size**: 10,000 bits (키워드 수의 2배)
- **Hash functions**: 7개 (optimal for 1% FP rate)
- **False positive rate**: 1% (허용 가능한 수준)
- **파일 크기**: ~20KB

### Trade-off
- **장점**: 99% 확률로 불필요한 I/O 방지
- **단점**: 1% False positive (실제로 없는데 있다고 판단)
  - 영향: shard 읽었는데 결과 없음 (최악의 경우)
  - 허용 가능: 사용자에게는 "검색 결과 없음"으로 보임

## Sharding 전략

### 1. Keyword Sharding (알파벳 기반)
```python
def get_keyword_shard(keyword: str) -> str:
    first_char = keyword.lower()[0]
    if 'a' <= first_char <= 'e':
        return "a-e"
    elif 'f' <= first_char <= 'j':
        return "f-j"
    elif 'k' <= first_char <= 'o':
        return "k-o"
    elif 'p' <= first_char <= 't':
        return "p-t"
    else:
        return "u-z"
```

**이점:**
- 예측 가능한 분포
- 영어 단어 빈도에 따라 균등 분배
- 'a-e', 'p-t'가 가장 많을 것으로 예상

### 2. Category Sharding (카테고리별)
```python
def get_category_shard(topic_id: str) -> str:
    return topic_id.split("/")[0]  # "python/gil" → "python"
```

**이점:**
- 자연스러운 격리
- 카테고리별 독립적 조회
- 캐싱 효율성 증가

### 3. Topic Sharding (해시 기반)
```python
def get_topic_shard(topic_id: str) -> int:
    import hashlib
    hash_val = int(hashlib.md5(topic_id.encode()).hexdigest(), 16)
    return hash_val % 10
```

**이점:**
- 균등 분배
- 특정 shard 집중 방지
- 확장 용이 (shard 수 증가 가능)

## 성능 비교

### 10,000 토픽 기준

| 작업 | v1.0 (단일 파일) | v2.0 (Sharded) | 개선율 |
|------|------------------|----------------|--------|
| 키워드 검색 | 10MB | 220KB | 98% ↓ |
| 카테고리 목록 | 4MB | 350KB | 91% ↓ |
| 토픽 메타데이터 | 4MB | 400KB | 90% ↓ |
| 전체 통계 | 4MB | 50KB | 99% ↓ |

### 100,000 토픽 기준

| 작업 | v1.0 (단일 파일) | v2.0 (Sharded) | 개선율 |
|------|------------------|----------------|--------|
| 키워드 검색 | 100MB | 2MB | 98% ↓ |
| 카테고리 목록 | 40MB | 3MB | 92% ↓ |
| 토픽 메타데이터 | 40MB | 4MB | 90% ↓ |

### Token 비용 (Claude API)

10,000 토픽 기준:
- **v1.0**: 10MB ≈ 2.5M tokens ≈ $7.50/query
- **v2.0**: 220KB ≈ 55k tokens ≈ $0.16/query
- **절약**: 97.8% ($7.34/query)

## 구현 계획

### Phase 1: Bloom Filter 유틸리티
- `storage/bloom_filter.py` 추가
- Bloom filter 생성/조회 함수

### Phase 2: Sharded Index Builder
- `tools/index_builder.py` 추가
- 기존 메타데이터 → Sharded index 변환
- Incremental update 지원

### Phase 3: Index Reader 수정
- `kb_tools.py`의 `get_index()`, `get_inverted_index()` 수정
- Backward compatibility 유지 (v1.0 → v2.0 자동 마이그레이션)

### Phase 4: 마이그레이션 도구
- `scripts/migrate_index_v2.py` 추가
- 기존 지식 베이스 자동 변환

### Phase 5: 테스트
- 성능 벤치마크
- 정확성 검증 (v1.0 vs v2.0 결과 동일)

## Backward Compatibility

### 자동 감지 및 마이그레이션
```python
async def get_index():
    # summary.json 확인
    summary = await storage.read_json("_index/summary.json")

    if summary.get("version") == "2.0.0":
        # v2.0 Sharded index
        return await load_sharded_index()
    else:
        # v1.0 단일 파일 index
        print("⚠️  Migrating to v2.0 sharded index...")
        await migrate_to_v2()
        return await load_sharded_index()
```

## 확장 가능성

### 더 많은 Shard 추가
```python
# 키워드를 10개 shard로 분할
# a, b, c, d, e, f-j, k-o, p, q-t, u-z

# Topic을 20개 shard로 분할
# hash(topic_id) % 20
```

### 동적 Shard 크기 조정
```python
# Shard가 1MB 초과 시 자동 분할
if shard_size > 1_000_000:
    split_shard(shard_id)
```

## 예상 효과

### 10,000 토픽 지식 베이스
- **I/O 감소**: 98%
- **메모리 사용**: 10MB → 500KB (95% 감소)
- **Token 비용**: 97.8% 절감
- **검색 속도**: 비슷 (Bloom filter overhead 미미)

### 100,000 토픽 지식 베이스
- **I/O 감소**: 98%
- **메모리 사용**: 100MB → 5MB (95% 감소)
- **Token 비용**: 97.8% 절감
- **검색 속도**: 2-3배 빠름 (캐시 효율 증가)

## 다음 단계

1. ✅ 설계 문서 작성 (현재)
2. Bloom Filter 구현
3. Index Builder 구현
4. kb_tools.py 수정
5. 마이그레이션 스크립트
6. 테스트 및 벤치마크
7. README 업데이트
