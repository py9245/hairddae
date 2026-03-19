# 심미진 Week3 Report

## 260317

> 별도 Jira Task 없음

- 인증 화면 UI 정리
  - Login, SignUp 화면 레이아웃 간소화
  - `index.css` CSS 추가, router 경로 정리
  - Login/SignUp 레이아웃 구조 개선
  - `not-found-page.tsx` 리팩토링
  - router 정리

- GitLab CI에 Gemini 자동 코드 리뷰 봇 추가 시도(실패)
  - `scripts/gemini_review.py` 신규 작성
  - `.gitlab-ci.yml` job 설정
  - `.gitlab-ci.yml` stages 6개 추가
  - 관련 문서: [Gemini Code Review Bot 도입 시도_심미진](https://docs.google.com/document/d/1_JpmzEWJPCrzGjLolPcy1Co9Fx-DfObEJiYSuC0BRgw/edit?usp=sharing)

- storybook 정리 정돈
    - Storybook deprecated 필드 제거
    - `BirthDatePicker` 컴포넌트 신규 생성
    - `SignUp.tsx` 나이 필드 → 생년월일 필드로 교체
        - Input Storybook 스토리를 birthDate 필드에 맞게 수정
        - Input Storybook 시나리오 추가
        - Input Storybook play 함수 수정
    - 파일명 PascalCase → kebab-case 일괄 변경
        - `Camera.tsx` → `camera.tsx`, `SignUp.tsx` → `sign-up.tsx` 등
        - 파일명 변경에 따른 import 경로 수정
    - Splash 화면을 router에서 독립 파일(`splash.tsx`)로 분리
    - HairApplyModal UI 스타일 업데이트
    - AGENTS.md 업데이트
    - BottomNav, HairChangeModal 스토리 정리

