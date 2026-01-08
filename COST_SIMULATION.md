# 대규모 스케일 비용 시뮬레이션 (Cost Simulation at Scale)

## 시뮬레이션 가정 (Assumptions)

### 스케일 파라미터
- **총 문서 수**: 1,000,000,000 (10억 건)
- **총 토픽 수**: 10,000,000 (1000만 개)
- **평균 문서당 토픽 생성/업데이트**: 3개
- **평균 문서 크기**: 5KB
- **평균 토픽 크기**: 2KB (content.md)
- **평균 메타데이터 크기**: 1KB (.meta.json)
- **평균 인용 크기**: 0.5KB

### 사용 패턴
- **일일 신규 문서 수집(Ingest)**: 1,000,000 건
- **일일 질의(Query)**: 5,000,000 건
- **평균 질의당 토픽 읽기**: 5개
- **평균 질의당 Claude 턴**: 3-5 턴

---

## 1. 저장소 비용 (Storage Costs)

### 1.1 GCS Standard Storage

#### 총 저장 용량 계산

```
토픽 파일:
- Topics (.md): 10,000,000 × 2KB = 20GB
- Metadata (.meta.json): 10,000,000 × 1KB = 10GB
- 토픽 소계: 30GB

인용 파일:
- Citations: 1,000,000,000 × 0.5KB = 500GB

로그 파일 (1년 누적):
- 수집 로그: 365,000,000 × 1KB = 365GB
- 질의 로그: 1,825,000,000 × 0.5KB = 912GB
- 로그 소계: 1,277GB

인덱스 파일:
- Topics Index: ~100MB (10M 토픽 메타데이터)
- Inverted Index: ~500MB (키워드 맵핑)
- 인덱스 소계: 0.6GB

총 저장소: 30 + 500 + 1,277 + 0.6 ≈ 1,808GB ≈ 1.8TB
```

#### GCS Storage 비용 (Standard Storage)
- **가격**: $0.020/GB/month (미국 multi-region)
- **월간 비용**: 1,808GB × $0.020 = **$36.16/month**
- **연간 비용**: $36.16 × 12 = **$433.92/year**

#### 최적화: Nearline/Coldline 스토리지 마이그레이션
```
오래된 로그/인용 → Nearline ($0.010/GB/month)
- 80% 로그 마이그레이션: 1,021GB × $0.010 = $10.21/month
- 나머지 Hot data: 787GB × $0.020 = $15.74/month
- 최적화된 월간 비용: $25.95/month ($311.4/year)
- **절감액**: ~$122/year (28% 절감)
```

---

## 2. GCS 작업 비용 (Operations Costs)

### 2.1 일일 수집(Ingest) 작업

#### 문서당 GCS 작업 분석

```
1. list_topics (인덱스 확인)
   - Class B Read: 1회 (topics_index.json)

2. search_topics (키워드 검색)
   - Class B Read: 1회 (inverted_index.json)

3. read_topic (기존 토픽 확인, 평균 3개)
   - Class B Read: 3회 (.md 파일)
   - Class B Read: 3회 (.meta.json 파일)

4. write_topic (토픽 쓰기, 평균 3개)
   - Class A Write: 3회 (.md 파일)
   - Class A Write: 3회 (.meta.json 파일)
   - Class B Read: 2회 (인덱스 파일 읽기)
   - Class A Write: 2회 (인덱스 업데이트)

5. add_citation
   - Class A Write: 1회

6. log_operation
   - Class A Write: 1회

문서당 총 작업:
- Class A (Write/List): 10회
- Class B (Read): 10회
```

#### 일일 수집 비용 (1,000,000 문서/일)

```
Class A Operations:
- 1,000,000 문서 × 10 = 10,000,000 ops/day
- 가격: $0.05 per 10,000 ops
- 비용: (10,000,000 / 10,000) × $0.05 = $50/day

Class B Operations:
- 1,000,000 문서 × 10 = 10,000,000 ops/day
- 가격: $0.004 per 10,000 ops
- 비용: (10,000,000 / 10,000) × $0.004 = $4/day

일일 수집 GCS 작업 비용: $54/day
월간 비용: $54 × 30 = $1,620/month
연간 비용: $1,620 × 12 = $19,440/year
```

### 2.2 일일 질의(Query) 작업

#### 질의당 GCS 작업 분석

```
1. search_topics
   - Class B Read: 2회 (topics_index.json + inverted_index.json)

2. read_topic (평균 5개)
   - Class B Read: 5회 (.md 파일)
   - Class B Read: 5회 (.meta.json 파일)

3. find_related_topics
   - Class B Read: 2회 (인덱스 재사용 또는 캐시 미스 시)

4. log_query
   - Class A Write: 1회

질의당 총 작업:
- Class A: 1회
- Class B: 14회
```

#### 일일 질의 비용 (5,000,000 질의/일)

```
Class A Operations:
- 5,000,000 × 1 = 5,000,000 ops/day
- 비용: (5,000,000 / 10,000) × $0.05 = $25/day

Class B Operations:
- 5,000,000 × 14 = 70,000,000 ops/day
- 비용: (70,000,000 / 10,000) × $0.004 = $28/day

일일 질의 GCS 작업 비용: $53/day
월간 비용: $53 × 30 = $1,590/month
연간 비용: $1,590 × 12 = $19,080/year
```

### 2.3 총 GCS 작업 비용

```
일일 총 작업 비용: $54 + $53 = $107/day
월간: $3,210/month
연간: $38,520/year
```

---

## 3. 네트워크 전송 비용 (Network Egress)

### 3.1 일일 데이터 전송량

#### 수집 워크플로우 (Egress from GCS)

```
인덱스 읽기 (캐시 미스 50% 가정):
- 500,000 × (0.1MB + 0.5MB) = 300GB/day

토픽 읽기:
- 1,000,000 문서 × 3 토픽 × (2KB + 1KB) × 50% = 4.5GB/day

수집 Egress: ~304GB/day
```

#### 질의 워크플로우 (Egress from GCS)

```
인덱스 읽기 (캐시 미스 30% 가정):
- 1,500,000 × 0.6MB = 900GB/day

토픽 읽기:
- 5,000,000 질의 × 5 토픽 × 3KB = 75GB/day

질의 Egress: ~975GB/day
```

#### 총 Egress: 1,279GB/day ≈ 38.4TB/month

### 3.2 네트워크 비용 (GCS → Internet/외부 클라우드)

```
GCS Network Egress 가격 (미국):
- 0-1TB: $0.12/GB
- 1-10TB: $0.11/GB
- 10TB+: $0.08/GB

월간 Egress 비용 계산:
- 1TB × $0.12 = $120
- 9TB × $0.11 = $990
- 28.4TB × $0.08 = $2,272
- 총: $3,382/month
- 연간: $40,584/year
```

### 3.3 최적화: GCP 내부 배포 (동일 리전)

```
GCS → GCE/GKE (동일 리전) = $0/GB (무료)
인프라를 GCP 내에 배포 시 네트워크 비용 제로!

절감액: $40,584/year → $0
```

---

## 4. LLM 비용 (Claude API Costs)

### 4.1 Claude Sonnet 4 가격 (2025년 1월 기준)

```
Input tokens: $3.00 per 1M tokens
Output tokens: $15.00 per 1M tokens
```

### 4.2 수집 워크플로우 토큰 사용량

#### 문서당 평균 토큰 분석

```
System Prompt: 400 tokens (IngestAgent)

Turn 1: 문서 파싱 및 컨텍스트 로딩
- Input: 400 (system) + 150 (user prompt) + 5,000 (document) = 5,550 tokens
- Tool call: parse_document
- Output: 200 tokens (reasoning) + 100 (tool call) = 300 tokens

Turn 2: 기존 토픽 검색
- Input: 5,550 + 300 + 500 (tool result) + 100 (thinking) = 6,450 tokens
- Tool calls: list_topics, search_topics
- Output: 200 + 150 = 350 tokens

Turn 3: 토픽 읽기 (3개)
- Input: 6,450 + 350 + 800 (search results) + 100 = 7,700 tokens
- Tool calls: read_topic × 3
- Output: 300 + 300 = 600 tokens

Turn 4: 토픽 쓰기/업데이트
- Input: 7,700 + 600 + 9,000 (3 topics content) + 200 = 17,500 tokens
- Tool calls: write_topic × 3, append_to_topic
- Output: 400 + 400 = 800 tokens

Turn 5: 인용 및 로그
- Input: 17,500 + 800 + 600 (write results) + 100 = 19,000 tokens
- Tool calls: add_citation, log_operation
- Output: 200 + 100 = 300 tokens

문서당 토큰 합계:
- Total Input: 56,200 tokens
- Total Output: 2,350 tokens
```

#### 일일 수집 비용 (1,000,000 문서)

```
Input tokens: 1,000,000 × 56,200 = 56,200,000,000 tokens = 56.2B tokens
Output tokens: 1,000,000 × 2,350 = 2,350,000,000 tokens = 2.35B tokens

Input 비용: 56.2B × ($3.00 / 1M) = $168,600/day
Output 비용: 2.35B × ($15.00 / 1M) = $35,250/day

일일 수집 LLM 비용: $203,850/day
월간: $6,115,500/month
연간: $73,386,000/year
```

### 4.3 질의 워크플로우 토큰 사용량

#### 질의당 평균 토큰 분석

```
System Prompt: 350 tokens (AnalysisAgent)

Turn 1: 질문 및 검색
- Input: 350 + 100 (question) = 450 tokens
- Tool calls: search_topics
- Output: 150 + 100 = 250 tokens

Turn 2: 토픽 읽기 (5개)
- Input: 450 + 250 + 600 (search results) = 1,300 tokens
- Tool calls: read_topic × 5
- Output: 200 + 300 = 500 tokens

Turn 3: 관련 토픽 확인
- Input: 1,300 + 500 + 15,000 (5 topics) = 16,800 tokens
- Tool calls: find_related_topics, read_topic × 2
- Output: 200 + 200 = 400 tokens

Turn 4: 답변 합성
- Input: 16,800 + 400 + 6,000 (related topics) = 23,200 tokens
- Tool call: log_query
- Output: 600 (answer) + 100 = 700 tokens

Turn 5: 마무리
- Input: 23,200 + 700 + 100 = 24,000 tokens
- Output: 200 tokens

질의당 토큰 합계:
- Total Input: 65,750 tokens
- Total Output: 2,050 tokens
```

#### 일일 질의 비용 (5,000,000 질의)

```
Input tokens: 5,000,000 × 65,750 = 328,750,000,000 tokens = 328.75B tokens
Output tokens: 5,000,000 × 2,050 = 10,250,000,000 tokens = 10.25B tokens

Input 비용: 328.75B × ($3.00 / 1M) = $986,250/day
Output 비용: 10.25B × ($15.00 / 1M) = $153,750/day

일일 질의 LLM 비용: $1,140,000/day
월간: $34,200,000/month
연간: $410,400,000/year
```

### 4.4 총 LLM 비용

```
일일: $203,850 + $1,140,000 = $1,343,850/day
월간: $40,315,500/month
연간: $483,786,000/year
```

---

## 5. 총 비용 요약 (Total Cost Summary)

### 5.1 비용 구성 (GCP 내부 배포 시)

| 비용 항목 | 일일 | 월간 | 연간 |
|----------|------|------|------|
| **GCS Storage** | - | $26 | $311 |
| **GCS Operations** | $107 | $3,210 | $38,520 |
| **Network Egress** | $0 | $0 | $0 |
| **Claude API (Ingest)** | $203,850 | $6,115,500 | $73,386,000 |
| **Claude API (Query)** | $1,140,000 | $34,200,000 | $410,400,000 |
| **총 비용** | **$1,343,957** | **$40,318,736** | **$483,824,831** |

### 5.2 비용 구성비

```
LLM 비용: 99.99%
GCS 비용: 0.01%
```

### 5.3 비용 스케일별 분석

```
문서당 수집 비용: $0.204
질의당 처리 비용: $0.228
토픽당 유지 비용: $0.0039/year (스토리지 + 작업)
```

---

## 6. 비용 최적화 전략 (Cost Optimization Strategies)

### 6.1 심각한 문제: LLM 토큰 사용량

현재 아키텍처의 **가장 큰 문제점**은 매 작업마다 전체 컨텍스트를 재전송하는 구조입니다.

#### 문제점:
- Turn 5에서 Input이 24,000 tokens → 누적 컨텍스트가 계속 증가
- 토픽 내용을 매번 전체 전송 (15KB ≈ 5,000 tokens)
- 시스템 프롬프트와 대화 히스토리가 매 턴마다 재전송

### 6.2 최적화 전략

#### Strategy 1: 컨텍스트 윈도우 최적화

```python
# 현재 구조:
# Turn 5: 24,000 input tokens (모든 히스토리 포함)

# 최적화 후:
# - 시스템 프롬프트 캐싱 (프롬프트 캐싱 기능 활용)
# - 이전 턴 요약 (4,000 tokens → 500 tokens)
# - 선택적 컨텍스트 로딩

예상 절감:
- 문서당 Input: 56,200 → 15,000 tokens (73% 감소)
- 질의당 Input: 65,750 → 18,000 tokens (73% 감소)

연간 절감: ~$353M (73% 감소)
```

#### Strategy 2: 프롬프트 캐싱 (Prompt Caching)

```
Claude API의 프롬프트 캐싱 활용:
- 시스템 프롬프트 캐시 (400 tokens)
- 문서 내용 캐시 (5,000 tokens)
- 인덱스 결과 캐시 (600 tokens)

캐싱 비용: $0.30 per 1M tokens (90% 할인)
캐시 가능 토큰: ~6,000 tokens/request

절감 예상:
- Input 비용: $168,600/day → $120,000/day (28% 감소)
- 연간 절감: ~$17.7M
```

#### Strategy 3: 배치 처리 및 병렬화

```
현재: 순차 처리 (5 turns)
최적화: 병렬 도구 호출 + 배치 처리

# 예: 토픽 읽기 3개를 한 번에 처리
# Turn 3, 4를 병합

예상 절감:
- 턴 수: 5 → 3 (40% 감소)
- 컨텍스트 누적 감소: 20%
- 연간 절감: ~$96.7M (20% 감소)
```

#### Strategy 4: 인덱스 캐싱 및 로컬 처리

```
GCS 인덱스를 메모리/Redis 캐싱:
- search_topics를 로컬에서 처리
- list_topics를 로컬에서 처리
- Claude에게는 최종 결과만 전달

예상 절감:
- Turn 2 제거 가능 (6,450 tokens 감소)
- GCS Read ops: 70M/day → 25M/day
- 연간 절감: LLM $15M + GCS $13K
```

#### Strategy 5: 스마트 캐싱 레이어

```
자주 조회되는 토픽 캐싱:
- Redis/Memcached에 Hot topics 캐싱
- 80/20 법칙 적용 (20% 토픽이 80% 조회)

효과:
- GCS Read ops: 70M/day → 14M/day (80% 감소)
- Network egress: 975GB/day → 195GB/day
- 연간 절감: GCS $15K
```

#### Strategy 6: Claude Haiku 사용 (간단한 작업)

```
복잡도별 모델 선택:
- 간단한 검색/읽기: Claude Haiku ($0.25 / $1.25 per 1M)
- 복잡한 분석/작성: Claude Sonnet

Haiku 가격: Input $0.25, Output $1.25 per 1M tokens
Sonnet 대비: 92% 저렴

적용 시나리오:
- 질의의 60%는 Haiku로 처리 가능
- 수집은 Sonnet 유지

예상 절감:
- Query 비용: $410M → $90M (78% 감소)
- 연간 총 절감: ~$320M
```

#### Strategy 7: 임베딩 기반 검색 (Vector DB)

```
현재: Claude가 키워드 검색 → 토픽 읽기 → 분석
최적화: Vector DB 검색 → 관련 토픽만 Claude에게 전달

아키텍처:
1. 토픽을 임베딩으로 변환 (OpenAI Ada-002: $0.0001/1K tokens)
2. Vector DB에 저장 (Pinecone/Weaviate)
3. 질의 → 임베딩 → Top-K 검색 → Claude

효과:
- 불필요한 토픽 읽기 제거
- Input tokens: 65,750 → 25,000 tokens (62% 감소)
- 질의 비용: $410M → $155M/year

추가 비용:
- 임베딩 생성: 10M topics × 2K tokens × $0.0001 = $2,000 (일회성)
- Vector DB: ~$5,000/month
- 순 절감: ~$255M/year
```

---

## 7. 최적화된 비용 예측 (Optimized Cost Projection)

### 7.1 모든 최적화 적용 시

```
전략 조합:
1. 컨텍스트 윈도우 최적화: -73% LLM 비용
2. 프롬프트 캐싱: 추가 -15% 절감
3. 배치 처리: 누적 효과
4. 인덱스 로컬 캐싱: -$15M/year
5. 스마트 토픽 캐싱: -$15K/year GCS
6. Haiku 혼합 사용: Query -78%
7. Vector DB 검색: 누적 효과

예상 최종 비용:
- Ingest LLM: $73.4M → $19.8M (73% 감소)
- Query LLM: $410M → $45M (89% 감소)
- GCS: $38.5K → $20K (48% 감소)
- Vector DB: $60K/year
- 임베딩: $2K (일회성)

총 연간 비용: $64.9M (원본 $483.8M 대비 87% 절감)
```

### 7.2 최적화 단계별 ROI

| 최적화 전략 | 구현 난이도 | 예상 절감 | ROI |
|------------|-----------|---------|-----|
| 컨텍스트 윈도우 최적화 | 중 | $353M | ⭐⭐⭐⭐⭐ |
| Haiku 혼합 사용 | 하 | $320M | ⭐⭐⭐⭐⭐ |
| Vector DB 검색 | 중 | $255M | ⭐⭐⭐⭐⭐ |
| 프롬프트 캐싱 | 하 | $17.7M | ⭐⭐⭐⭐ |
| 배치 처리 | 중 | $96.7M | ⭐⭐⭐⭐ |
| 인덱스 로컬 캐싱 | 중 | $15M | ⭐⭐⭐ |
| GCS 캐싱 레이어 | 하 | $15K | ⭐⭐ |

---

## 8. 아키텍처 권장사항 (Architecture Recommendations)

### 8.1 즉시 적용 가능 (Quick Wins)

```
1. GCP 내부 배포 → 네트워크 비용 $40K 절감
2. Claude Haiku 사용 (간단한 질의) → $320M 절감
3. 프롬프트 캐싱 활성화 → $17.7M 절감
4. Old logs를 Nearline으로 이동 → $122 절감

총 절감: ~$337.7M (70% 비용 절감)
구현 기간: 1-2주
```

### 8.2 중기 개선 (Medium-term)

```
1. Vector DB 통합 (Pinecone/Weaviate)
2. 컨텍스트 윈도우 최적화 (요약 엔진)
3. Redis 캐싱 레이어 추가
4. 배치 처리 파이프라인 구축

총 절감: ~$418.8M (87% 비용 절감)
구현 기간: 2-3개월
```

### 8.3 장기 최적화 (Long-term)

```
1. 자체 임베딩 모델 학습/배포
2. 토픽 요약 자동화 (작은 모델 사용)
3. 분산 인덱싱 시스템 (Elasticsearch/Solr)
4. 점진적 인덱스 업데이트 최적화

추가 절감 가능성: 10-15%
유지보수 비용 감소
```

---

## 9. 리스크 및 한계 (Risks and Limitations)

### 9.1 스케일 리스크

```
1. 인덱스 파일 크기 증가
   - 1000만 토픽 → 인덱스 ~600MB
   - 단일 파일 한계 → 샤딩 필요

2. 인덱스 업데이트 병목
   - 현재: 매 write마다 인덱스 업데이트
   - 대안: 배치 업데이트 (5분마다)

3. GCS API Rate Limits
   - Class B ops: 70M/day = 810 ops/sec (안전)
   - 단, 버스트 트래픽 시 Throttling 가능

4. Claude API Rate Limits
   - 1,343,850 requests/day ≈ 15.5 req/sec
   - 엔터프라이즈 계약 필요 (기본 한도 초과)
```

### 9.2 정확성 트레이드오프

```
최적화 시 주의사항:
1. 컨텍스트 축소 → 정확도 하락 가능
2. Haiku 사용 → 복잡한 질의 오답 가능
3. Vector 검색 → Semantic drift 가능
4. 캐싱 → Stale data 문제

권장: A/B 테스트 및 정확도 모니터링
```

---

## 10. 결론 및 권장 경로 (Conclusion and Recommended Path)

### 10.1 현실적인 비용 추정

```
초기 (최적화 없음):
- 연간: $483.8M
- 실행 불가능 (비용 너무 높음)

최소 최적화 (Quick Wins):
- 연간: $146.1M (70% 절감)
- Haiku + 프롬프트 캐싱 + GCP 배포

권장 최적화 (Medium-term):
- 연간: $64.9M (87% 절감)
- + Vector DB + 컨텍스트 최적화

목표 비용:
- 문서당 수집: $0.020 (원래 $0.204)
- 질의당 처리: $0.013 (원래 $0.228)
```

### 10.2 단계별 실행 계획

```
Phase 1 (Week 1-2): Quick Wins
→ 비용을 $483.8M → $146.1M으로 절감
1. Haiku 통합
2. 프롬프트 캐싱
3. GCP 배포

Phase 2 (Month 1-2): Vector DB
→ 비용을 $146.1M → $90M으로 절감
1. Vector DB 설정 (Pinecone)
2. 임베딩 생성 파이프라인
3. 검색 로직 변경

Phase 3 (Month 2-3): 컨텍스트 최적화
→ 비용을 $90M → $64.9M으로 절감
1. 컨텍스트 요약 엔진
2. 배치 처리 파이프라인
3. 인덱스 캐싱

Phase 4 (Ongoing): 모니터링 및 미세 조정
→ 추가 10-15% 절감 가능
```

### 10.3 핵심 인사이트

```
1. LLM 비용이 전체의 99.99%
   → 최적화 노력을 LLM 토큰 사용량에 집중

2. GCS 비용은 무시할 수 있는 수준
   → 스토리지 아키텍처는 현재 상태로 충분

3. 네트워크 비용은 배포 위치로 해결
   → GCP 내부 배포가 필수

4. 가장 큰 낭비는 불필요한 컨텍스트 재전송
   → 캐싱과 Vector DB가 게임 체인저

5. 적절한 모델 선택이 중요
   → Haiku vs Sonnet 선택만으로 78% 절감 가능
```

---

## 부록 A: GCS 가격표 (2025)

```
Storage (US multi-region):
- Standard: $0.020/GB/month
- Nearline: $0.010/GB/month
- Coldline: $0.004/GB/month

Operations:
- Class A (write/list): $0.05 per 10,000
- Class B (read): $0.004 per 10,000

Network:
- Egress to Internet (0-1TB): $0.12/GB
- Egress to Internet (1-10TB): $0.11/GB
- Egress to Internet (10TB+): $0.08/GB
- Egress within GCP (same region): Free
```

## 부록 B: Claude API 가격표 (2025)

```
Claude Sonnet 4:
- Input: $3.00 per 1M tokens
- Output: $15.00 per 1M tokens

Claude Haiku 3.5:
- Input: $0.25 per 1M tokens
- Output: $1.25 per 1M tokens

Prompt Caching:
- Cache write: $3.75 per 1M tokens
- Cache read: $0.30 per 1M tokens (90% discount)
```

## 부록 C: 계산 스프레드시트

```python
# 파이썬 계산 코드 (검증용)

# 기본 파라미터
TOTAL_DOCS = 1_000_000_000
TOTAL_TOPICS = 10_000_000
DAILY_INGEST = 1_000_000
DAILY_QUERIES = 5_000_000

# 문서당 토큰 사용량
INGEST_INPUT_TOKENS = 56_200
INGEST_OUTPUT_TOKENS = 2_350
QUERY_INPUT_TOKENS = 65_750
QUERY_OUTPUT_TOKENS = 2_050

# Claude 가격
SONNET_INPUT_PRICE = 3.00 / 1_000_000
SONNET_OUTPUT_PRICE = 15.00 / 1_000_000
HAIKU_INPUT_PRICE = 0.25 / 1_000_000
HAIKU_OUTPUT_PRICE = 1.25 / 1_000_000

# 일일 LLM 비용 계산
daily_ingest_llm = (
    DAILY_INGEST * INGEST_INPUT_TOKENS * SONNET_INPUT_PRICE +
    DAILY_INGEST * INGEST_OUTPUT_TOKENS * SONNET_OUTPUT_PRICE
)

daily_query_llm = (
    DAILY_QUERIES * QUERY_INPUT_TOKENS * SONNET_INPUT_PRICE +
    DAILY_QUERIES * QUERY_OUTPUT_TOKENS * SONNET_OUTPUT_PRICE
)

print(f"일일 수집 LLM 비용: ${daily_ingest_llm:,.2f}")
print(f"일일 질의 LLM 비용: ${daily_query_llm:,.2f}")
print(f"연간 총 LLM 비용: ${(daily_ingest_llm + daily_query_llm) * 365:,.2f}")
```

---

**문서 버전**: 1.0
**작성일**: 2026-01-08
**작성자**: Cost Analysis Simulation
**다음 리뷰**: Phase 1 구현 후
