# Sitelayout 확장 계획 — Plot Plan 요구사항 대응

> 작성: 2026-07-04. 근거: 4개 설계영역 병렬 설계 + 완전성 검증(누락 7건·충돌 15건·불변조건 리스크 7건 검출 후 중재).

## 0. 불변 원칙 (모든 결정에 우선)

**프로그램은 규칙 "어휘"만 제공하고, 내용은 전부 사용자 데이터다.**

- 코드에는 특정 시설물(GT/HRSG/…)·특정 프로젝트 규칙을 넣지 않는다. 추가되는 것은 언제나
  **일반 기능**(새 규칙 종류, 새 요소 종류, 새 도구)이다.
- Plot plan requirement.xlsx 같은 실제 케이스는 **JSON 시나리오 파일(데이터)** 로만 존재한다.
  요구사항 변경 = 데이터 수정이며 코드 수정이 아니다.
- 배치 흐름 유지: **타입 정의 → 규칙 정의 → 순서 구성 → 순서대로 자동/수동 배치.**
  블록(그룹)도 "순서 목록에 들어가는 배치 단위 하나"로 편입된다.

## 1. 목표

발전소 Plot plan 수준의 요구사항을 **사용자 데이터만으로** 표현·배치·검증할 수 있게 앱을 확장한다.
xlsx 25개 블록 요구사항 기준 커버리지: 현재 ~60% → 목표 ~95% (미지원 항목은 §7에 명시하고 근사/문서화).

## 2. 아키텍처 중재 결정 (설계 충돌 15건 단일화)

병렬 설계안 간 충돌을 다음과 같이 확정한다. **이후 구현은 이 표가 유일한 진실.**

| # | 쟁점 | 결정 | 기각안 및 사유 |
|---|---|---|---|
| D1 | 블록 데이터 모델 | **buildingTypes에 `kind:'block'` + `members:[{typeId,dc,dr,w,h}]`**. 배치 시 placement에 members 스냅샷 복사(기존 w,h 복사 관행과 동일). 블록도 typeId이므로 sequence/feasibility/autoPlace 계약 무변경 | 별도 blockGroups[]+groupId 방식 기각 — 엔진 전체가 placement 원자성 가정이라 사실상 재작성이 됨 |
| D2 | 블록 내부 멤버 타깃 | **규칙 스키마 무변경 + `expandTargets()` 암묵 확장** — targetType이 유닛 타입이면 블록 내 동일 타입 멤버가 가상 rect로 자동 타깃("HRSG 가까이"가 Power block 내부 HRSG에 걸림) | targetKind:'member' 명시 스키마 기각 — 규칙 UI/스키마 복잡도 대비 이득 없음 |
| D3 | 단위계 | **m 정본** — 규칙에 `gapM/minM/maxM` 저장, 엔진 직전 `compileRules(rules, cellSize)` 1곳에서 셀 환산. 엔진은 셀 정수 연산 유지(성능·시드 재현성 보존). **셀 필드는 컴파일 캐시로만 존재, 직렬화 금지(이중 진실 금지)** | 엔진 전면 m화 기각(부동소수 회귀 리스크), 셀 canonical 기각(cellSize 변경 시 물리 의미 붕괴) |
| D4 | 환산 정책 | `units.js` 한 곳에 고정: **이격류=올림(ceil), 이내류=내림(floor)**, epsilon 1e-9 가드. nearRoad는 경계셀=1 오프셋 반영해 `1+floor(gapM/cs)`. 환산 결과 0셀이면 UI 경고 | — |
| D5 | 엔진 컨텍스트 전달 | **placeGrid.ctx 부착** (centroid/풍향장/도로축/거리장) — 기존 함수 시그니처 유지, selftest 무수정 통과 | (grid,edgeDist)→ctx 인자 리팩터 기각 — 호출부 15곳 파급, 회귀 부담 |
| D6 | 풍향 | `state.windDir`(방위각 도, 8방위 스냅 UI, null=비활성) + 규칙 kind **`windSide`** {side:'down'\|'up', gapM 여유}. soft는 투영값 비례 **graded 점수**(=Flare "가장 외곽" 표현) | 16방위 문자열/`windRelative` 기각 — 표현 통일 |
| D7 | between 정의 | **midpoint ± gapM(셀 환산)** — "K.O Drum은 Stack과 PB의 중간" | ±20% 비율 밴드 기각 — 파라미터 직관성 |
| D8 | 중앙 배치 | 규칙 kind **`centerOf`** (buildable 질량중심에서 gapM 이내, soft 권장) 단일 해법 | fence setback 그라디언트 기각 — 동일 의미의 우회 표현 |
| D9 | 선형 요소 | **`corridors[{id,kind:'road'\|'rack'\|'tunnel'\|'conduit',name,widthM,waypoints,route,cells}]` 단일 레이어**. 기존 roadNetwork는 로드 시 corridor(road)로 승격 흡수. kind별 물성: tunnel은 `blocks:false`(지하 — 배치 차단 안 함, 클리어런스만 참여) | roadNetwork/rackNetwork 병렬 배열 기각 — 코드 중복 |
| D10 | 전역/대안별 귀속 | **배치 위치에 종속되는 기하(블록 둘레도로, from/to 자동 라우팅 결과)는 대안별(alt) 저장.** 사이트 인프라(외곽 소방도로, 수동 그린 랙)만 전역 corridors | 전역 병합 기각 — 한 대안의 드래그가 다른 대안을 소급 invalid시키는 불변조건 위반 |
| D11 | 클리어런스 | **전역 `clearances` 대칭 매트릭스**(카테고리×kind, m 단위: 도로↔장비 3m 등) + buildingTypes에 `category` 필드. evaluateHard에서 kind별 거리장 O(1) 조회로 판정(위반 사유 리포트 가능). 라우팅 시점에만 마스크 팽창(dilate) 기법 차용 | per-type 규칙 폭발 기각(68타입×3종), 전면 버퍼 마스크 기각(진단 정보 소실, 건물↔건물 커버 불가) |
| D12 | nearRoad/setback 기준 | `basis:'any'(기본, 기존 동작)\|'road'\|'fence'` 3분기. **거리장 소스 분리**: fence장(원본 격자 경계만), road장(road kind 셀만). rack/tunnel은 edgeDist 소스에서 제외(의미 오염 방지) | — |
| D13 | 회전 | **블록 타입만 rot 0~3 지원**(R키, 후보 4배 탐색). members는 "회전 적용 후" 좌표로 저장(단일 진실). 유닛 회전·alignToRoad는 2차 과제로 보류, Oil storage류는 장변 방향으로 타입 정의해 우회 | 미러링 기각(장비 좌우반전 문제) |
| D14 | 스키마 버전 | `schemaVersion:2` 도입, **migrateState() 한 곳**이 마이그레이션 소유(구형 kind 변환 → 셀→m 이관 → 기본값 주입 순). v1 로드 시 완전 재현 보장(왕복 동등성 테스트) | 필드 추가만으로 버티기 기각 — undo 스택 내 v1/v2 혼재 해석 버그 방지 |
| D15 | 점수식 변경 | 경계 근접 가점(5/(1+minEdge)) 제거는 **옵션 플래그**로 — 기본값은 기존 유지(selftest 시드 재현성 보존) | 무조건 제거 기각 |

## 3. 단계별 계획

의존성 순서. 각 Phase는 독립 배포·검증 가능하며, 완료 기준은 **selftest 전체 통과 + 해당 Phase 신규 케이스**.

### Phase 0 — 사전 검증·도구 (게이트) ✅ 완료 (2026-07-04)

| 항목 | 결과 |
|---|---|
| 성능 스파이크 | **cellSize 2m 지원 확정.** 60k 셀 측정: buildGrid 2ms·edgeDist 8ms·소형 candidateMap 3~50ms는 무해. 병목은 대형 블록(60×45셀) 전수 스캔 393ms/회 → 어닐링 300회에서 2분대. **완화책 적용 완료**: 연산량 예산(`scanCost=격자셀×풋프린트 > 1.5e6`) 초과 시 improvePlacements/annealPlacements가 전수 스캔 대신 무작위 샘플링(40회 시도, 시드 기반=결정적). 적용 후 21동+블록 autoPlace 10s→**1.0s**, 어닐링 300회 6.4s→**13ms**. 소형 격자(기존 시나리오)는 전수 경로 유지(회귀 무영향) |
| xlsx 변환 스크립트 | `tools/import_xlsx.py` 완성·실검증: 실제 xlsx에서 타입 65개, 블록 초안 28개(PB 멤버 16 정확), m값 힌트 추출(20m/100m), 미배치 3블록 식별 → `demos/draft.json` |
| 결정 고정 | §2 표 기준으로 Phase 1 구현 완료 |

### Phase 1 — 단위계(m)·거리장·컨텍스트 토대 ✅ 완료 (2026-07-04)

구현·검증 완료: units.js(환산 정책 단일화)·규칙 m 정본(gapM/minM/maxM)·migrateState(v1→v2 왕복 동등성 증명)·
computeDistFieldNear 일반화·basis(any/road/fence) 분기·placeGrid.ctx 부착·refreshPlacementContext 단일 경로·
모달 m 입력+환산 미리보기+0셀 경고·ruleToText m 병기. selftest 39/39(신규 9), UI 통합 9케이스 통과.

원래 계획(참고):

- `src/units.js` 신설: `mCeil/mFloor`(epsilon), `compileRules`, `fmtM` — 환산 정책 단일화, DOM 무의존 순수 모듈
- 규칙 m 정본화(`gapM/minM/maxM`) + `migrateState`(v1 셀값×cellSize 이관, **왕복 동등성 테스트로 배치 판정 100% 불변 증명**)
- `computeDistField(grid, sources)` 일반화(computeEdgeDist는 래퍼로 유지) → fence장/road장 분리, `basis` 분기
- `placeGrid.ctx` 부착 + **refreshPlacementContext를 유일한 재계산·candCache 무효화 경로로 확립**(규칙 저장/cellSize/windDir/restore 전부 경유 — stale 캐시 계열 버그의 구조적 봉쇄)
- UI: 규칙 모달 m 입력 + "20m → 2셀(올림)" 실시간 환산 표시, 셀 크기 라벨 "m/셀", 축척바
- 테스트: 환산 정책표, 마이그레이션 왕복, 거리장 분리(fence↔road 상호 무반응), 기존 30케이스 무회귀

### Phase 2 — 블록 시스템 ✅ 완료 (2026-07-04)

구현·검증 완료: kind:'block' 타입+members 스냅샷, mask 기반 fits/buildOccupancy/placementCovers/placementArea(WeakMap 캐시),
placementGap 전수 치환, expandTargets 멤버 자동 타깃, **addWouldViolate cand측 멤버 확장(전용 회귀 케이스 고정)**,
typeVariants 회전 0~3(R키), autoPlace/feasibility 변형 탐색, coverage 실풋프린트, generateRoads 전면셀+ringRoad(대안별),
shift+클릭 다중선택→묶기/해제 UX, 렌더 멤버 표시, DXF BLOCK_/멤버 레이어, 멤버 참조 타입 삭제 가드.
selftest 50/50(신규 11), UI 통합 8케이스 통과. 미룬 것: ringRoad UI 노출(Phase 4 corridors와 통합 시), 블록 편집 모드(2b).

원래 계획(참고):

- `kind:'block'` 타입 + placement.members 스냅샷, mask 기반 `fits/buildOccupancy/placementCovers`(WeakMap 캐시 — **직렬화 금지 목록에 등재**)
- `placementGap`(멤버 rect 쌍 최소 거리)으로 rectGap 호출 **전수 치환**(혼용 금지), `expandTargets`(D2)
- **addWouldViolate cand측 멤버 확장** — "GT 멤버 포함 블록을 나중에 놓을 때 기존 Admin의 20m 이격이 뚫리는" 시나리오 전용 회귀 테스트로 고정 (검증 단계에서 최상위 리스크로 지목된 지점)
- coverageOK/layoutMetrics를 실풋프린트 기준으로, generateRoads 전면셀 스캔 교체, 블록 둘레도로(`ringRoad` — **대안별 alt.roads 귀속**, D10)
- UX: 캔버스 다중선택(shift+클릭) → 「블록으로 묶기/해제」(별도 편집기 불필요 — 기존 캔버스·place 툴 재사용), R키 회전, 렌더/DXF 멤버 출력, 멤버 참조 중 타입 삭제 가드
- (2b 선택) 블록 회전 확대 여부는 Phase 0 벤치와 함께 재결정

### Phase 3 — 풍향·특수 규칙·앵커 ✅ 완료 (2026-07-04)

구현·검증 완료: windDir(방위각, 8방위 UI)+ctx.wind(다운윈드 벡터·maxAbs), windSide(hard 반평면+graded soft — Flare
"가장 외곽"이 실제로 외곽에 배치됨을 E2E 확인), centerOf(graded soft 지원), between(중점±반경, 대상 미배치=유보/final=위반),
anchors(도구·목록·이름변경·삭제)+distanceToAnchor(min~max m), 나침반·앵커 마커 렌더, 직렬화·마이그레이션.
selftest 60/60(신규 10), 발전소 축소 시나리오 E2E 9/9(SW풍→Flare NE 외곽, KO 중간, LNG필터 앵커 50m).

원래 계획(참고):

- `windDir` + ctx.wind(투영장) + **`windSide`**(hard 반평면 + graded soft), 나침반 UI
- **`centerOf`**, **`between`**(한계 명시: 대상 이동 시 즉시 차단이 아닌 최종검증 배지 — README·이동 경고로 보완), **`distanceToAnchor`**
- `anchors[{id,name,c,r}]`(Gate·Tie-in 등 사용자 지정점) + 앵커 지정 툴(진입점 툴 패턴 재사용)
- 규칙 모달 kind 4종 추가, ruleToText m 병기

### Phase 4 — 도로 파라미터화·선형 요소·클리어런스 ✅ v1 완료 (2026-07-04)

구현·검증 완료: corridors(rack/tunnel/conduit — 수동 그리기 도구·웨이포인트·rasterizeCenterline 45°지원·목록 UI),
CORRIDOR_KINDS(tunnel=지하 비차단), placeGrid 마스킹 확장 + **edgeDist 'any' 소스 분리 원자 적용**(랙이 nearRoad를
오염하지 않음 — E2E 확인), 전역 클리어런스 매트릭스(카테고리/kind × m, UI 편집, evaluateHard 통합·layoutHardOK 재평가),
buildingTypes.category(건물/장비, 블록 자동), 도로 폭·루프 링 이격(m) 파라미터 + widenNetwork,
networkComponents 폐합/단절 경고, DXF kind 레이어+중심선(_CL) 벡터 출력. selftest 70/70(신규 10), UI 통합 10케이스.

**4b ✅ 완료 (2026-07-04)**: routeCorridor(Dial 버킷 0-1 BFS, 직진 비용 0/회전 페널티 — "최대한 직선" 근사).
자동 라우팅 = 그리기 보조 도구(결과물은 수동 그린 corridor와 동일한 전역 요소 — D10 위반 없음).
UI: 선형 요소 섹션 출발→도착 타입 선택+「라우팅」(블록 멤버 타깃 지원 — GIS→GT승압TR 터널).
통과 정책: 건물·타 차단성 선형 회피, 도로·터널은 횡단 허용. 데모 E2E: PB→CT 랙 28셀 0회전(직선),
GIS→멤버 터널 40셀, 무겹침·연결성·route 스펙 직렬화 확인. selftest 75/75(신규 5).
결정 조정(D9 부분 적용): 자동 도로망은 기존 roadNetwork 필드 유지, corridors는 선형요소 레이어 — 완전 흡수는 후속.

원래 계획(참고):

서브단계 순서 고정(각각 selftest 게이트):
1. **corridors 데이터모델 + roadNetwork 흡수** — "기존 동작 등가" 상태로 먼저 배포(30케이스가 검증)
2. `generateRoadNetwork` opts화(폭 widthM, 루프 링 인셋 ringOffsetM=경계 5m, 간격) + `dilateCells/widenNetwork` — 구형 위치인자 하위호환
3. **clearances 매트릭스 + kind별 거리장 + evaluateHard 통합** — ⚠️ 거리장 소스 분리(D12)와 **원자적으로 동시 적용**(분리 없이 마스킹만 먼저 넣는 단계 분할 금지 — nearRoad 의미 오염)
4. `rasterizeCenterline`(45° 지원, 30/60°는 waypoints 벡터로 기록+셀은 계단 근사) + `routeCorridor`(방향 상태 0-1 BFS, 직진 비용 0/회전 페널티="최대한 직선", 수직 교차 예외) + drawCorridor 툴 + 자동 라우팅(from/to 타입·블록·앵커)
5. **검증 단계 발견 누락 3건 보완**: ① generateRoads 진입로의 랙 클리어런스 인지(진입로가 랙 변을 도로로 오인하지 않도록), ② corridor DXF 레이어 출력(export.js — 30/60° 벡터 폴리라인 포함), ③ **외곽 소방도로 폐합·진입점 접속 검증 리포트**(오목 부지에서 링 단절 감지)

### Phase 5 — Plot plan 번역·데모 시나리오·튜닝 ✅ 완료 (2026-07-04)

구현·검증 완료: demos/lng-ccpp.json — 500×350m 부지 @2m/셀(43.7k셀), 타입 46(블록 3: PB 16멤버·GIS·CT),
규칙 38개(전부 m 단위·xlsx 요구 번역), 앵커 5(Tie-in/정문), 클리어런스 3(도로↔장비/건물/블록 3m),
풍향 SW, 도로 루프 8m/링 5m. 「데모」 버튼(fetch→restore, 무빌드 유지).
E2E: 로드→도로망(68ms)→자동배치 8.7초 **24/24 전량·위반 0** — Flare 다운윈드 최외곽, KO 중간,
Admin 3중 이격, CHEM↔HRSG 멤버 20m(회전 블록에서 정확히 한계값), 앵커·클리어런스 전수 준수. 검증 14/14.
대형 격자 모드 추가: 2만 셀 초과 시 대안 1개 생성·검증 온디맨드(버튼)·어닐링 120회 — UI 블로킹 방지.
튜닝 기록: 송전철탑 "GIS 40m+fence" 교집합 공집합 → hard 120m 완화+soft 60m(원칙: hard 과적 시 soft 강등).

원래 계획(참고):

- 매핑 표(설계 산출물에 25블록 전수 번역표 확보됨) → **`demos/lng-ccpp.json`** (타입 ~30 + 주차 3종, 블록 8, 규칙 ~55, 앵커 5) — import_xlsx.py 초안에서 수동 완성. **원칙 재확인: 이 파일은 데이터. 코드에 어떤 시설물명도 들어가지 않음**
- 툴바 「데모 불러오기」= 정적 JSON fetch→restore (무빌드 유지)
- 시퀀스 튜닝: 블록 선행 배치, hard 과적(Admin 5중 hard) soft 강등 판단, feasibility 100%까지 반복
- **max류 대각선 오차 결정**: rectGap은 체비셰프라 "100m 이내" hard가 대각 실거리 141m를 통과시킴 — 유클리드 rect 거리 도입 여부를 여기서 확정(이격류는 보수적이라 안전)
- E2E: 데모 restore→도로망→autoPlace(시드 고정)에서 unplaced=0·hardViolations=0·clearanceViolations=0
- README: 시나리오 절차 + 미지원 항목 명시

## 4. 커버리지 목표 (xlsx 25블록 기준)

| 구분 | 항목 수 | 대응 |
|---|---|---|
| 현재 규칙으로 표현 가능 | ~15 | 거리범위(m)·인접·세트백·경계인접·수동배치 |
| 이번 확장으로 가능해짐 | ~8 | 블록(PB/GIS/CT/LPG/WT·WWT/Water/AUX/CHEM), 풍향 6건, between(K.O Drum), 앵커(Tie-in/Gate), 도로폭·링인셋, 랙 연결 |
| 명시적 미지원(§7) | 4~5 | 회전반경 18m, 30/60° 정확 표현, 주차 대수→면적 법규 환산, package성 유지보수 도로, CW conduit 단면 검증 |

## 5. 성능 게이트

- cellSize 2m(요구 최소 이격 2.5m 구분에 필요) 시 셀 수 현재 대비 ~25배. Phase 0 벤치 결과에 따라:
  - 통과 시: 그대로 진행
  - 미달 시: 후보 스트라이드/증분 점유맵/어닐링 반복 축소 튜닝을 Phase 2에 편입, 또는 cellSize 2.5m 절충
- Undo 스냅샷(50개)×대형 셀 배열 직렬화 비용 확인 — 필요 시 corridors.cells를 스냅샷에서 제외하고 waypoints 재래스터화

## 6. 직렬화 금지 목록 (파생 캐시 — JSON에 절대 미포함)

mask(WeakMap), compiledRules, placeGrid.ctx(투영장·거리장 TypedArray), kind별 거리장.
serialize 경로 소유: `serialize()`/`migrateState()` 두 함수만 스키마를 안다.

## 7. 명시적 미지원 (억지 구현 금지 — README 고지)

| 항목 | 사유 | 대안 |
|---|---|---|
| 도로 회전반경 18m | 축정렬 격자 모델 밖 | DXF 벡터 출력 후 CAD 후처리 검증 |
| 30/60° 정확 기하 | 〃 | waypoints 벡터 기록 + 셀은 1:2 계단 근사(보수적) |
| 주차 대수→면적 | 법규(차로·장애인 구획) 미반영 | 30m²/대 휴리스틱, 발주처 기준 재확인 문구 |
| "최대한 직선" 전역 보장 | NP성 | 회전 페널티 라우팅 근사 |
| 지하/지상 단면 검증 | 레이어 개념 없음 | tunnel blocks:false + 클리어런스만 |

## 8. 리스크 상위 5 + 완화

1. **placeGrid 마스킹 오염** (rack까지 경계 취급 → nearRoad 오동작): 거리장 소스 분리와 마스킹을 원자적 동시 적용, 분리 selftest("rack 추가 전후 nearRoad 판정 불변")
2. **addWouldViolate 멤버 확장 누락** (블록 후행 배치가 기존 hard 뚫음): Phase 2 전용 회귀 케이스로 고정
3. **성능**: Phase 0 게이트에서 선판정, 미달 시 범위 조정
4. **환산 캐시 stale**: refreshPlacementContext 단일 경로 강제(구조적 봉쇄) — [UI 검증 교훈]과 동일 계열
5. **hard 과적으로 feasibility 전멸**: 데모 튜닝에서 soft 강등 기준 수립, 배치 거부 힌트에 "어느 규칙·몇 m 부족" 표기

## 9. 테스트 계획

- 기존 30케이스 무회귀가 모든 Phase의 게이트 (엔진 셀 계약·시드 재현성 불변이 안전망의 전제)
- Phase별 신규: 환산 정책표·마이그레이션 왕복(P1), 블록 mask/멤버타깃/역방향(P2), 풍향 반평면·graded/between/anchor(P3), 거리장 분리·클리어런스·라우팅·소방도로 폐합(P4), 데모 E2E·v1 스냅샷 봉인(P5) — 합계 +약 45케이스
