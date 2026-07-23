# 설치 및 구성

## 한 문장으로 설치하기

아래 문장을 agent에게 보내 설치를 맡기는 방법을 권장합니다.

```text
image-to-editable-ppt skill을 설치해 주세요. 주소는 https://github.com/ningzimu/image-to-editable-ppt-skill 입니다.
```

설치 후 일반 변환, 이미지 API 폴백, OCR Token 설정은 AI가 실행 중 확인하고 처리합니다. AI가 요청할 때 타사 API 정보나 OCR Token만 제공하면 됩니다.

## 수동 설치

[GitHub Releases](https://github.com/ningzimu/image-to-editable-ppt-skill/releases)에서 `image-to-editable-ppt-skill-v*.zip`을 내려받아 압축을 풉니다. 그 안의 `image-to-editable-ppt` 폴더를 agent의 skills 디렉터리(Codex는 `~/.codex/skills/image-to-editable-ppt`)에 넣고 agent를 다시 시작하세요.

이 저장소를 로컬에서 개발하는 경우 skill 디렉터리를 skills 디렉터리에 심볼릭 링크해 변경 사항을 실시간으로 테스트할 수 있습니다.

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/image-to-editable-ppt-skill/skills/image-to-editable-ppt ~/.codex/skills/image-to-editable-ppt
```

## skill 업데이트

아래 문장을 agent에게 보내 업데이트를 맡기는 방법을 권장합니다.

```text
image-to-editable-ppt skill을 업데이트해 주세요. 주소는 https://github.com/ningzimu/image-to-editable-ppt-skill 입니다.
```

수동으로 업데이트하려면 [GitHub Releases](https://github.com/ningzimu/image-to-editable-ppt-skill/releases)에서 최신 zip을 내려받아 압축을 풀고 기존 `image-to-editable-ppt` 디렉터리를 교체하세요. 업데이트 후 agent를 다시 시작하면 적용됩니다.

업데이트는 안전합니다. 이미지 API 자격 증명과 OCR Token은 skill 설치 디렉터리 밖의 `~/.editppt/config.yaml`(Windows에서는 `%USERPROFILE%\.editppt\config.yaml`)에 저장되므로 업데이트하거나 다시 설치해도 사라지지 않습니다. 각 버전의 변경 사항은 [Releases 페이지](https://github.com/ningzimu/image-to-editable-ppt-skill/releases) 또는 저장소의 `CHANGELOG.md`에서 확인할 수 있습니다.

## 실행 권한 권장 사항

**Codex에서 이 skill을 실행할 때는 “전체 액세스 권한” 사용을 권장합니다.**

이 skill은 실행 시간이 길며 OCR, 이미지 생성/편집, 파일 읽기·쓰기, 하위 agent 분배, 장시간 폴링 등의 단계를 자동으로 수행합니다. “승인 요청” 모드는 실행을 자주 중단해 일부 단계를 막을 수 있으며, 특히 하위 agent 환경에서 문제가 될 수 있습니다. “대신 승인” 모드도 OCR이나 이미지 생성/편집 또는 타사 API 호출 단계에서 요청을 차단하고 수동 승인을 요구할 수 있습니다. 사용자가 컴퓨터 앞에 없으면 변환 흐름이 멈출 수 있습니다.

![Codex 전체 액세스 권한 설정 예시](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/codex-full-access-permission.png)

## 실행 요구 사항

- 단일 페이지/이미지 입력은 page worker를 만들 필요가 없으며 메인 agent가 동일한 페이지 재구성 흐름을 로컬에서 수행합니다.
- 다중 페이지 입력은 agent가 page worker/subagent를 분배할 수 있어야 합니다. 현재 환경에서 page worker를 만들 수 없다면 지원되는 환경에서 실행해야 합니다.
- 이 skill이 의존하는 `editppt` 명령줄 도구는 AI가 skill 실행 과정에서 자동으로 설치하므로 사용자가 명령을 직접 실행할 필요가 없습니다.
- 모델의 기본 이해 능력과 skill 준수 능력에 따라 gpt-5.5 미만 모델의 사용 결과는 보장하지 않습니다.

## OCR Token(권장 구성)

이 skill은 타사 OCR 서비스(바이두 PaddleOCR-VL)로 텍스트 상자 좌표, 글자 크기, 크기 그룹을 보정해 텍스트 복원 품질을 크게 높입니다. 원리는 [설계 철학](/ko/design.md)을 참고하세요.

**사용자가 할 일은 Token 신청 하나뿐입니다.** 바이두 AI Studio에서 Access Token을 신청하세요: <https://aistudio.baidu.com/account/accessToken>. 개인 사용의 경우 현재 무료 할당량으로 충분하며 추가 비용이 없습니다.

최초 사용 시 Token이 설정되어 있지 않으면 AI가 한 번 요청합니다. Token을 전달하면 AI가 사용자 수준 설정 `~/.editppt/config.yaml`에 민감한 값을 가려 저장하며, 한 번 구성하면 계속 적용되어 다시 묻지 않습니다.

Token 없이도 실행할 수 있습니다. 이 경우 skill은 내장 오프라인 감지기(텍스트 위치와 크기를 알지만 내용을 인식하지 않는 순수 기하 측정)로 폴백하므로 텍스트 복원 품질이 낮아질 수 있습니다.

## 이미지 Backend 및 타사 API 구성

이미지 생성과 편집은 현재 agent의 내장 `image_gen.imagegen` 도구를 우선 사용합니다. 정해진 폴백 조건을 충족할 때만 `editppt image` CLI로 전환하며, CLI는 로컬 Codex OAuth(`~/.codex/auth.json`)를 우선 사용하고 사용할 수 없으면 `~/.editppt/config.yaml` 또는 환경 변수의 OpenAI-compatible API 설정을 읽습니다.

일반적으로 직접 구성할 필요는 없습니다. 다음 경우에만 AI에게 API 폴백 구성을 요청하세요.

- 타사 API 또는 OpenAI 호환 중계 서비스를 사용하도록 명시적으로 요청한 경우
- Claude Code, OpenClaw, Hermes Agent 등 Codex가 아닌 환경에서 사용하며 Codex OAuth auth를 사용할 수 없는 경우
- `editppt image`가 Codex OAuth와 `OPENAI_API_KEY`를 모두 사용할 수 없다고 보고한 경우

타사 API 폴백이 필요하면 사용할 서비스, base URL, 모델명, API key를 AI에게 알려 주세요. AI가 실행 중 환경 확인과 설정 기록을 완료하고, 자격 증명을 사용자 수준 설정 `~/.editppt/config.yaml`에 저장하며 출력에서는 민감한 값을 가립니다. API key를 프로젝트 디렉터리, run 디렉터리 또는 skill 디렉터리에 기록하지 마세요.

Codex OAuth 경로는 로컬 Codex auth와 구독 측 이미지 할당량에 의존하고, API 폴백은 선택한 OpenAI-compatible 서비스의 이미지 생성/편집 기능에 의존합니다.
