# Weekly Progress Email Draft: Layout Automation – Phase 06 Engine (May Week 4)
Date: May 22, 2026

### 🇬🇧 English Version (이메일 영문 버전)

Subject: Weekly Update: Layout Automation Enhancements (May Week 4)

Dear Team,

Here are this week's updates for the Layout Automation system. We updated the system using the requirements provided via email.

This Week's Core Updates:

1. Phase 06 Grid Engine: Completed Steps 1.1 through 1.6 to place buildings on a 2m grid with 16m block gaps and 8m road setbacks
2. Fire Road Network: Implemented PB Ring Road and Perimeter Fire Road as placement exclusion zones
3. Obstacle-Avoiding Stub Connections: Generated obstacle-avoiding connection roads from each building to the fire road network
4. 2-Path Verification & Pruning: Computed two shortest paths to the Gate for each building and automatically pruned unused road segments
5. Pipe Rack Algorithm Design: Designed orthogonal routing logic for the 6m-wide pipe rack connecting 5 process buildings
6. Interactive Visual Dashboard: Added raw stubs, pruned segments, kept roads, and per-building path trace overlays

Next Week's Plan:
Implement the Pipe Rack algorithm in code
Step 2 preparation: building subdivision within blocks

Please let me know if you have any questions.

Best regards,

Daria
Manager | CST Team

Sangsang Jinwha Co., Ltd.
Phone: +82-2-3474-2263  |  Mobile: +82-10-8420-2280


### 🇰🇷 Korean Version (이메일 국문 버전)

제목: 주간 보고: 레이아웃 자동화 프로젝트 업데이트 사항 (5월 4주차)

안녕하세요!

이번 주 진행한 레이아웃 자동화 시스템 개선 사항을 공유해 드립니다.

주요 업데이트 내용:

1. Phase 06 그리드 엔진: 10개 건물에 대해 16m 건물 간격 및 8m 도로 이격을 적용한 2m 스냅 그리드 기반 자동 배치 로직 구현
2. 소방도로 네트워크: 파워블록 링 도로 및 외곽 소방도로 생성 후 건물 배치 제외 영역 지정
3. 장애물 회피 스텁 연결: 각 건물에서 소방도로망으로 이어지는 최단 거리 우회 연결 도로 생성
4. 2경로 검증 및 가지치기: 건물별 게이트 향 2개 경로 계산 후 짧은 경로 유지 및 미사용 도로 구간 자동 제거
5. 파이프 랙 알고리즘 설계: 5개 주요 공정 건물을 연결하는 6m 파이프 랙 직교 라우팅 방식 알고리즘 설계
6. 인터랙티브 시각 대시보드: 미사용 도로 및 유지된 소방도로망 확인을 위한 경로 추적 오버레이 레이어 기능 추가

다음 주 계획:
파이프 랙 알고리즘 개발 적용
블록 내부 개별 건물 세분화 로직 준비

문의 사항이 있으시면 편하게 말씀해 주세요.

감사합니다.

다리아
매니저 | CST팀 

(주) 상상진화 
전화: 02-3474-2263  |  휴대폰: 010-8420-2280
