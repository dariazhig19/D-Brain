# Weekly Progress Email Draft: Layout Automation – Phase 06 Engine (May Week 4)
Date: May 22, 2026

---

### 🇬🇧 English Version (이메일 영문 버전)

Subject: Weekly Update: Phase 06 Grid-First Generative Layout Engine (May Week 4)

Dear Team,

Here are this week's updates for the Layout Automation system. The focus was on building the Phase 06 "infrastructure-first" generative design engine — a complete rewrite of the layout generator that places roads before buildings, then verifies access paths.

This Week's Core Updates:

1. Phase 06 Grid Engine (Core/Layout06.py, ~925 lines):
   Completed Steps 1.1 through 1.6. All 10 facility blocks are now placed on a 2m snapped grid with dual buffer enforcement: 16m block-to-block gap + 8m road-centerline setback.

2. Fire Road Network:
   Implemented PB Ring Road (9m offset from Power Block face), Perimeter Fire Road (9m from site boundary), Gate Spur (boundary → perimeter road connection), and Ring Spur (ring road → perimeter road connection). All road corridors act as placement exclusion zones during block generation.

3. Obstacle-Avoiding Stub Connections (Step 1.4):
   Each block now gets two A*-routed connection stubs — one to the PB Ring Road, one to the Perimeter Road. Stubs are axis-aligned, route around other blocks, and snap to the 2m grid.

4. 2-Path Verification & Pruning (Steps 1.5-1.6):
   Built a NetworkX road graph from all fire road segments + stubs. For each block, two candidate paths to the Gate are computed; only the shorter path is kept. Unused road segments are automatically pruned. Remaining edges are classified as Primary (fire road, 8m) or Secondary (stub, 6m).

5. Pipe Rack Algorithm Design (Step 1.2-RACK):
   Designed the rack placement algorithm for the 6m-wide pipe rack connecting 5 process blocks (PB, CT, WT/WWT, RAW Water, Demi Water). Uses randomized Case 1/Case 2 buffer selection and orthogonal spine routing. Updated Phase_06_Plan.md with full specification.

6. Dashboard Visualization (Dashboard/Roads_Test.py):
   Updated to show raw stubs, pruned segments (red), kept fire + secondary roads, and per-block 2-path trace overlays. Added toggle controls and per-block path length statistics.

Next Week's Plan:
- Implement the Pipe Rack algorithm (Step 1.2-RACK) in code
- Step 2 preparation: building subdivision within blocks

Please let me know if you have any questions.

Best regards,

Daria
Manager | CST Team

Sangsang Jinwha Co., Ltd.
Phone: +82-2-3474-2263  |  Mobile: +82-10-8420-2280

---

### 🇰🇷 Korean Version (이메일 국문 버전)

제목: 주간 보고: Phase 06 그리드 기반 레이아웃 자동 생성 엔진 (5월 4주차)

안녕하세요!

이번 주 레이아웃 자동화 시스템 개선 사항을 공유해 드립니다. 이번 주에는 도로를 건물보다 먼저 배치하는 "인프라 우선" Phase 06 생성 엔진을 완성하는 데 집중했습니다.

주요 업데이트 내용:

1. Phase 06 그리드 엔진 (Core/Layout06.py, 약 925줄):
   Step 1.1~1.6 완성. 10개 시설 블록이 2m 스냅 그리드 위에 배치되며, 블록 간 16m 이격 + 도로 중심선 8m 이격 이중 버퍼 적용.

2. 소방도로 네트워크:
   PB 링 도로(파워블록 면에서 9m 오프셋), 외곽 소방도로(부지 경계에서 9m), 게이트 스퍼(경계→외곽도로 연결), 링 스퍼(링 도로→외곽도로 연결) 구현. 모든 도로 구간이 블록 배치 시 제외 영역으로 작동.

3. 장애물 회피 스텁 연결 (Step 1.4):
   각 블록이 PB 링 도로와 외곽 소방도로에 각 1개씩 A* 경로탐색 기반 연결 스텁을 생성. 축 정렬 직교 경로, 다른 블록 자동 우회, 2m 그리드 스냅.

4. 2경로 검증 및 가지치기 (Steps 1.5-1.6):
   NetworkX 도로 그래프 구축 후 각 블록의 게이트까지 2개 후보 경로를 계산하여 짧은 경로만 유지. 미사용 도로 구간 자동 제거. 남은 구간을 주도로(소방도로 8m) / 보조도로(스텁 6m)로 분류.

5. 파이프 랙 알고리즘 설계 (Step 1.2-RACK):
   5개 공정 블록(PB, CT, WT/WWT, RAW Water, Demi Water)을 연결하는 6m 파이프 랙 배치 알고리즘 설계. Case 1/Case 2 랜덤 버퍼 선택 및 직교 스파인 라우팅 방식. Phase_06_Plan.md에 전체 사양 문서화 완료.

6. 대시보드 시각화 (Dashboard/Roads_Test.py):
   원시 스텁, 가지치기 구간(빨간색), 유지된 소방도로 + 보조도로, 블록별 2-경로 추적 오버레이 표시. 토글 컨트롤 및 블록별 경로 길이 통계 추가.

다음 주 계획:
- 파이프 랙 알고리즘 (Step 1.2-RACK) 코드 구현
- Step 2 준비: 블록 내부 건물 세분화

문의 사항이 있으시면 편하게 말씀해 주세요.

감사합니다.

다리아
매니저 | CST팀

(주) 상상진화
전화: 02-3474-2263  |  휴대폰: 010-8420-2280
