
# 🚀 제품 비전: PowerPlan AI (Layout_Gen_Design)

**프로젝트 목표:**

발전소 배치도(Plot Plan) 생성 자동화. 엔지니어링 제약 조건과 규칙에 기반하여 부지 위 60개 이상의 건물 배치를 최적화하는 시스템을 개발한다.

## 🛠 기술 스택 (Vibe Coding)

- **아키텍트 (조직화):** Obsidian
- **엔진 (IDE):** VS Code + Antigravity 확장 프로그램
- **제도공 (시각화):** Matplotlib (Python 라이브러리)
- **인터페이스 (대시보드):** Streamlit (웹 UI)
- **언어:** Python


## 🎯 주요 기능

1. **인터랙티브 부지 설정:** 대시보드의 슬라이더를 사용하여 부지 경계(a × b) 정의.
2. **스마트 그룹화:** 규칙에 따라 주요 클러스터(Power Block, Cooling Tower, Admin) 배치.
3. **자동 점수 산정:** 거리에 대한 실시간 검증 (예: "Admin은 Cooling Tower로부터 50m 떨어져야 함").
4. **생성형 레이아웃:** 다수의 반복 실행을 통해 가장 높은 점수의 최적 배치를 찾기.


## 📈 개발 로드맵 (단계별 계획)

### Phase_01: 빈 부지 (완료)

- [x] 프로젝트 구조 초기화: `Core/`, `Dashboard/`, `Data/`, `Notes/`.
- [x] Streamlit을 사용해 `Dashboard/App.py` 설정.
- [x] 사용자 입력에 기반한 부지 경계(사각형) 그리기.

### Phase_02: 3대 거인 (완료)

- [x] 3개 주요 그룹 정의: **Power Block**, **Cooling Tower**, **Admin Building**.
- [x] 부지 내부에 색상 블록으로 렌더링.
- [x] 캔버스 한계 테스트를 위한 수동 X/Y 좌표 슬라이더 추가.

### Phase_03: 엔지니어링 규칙 (완료)

- [x] 엑셀 규칙을 `Core/Rules.py`의 Python 함수로 변환.
- [x] 거리 검사 구현 (경계로부터의 이격 및 건물 간 이격).
- [x] 시각적 경고: 규칙 위반 시 블록을 **빨간색**으로 표시.

### Phase_04: 새로운 그룹, 일반 규칙 및 규칙 네트워크

- [x] 3개 → **12개 그룹**으로 확장: Power Block, Cooling Tower, Admin Building, Gate House, Cable Tunnel, LPG/Metering, Flare, WT/WWT, Water + 3개 폴리라인 랙(Pipe Rack, Main Rack, Utility Rack).
- [x] **일반 룰 엔진:** 6개의 수동 코딩된 규칙 함수를 `RULES` 데이터 리스트 + **규칙 유형(Rule Type)** (`min_distance`, `max_distance`, `center_proximity`, `boundary_setback`, `windward_edge`, `pipe_rack_proximity`)으로 디스패치되는 일반 평가자(generic evaluators)로 대체.
- [x] `!Scoring_Logic.md`에 **규칙 유형(Rule Type)** 열 추가 — 각 행은 `Rules.py`의 `RULES` 리스트의 dict와 1:1로 매핑됨.
- [x] **폴리라인 랙:** Pipe Rack, Main Rack, Utility Rack을 직선(사각형 아님)으로 렌더링.
- [x] **규칙 네트워크 시각화 도구:** **Pyvis**를 사용한 독립형 `Notes/Rule_Network.html` — 모든 그룹(노드)과 규칙(엣지)을 보여주는 인터랙티브 물리 기반 그래프. `Core/RuleNetwork.py`에 의해 생성됨.
- [x] 12개 그룹을 모두 배치하도록 생성형 엔진 업데이트.

### Phase_05: 고급 라우팅 및 순차 배치

- [ ] **도로 추가:** Primary Road(외곽 순환 도로, 5m 이격) 및 Inner Road(Power Block 주변) 구현.
- [ ] **대시보드 인터페이스:** 시각적 레이아웃 및 컨트롤 업데이트.
- [ ] **고급 랙 로직:** 1개의 랙이 여러 건물을 연결하는 메인 척추(spine) 역할을 하도록 랙 라우팅 리팩토링.
- [ ] **계층적 배치 로직:** Power Block 앵커링부터 시작하여 3개의 메인 블록을 순차적으로 배치하도록 레이아웃 생성기 변경.
- [ ] **규칙 네트워크:** `RuleNetwork.py` 및 `Rule_Network.html` 업데이트 중단 (Phase 05 이후로는 더 이상 필요하지 않음).
- [ ] **건물 회전:** 생성형 엔진에 건물 회전 무작위화 추가.

## 📍 현재 상태: **Phase_04 완료, Phase_05로 이동 (생성형 최적화 및 서브 클러스터)**
