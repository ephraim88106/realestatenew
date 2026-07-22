# 동네별 톱10 객관적 재작성 — 진행 상황

이 파일은 각 동의 아파트 톱10 데이터를 국토부 실거래 기준으로 전수조사해서
재작성했는지 추적하는 용도입니다. 매일 예약 작업(scheduled task)이 이 파일을
읽고 다음 순서의 동을 처리한 뒤, 완료 표시를 갱신하고 커밋합니다.

## 처리 순서 및 상태

- [x] 연수구 송도동 — lawd 28185, umd 송도동 — data/incheon/yeonsu/songdo.json (2026-07-22 완료, 커밋 9f39630)
- [ ] 남동구 논현동 — lawd 28200, umd 논현동 — data/incheon/namdong/nonhyeon.json
- [ ] 부평구 삼산동 — lawd 28237, umd 삼산동 — data/incheon/bupyeong/samsan.json
- [ ] 계양구 작전동 — lawd 28245, umd 작전동 — data/incheon/gyeyang/jakjeon.json
- [ ] 서해구 청라동 — lawd 28260, umd 청라동 — data/incheon/seo/cheongna.json
- [ ] 검단구 검단신도시 — lawd 28260, umd 확인 필요(대곡동/원당동 인근일 수 있음, umd 없이 받아서 지번으로 판별) — data/incheon/seo/geomdan.json
- [ ] 검단구 아라동 — lawd 28260, umd 아라동 — data/incheon/seo/ara.json
- [ ] 검단구 원당동 — lawd 28260, umd 원당동 — data/incheon/seo/wondang.json
- [ ] 미추홀구 용현동 — lawd 28177, umd 용현동 — data/incheon/michuhol/yonghyeon.json
- [ ] 중구 운서동 — lawd 28110, umd 운서동 — data/incheon/jung/unseo.json

## 작업 방법론 (2026-07-22 송도동 작업에서 확립, 매회 동일하게 적용)

1. **사전 점검**: `functions/api/trade.js`가 정상 동작하는지 확인
   (`/api/trade?LAWD_CD=<lawd>&DEAL_YMD=<최근월>&raw=1&_cb=<캐시버스터>` 호출 후
   items의 apt/umd 필드가 빈 문자열이 아닌지 확인 — Cloudflare 엣지 캐시가
   있으므로 캐시버스터 쿼리 파라미터를 매번 다르게 줄 것).

2. **전체 단지 목록 확보**: 나무위키 "공동주택/목록/<구>" 문서(또는 동급 자료)를
   WebFetch해서 대상 동에 있는 모든 아파트 단지(세대수·층수 포함)를 빠짐없이
   추출. 최소 300세대 이상인 단지는 전부 후보로 포함.

3. **실거래 데이터 확보**: `/api/trade?LAWD_CD=<lawd>&months=12&raw=1&_cb=<버스터>`
   로 최근 12개월 실거래를 받아서 umd로 대상 동만 필터링. 단지명(MOLIT
   등록명)별로 그룹핑해서 82~90㎡(84타입) 실거래 중앙값, 최빈 buildYear
   (준공년도), 거래건수를 계산. 이 값이 세대수·시세·준공년도의 1차 근거.

4. **세대수 교차검증**: 나무위키 세대수와 국토부 buildYear가 기존 JSON
   데이터와 다르면 실거래/나무위키 쪽을 신뢰하고 기존 값을 정정 (송도동
   작업에서 세대수가 다른 단지와 뒤바뀐 오류가 실제로 있었음 — 항상 의심할 것).

5. **예비 점수로 후보 압축**: 시세(45%)+신축(10%)+규모(10%) = 65%만 먼저
   계산해서 상위 15~18개로 후보를 좁힘 (입지·학군 조사는 비용이 크므로).

6. **병렬 조사**: Agent 도구로 후보 단지 각각에 대해 역세권 도보시간, 배정
   초·중학교 및 거리, 생활 인프라(마트·상권), 호재·리스크를 조사 (한 번에
   여러 Agent를 동시 호출). 결과를 바탕으로 입지(ipji)·학군(hakgun) 점수를
   0~100로 매기되, 전체 후보에 일관된 기준(도보시간 구간, 학교 거리 구간)을
   적용할 것 — 이미 있는 동 데이터의 점수 분포를 참고해서 스케일을 맞출 것.

7. **최종 점수 계산 및 톱10 선정**: 기존 weights(sise 45·ipji 20·hakgun 15·
   sinchuk 10·gyumo 10)를 그대로 적용해서 최종 톱10 확정.

8. **JSON 재작성**: 기존 스키마(id/name/brand/year/households/floors/ipji/
   hakgun/sizes[]/transit/school/mart/hojae[]/risk[]/desc{sise,ipji,hakgun})를
   그대로 유지해서 해당 동 JSON 파일을 통째로 재작성. ask/kb는 real 기준
   +7%/-4% 정도로 추정하고 verified:false로 표시.

9. **커밋 메시지 규칙**: `feat: <동이름> 톱10 전면 재작성 - 실거래 데이터 기반 객관적 재산정`
   형식으로 커밋 (이 파일을 파싱해서 진행 상황을 추적하는 그 어떤 자동화도
   없지만, 사람이 git log로 훑어볼 때 알아보기 쉽게).

10. **이 진행 상황 파일 갱신**: 처리한 동의 체크박스를 `[x]`로 바꾸고 완료
    날짜·커밋 해시를 적어서 같은 커밋 또는 바로 다음 커밋으로 push.

11. **로컬 동기화**: 완료된 JSON 파일과 이 진행 상황 파일을 SendUserFile +
    device_commit_files로 `D:\2026 남호\desktop\realestatenew\...`에도 반영.

12. **GitHub 인증**: PAT는 프로젝트 컨텍스트(사용자명 ephraim88106, 이메일
    namho1123@gmail.com)에 있음 — `git clone https://<username>:<PAT>@github.com/ephraim88106/realestatenew.git`
    형식으로 클론해서 작업.

## 주의사항

- 검단구 3개 동(검단신도시·아라동·원당동)은 lawd가 모두 28260으로 서해구
  청라동과 동일함(법정구역상 서구로 묶여 있어서). umd 필터로 구분해야 함.
  검단신도시는 특정 법정동명이 아닐 수 있으니, 실거래 응답의 지번/umd를
  보고 검단신도시 권역(예: 원당동·마전동·불로동 등 검단 신축 택지지구)에
  해당하는지 직접 판별이 필요할 수 있음.
- 한 번에 하루 1개 동만 처리. 절대 여러 동을 한 번에 몰아서 하지 말 것
  (각 동마다 충분한 조사 시간이 필요하고, 리뷰 없이 대량으로 밀어붙이면
  송도동에서처럼 오류가 반복될 수 있음).
- 모든 9개 동이 완료되면(체크박스 전부 [x]) 이 예약 작업은 스스로 종료해도
  됨 — mcp__claude-code-remote__list_triggers로 이 작업의 trigger_id를 찾아
  update_trigger(enabled:false)로 비활성화할 것.
