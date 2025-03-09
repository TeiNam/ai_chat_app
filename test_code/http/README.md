# AI 챗봇 API 테스트

이 디렉토리는 AI 챗봇 API의 테스트 코드와 HTTP 요청 파일을 포함합니다.

## 디렉토리 구조

```
test_code/
│
├── conftest.py               - 공통 테스트 픽스처
│
├── test_auth_api.py          - 인증 API 테스트
├── test_user_api.py          - 사용자 API 테스트
├── test_health_api.py        - 헬스 체크 API 테스트
│
└── http/                     - HTTP 요청 파일 (REST 클라이언트용)
    ├── auth.http             - 인증 관련 요청
    ├── user.http             - 사용자 관련 요청
    └── health.http           - 헬스 체크 요청
```

## 테스트 실행 방법

### pytest를 사용한 테스트 실행

```bash
# 모든 테스트 실행
pytest test_code/ -v

# 특정 테스트 파일 실행
pytest test_code/test_auth_api.py -v
pytest test_code/test_user_api.py -v
pytest test_code/test_health_api.py -v
```

### HTTP 요청 파일 사용 방법

HTTP 요청 파일(.http)은 VSCode의 REST Client 확장 프로그램이나 IntelliJ IDEA의 HTTP Client 기능으로 실행할 수 있습니다.

1. VSCode에 REST Client 확장 프로그램 설치
2. `.http` 파일을 열고 각 요청 위의 `Send Request` 링크 클릭
3. 응답은 새 탭에 표시됨

## 테스트 사용자 설정

테스트를 실행하기 전에 다음 설정이 필요합니다:

1. 데이터베이스에 테스트 사용자 생성
2. `conftest.py`와 HTTP 파일에 있는 이메일/비밀번호 업데이트

## 주의사항

- 테스트는 실제 DB에 접근하므로 테스트용 DB를 사용하는 것이 좋습니다.
- 이메일 인증 과정을 포함한 일부 기능은 통합 테스트 환경에서 추가 설정이 필요할 수 있습니다.
- API 응답이 변경되면 테스트 코드도 업데이트해야 합니다.