# ⚖️ 룰 엔진: 페널티 점수 산정 로직

이 문서는 모든 레이아웃 규칙에 대한 **단일 진실 공급원(Single Source of Truth)** 입니다.
생성형 디자인 시스템은 **총 페널티 점수(Total Penalty Score)** 를 계산하여 레이아웃을 평가합니다.
*점수가 낮을수록 = 더 좋은 레이아웃.*
점수 `0`은 규칙 위반이 전혀 없는 완벽한 레이아웃을 의미합니다.

## 📖 사용 가능한 규칙 유형

각 규칙에는 `Rules.py`의 일반 평가자(evaluator) 함수에 매핑되는 **규칙 유형(Rule Type)** 이 있습니다.

| 규칙 유형              | Rules.py의 함수              | 검사 항목                                         | 페널티 모드   |
| :-------------------- | :-------------------------- | :----------------------------------------------- | :----------- |
| `center_proximity`    | `_eval_center_proximity()`  | 건물 중심에서 부지 중심까지의 거리                  | Linear       |
| `boundary_setback`    | `_eval_boundary_setback()`  | 모든 모서리에서 부지 경계까지의 최소 거리            | Flat         |
| `windward_edge`       | `_eval_windward_edge()`     | 건물이 부지의 바람 부는 쪽(풍상측)에 있는가?         | Flat         |
| `min_distance`        | `_eval_min_distance()`      | 중심 간 거리가 임계값 이상이어야 함                  | Linear       |
| `max_distance`        | `_eval_max_distance()`      | 중심 간 거리가 임계값 이하여야 함                    | Linear       |
| `leeward_edge`        | `_eval_leeward_edge()`      | 건물이 바람 받는 쪽(풍하측)에 있는가?                | Flat         |
| `rack_length`         | `_eval_rack_length()`       | 연결된 두 건물 간의 모서리 간 거리                   | Linear       |
| `pipe_rack_proximity` | `_eval_pipe_rack_proximity()` | 건물 모서리에서 가장 가까운 랙 라인까지의 거리      | Linear       |

**페널티 모드:**
- **Linear** = `초과량 또는 부족량 × 페널티 비율` (위반 정도에 비례)
- **Flat** = 위반 시 `페널티 비율` 1회 적용 (이진 합/불 판정)

---

## 🏗️ Phase 03: 3대 거인(The Three Giants) (6개 규칙)

| ID        | 그룹             | 규칙 유형              | 대상             | 임계값  | 페널티             | 조건                 |
| :-------- | :------------- | :----------------- | :------------- | :--- | :-------------- | :----------------- |
| **PB-01** | Power Block    | `center_proximity` | 부지 중심          | 20 m | 100 pts / m     | 20 m 초과 시에만 적용     |
| **PB-02** | Power Block    | `boundary_setback` | 주 도로           | 5 m  | 5000 pts (flat) | 어떤 모서리든 5 m 미만이면   |
| **CT-01** | Cooling Tower  | `leeward_edge`     | 풍향             | 30 m | 1000 pts (flat) | 반드시 **풍하측**에 있어야 함 |
| **CT-02** | Cooling Tower  | `min_distance`     | Admin Building | 50 m | 500 pts / m     | 거리가 50 m 미만일 때     |
| **AD-01** | Admin Building | `boundary_setback` | 주 도로           | 20 m | 1000 pts (flat) | 어떤 모서리든 20 m 미만이면  |
| **AD-02** | Admin Building | `max_distance`     | Gate House     | 50 m | 100 pts / m     | 거리가 50 m 초과일 때     |
| **AD-03** | Admin Building | `windward_edge`    | 풍향             | 30 m | 1000 pts (flat) | 반드시 **풍상측**에 있어야 함 |

---

## 🔧 Phase 04: 새로운 그룹 (확장 규칙)

### 새로운 사각형 그룹

| ID        | 그룹                 | 규칙 유형              | 대상             | 임계값   | 페널티             | 조건                 |
| :-------- | :----------------- | :----------------- | :------------- | :---- | :-------------- | :----------------- |
| **GH-01** | Gate House User 지정 | `boundary_setback` | 주 도로           | 0 m   | 5000 pts (flat) | 반드시 부지 경계에 위치해야 함  |
| **LP-01** | LPG/MeteringXXX    | `boundary_setback` | 주 도로           | 10 m  | 1000 pts (flat) | 경계로부X터 이격          |
| **LP-02** | LPG/MeteringXXX    | `min_distance`     | Power Block    | 30 m  | 300 pts / m     | PB로부터 안전 거리        |
| **FL-01** | Flare              | `leeward_edge`     | 풍향             | 30 m  | 1000 pts (flat) | 반드시 **풍하측**에 있어야 함 |
| **FL-02** | Flare              | `min_distance`     | Admin Building | 100 m | 500 pts / m     | Admin으로부터 안전 거리    |
| **FL-03** | Flare              | `min_distance`     | Power Block    | 50 m  | 300 pts / m     | PB로부터 안전 거리        |
| **WW-01** | WT/WWT             | `boundary_setback` | 주 도로           | 10 m  | 1000 pts (flat) | 경계로부터 이격           |
| **WW-02** | WT/WWT             | `leeward_edge`     | 풍향             | 50 m  | 500 pts (flat)  | 반드시 **풍하측**에 있어야 함 |
| **WA-01** | Water              | `boundary_setback` | 주 도로           | 10 m  | 1000 pts (flat) | 경계로부터 이격           |
| **WA-02** | Water              | `min_distance`     | WT/WWT         | 10 m  | 200 pts / m     | 수처리 시설 인근          |
| **WA-03** | Water              | `max_distance`     | WT/WWT         | 80 m  | 100 pts / m     | WWT로부터 너무 멀면 안 됨   |
|           | tank 3EA           |                    |                |       |                 |                    |
|           | Warehouse          |                    |                |       |                 |                    |
|           | 전기                 |                    |                |       |                 |                    |
|           |                    |                    |                |       |                 |                    |

### 폴리라인 랙 — 연결 맵

랙은 건물을 연결하는 배관/케이블 통로입니다. **짧을수록 좋음.**

| 랙                | 폭   | 용도                        | 연결                                                                            |
| :--------------- | :-- | :------------------------ | :---------------------------------------------------------------------------- |
| **Pipe Rack**    | 6 m | 공정 배관 (냉각수, 연료가스, 증기/응축수) | Power Block ↔ Cooling Tower, Power Block ↔ LPG/Metering, Power Block ↔ WT/WWT |
| **Main Rack**    | 8 m | 전기 케이블 + 제어 신호            | Power Block ↔ Admin Building                                                  |
| **Utility Rack** | 6 m | 유틸리티 서비스 (원수, 소화수, 보충수)   | WT/WWT ↔ Water, WT/WWT ↔ Cooling Tower                                        |
| **Cable Tunnel** | 3 m | 지하 케이블 경로                 | Powerplan  전기                                                                 |

### 랙 길이 규칙

규칙: 각 연결은 가능한 짧아야 합니다. 페널티 = `랙 길이 × 페널티 비율`.

| ID        | 랙            | 규칙 유형         | 건물 A        | 건물 B           | 페널티        | 조건               |
| :-------- | :----------- | :------------ | :---------- | :------------- | :--------- | :--------------- |
| **PR-01** | Pipe Rack    | `rack_length` | Power Block | Cooling Tower  | 50 pts / m | 짧을수록 좋음 (냉각수)    |
| **PR-02** | Pipe Rack    | `rack_length` | Power Block | LPG/Metering   | 30 pts / m | 짧을수록 좋음 (연료가스)   |
| **PR-03** | Pipe Rack    | `rack_length` | Power Block | WT/WWT         | 30 pts / m | 짧을수록 좋음 (탈염수)    |
| **MR-02** | Main Rack    | `rack_length` | Power Block | Admin Building | 20 pts / m | 짧을수록 좋음 (제어 케이블) |
| **UR-01** | Utility Rack | `rack_length` | WT/WWT      | Water          | 40 pts / m | 짧을수록 좋음 (원수)     |
| **UR-02** | Utility Rack | `rack_length` | WT/WWT      | Cooling Tower  | 30 pts / m | 짧을수록 좋음 (보충수)    |

---

*새 규칙 추가 방법: 이 표에 행을 추가한 후, `Core/Rules.py`의 `RULES` 리스트에 일치하는 dict를 추가하세요.*

---

## 사용자 입력 대기 중

- [ ] **1) 건물 크기** — 각 그룹별 치수 확정 또는 업데이트
- [ ] **2) 랙 연결** — 임시 정의 완료: 3개 랙, 7개 연결 (위 랙 연결 맵 참조) -> 상세 연결 필요
- [ ] **3) 배치 우선순위** — 중요도순 건물 목록 (먼저 배치 = 최우선순위)
- [ ] **4) 수동 배치 목록** — 사용자가 직접 배치하는 건물 (자동 생성 제외)


Gate, Wind -> Rack, Road  + added buildings -> need to compare

