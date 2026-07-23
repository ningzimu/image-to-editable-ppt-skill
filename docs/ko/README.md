# Image to Editable PPT Skill 사용 설명서

Image to Editable PPT는 이미지, PDF, 이미지 기반 PPT를 **객체 단위로 편집 가능한 PowerPoint**(`.pptx`)로 변환하는 skill입니다. 입력을 페이지별 작업으로 정규화한 다음 `.pptx`로 재구성합니다. 읽을 수 있는 텍스트는 가능한 한 네이티브 텍스트 상자로 복원하고, 단순한 도형은 PowerPoint 도형으로 복원하며, 복잡한 시각 요소는 출처가 기록된 독립 이미지 에셋으로 유지합니다.

![Image to Editable PPT 프로젝트 개요](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/image-to-editable-ppt-overview.png)

## 문서 읽는 방법

빠르게 시작하려면 [빠른 시작](/ko/quickstart.md)을 먼저 읽어 보세요.

이 skill이 왜 이렇게 설계되었고 왜 token을 많이 사용하는지 알고 싶다면 [설계 철학](/ko/design.md)을 참고하세요.

설치, 업데이트, OCR Token 또는 타사 이미지 생성 API를 설정하려면 [설치 및 구성](/ko/installation.md)을 참고하세요.

전체 변환 과정과 출력 구조를 이해하려면 [표준 워크플로](/ko/workflow.md)를 참고하세요.

사용 중 문제가 생겼다면 [자주 묻는 질문](/ko/faq.md)을 확인하세요.

## 하위 페이지

- [빠른 시작](/ko/quickstart.md): 처음 사용할 때의 가장 짧은 경로, 예시 명령, 산출물 설명
- [설계 철학](/ko/design.md): 객체 단위 재구성 원칙, 재구성-자체 점검-수정 사이클, codex-ppt와의 역할 분담
- [설치 및 구성](/ko/installation.md): 설치 및 업데이트, 실행 권한 권장 사항, OCR Token 신청, 이미지 backend와 타사 API 폴백
- [표준 워크플로](/ko/workflow.md): 입력 정규화와 페이지 분배부터 페이지별 재구성, 최종 조립과 검증까지의 전체 흐름 및 출력 디렉터리 구조
- [자주 묻는 질문](/ko/faq.md): token 사용량, 권한 모드, OCR Token, 복원 정확도, agent 지원 등 자주 묻는 문제
- [예시 프롬프트](/ko/prompts.md): 단일 이미지, 여러 이미지, PDF, 이미지 기반 PPT 변환에 바로 사용할 수 있는 프롬프트

## 변환 결과 예시

| 원본 이미지 | 변환 후 편집 가능한 결과 |
| --- | --- |
| ![시장 개요 원본](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-market-snapshot.png) | ![시장 개요 변환 결과](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-market-snapshot.png) |
| ![프로젝트 진행 보고 원본](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-status-report.png) | ![프로젝트 진행 보고 변환 결과](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-status-report.png) |
| ![신장암 MDT 인포그래픽 원본](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-origin-mdt-kidney-cancer.jpg) | ![신장암 MDT 인포그래픽 변환 결과](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/showcase-editable-ppt-result-mdt-kidney-cancer.png) |

## 주요 기능

- 단일 이미지, 여러 이미지, 다중 페이지 PDF, 이미지 기반 PPT 등 다양한 입력을 지원하며 모두 편집 가능한 `.pptx`로 출력합니다.
- 객체 단위 재구성: 텍스트는 네이티브 텍스트 상자, 단순한 도형은 PowerPoint 도형, 복잡한 시각 요소는 독립 이미지 에셋으로 복원해 세 종류를 따로 조정할 수 있습니다.
- 측정 기반 텍스트 복원: OCR로 각 페이지의 텍스트 주석(상자 좌표 + 글자 크기 + 크기 그룹)을 생성하고, 모델은 측정값에 따라 텍스트를 복원하며 같은 계층의 글자 크기를 자동으로 일관되게 유지합니다. 자세한 내용은 [설치 및 구성](/ko/installation.md)의 OCR Token 절을 참고하세요.
- 다중 페이지 병렬 재구성: 다중 페이지 입력은 메인 agent가 page worker/subagent에게 병렬로 분배하고, 단일 페이지 입력은 메인 agent가 같은 재구성 흐름으로 로컬에서 처리합니다.
- 이미지 생성과 편집은 현재 agent의 내장 `image_gen.imagegen` 도구를 우선 사용합니다. 정해진 폴백 조건을 충족할 때만 `editppt image`를 호출하며, CLI가 Codex OAuth와 OpenAI-compatible API 중 backend를 선택합니다.
- `.pptx` 입력의 페이지 노트는 번역·요약·수정 없이 출력의 해당 페이지에 그대로 복사됩니다.
- 페이지 순서가 안정적입니다. 여러 이미지는 제공된 순서대로 페이지를 만들고, PDF와 `.pptx`는 원래 페이지 순서를 유지합니다.

## 중요 안내

**이것은 가벼운 변환기가 아닙니다.** 이 skill은 멀티 agent 협업 복원 흐름을 사용하며, AI가 “재구성 → 자체 점검 → 페이지 내부 수정” 사이클을 여러 번 반복할 수 있어 token 사용량이 큽니다. 10페이지짜리 PPT 하나를 복원하는 데 ChatGPT의 5시간 한도를 모두 사용할 수도 있고, 한 페이지를 복원하는 데 10분 이상 걸릴 수 있습니다. **ChatGPT Pro 사용자에게 권장하며, Plus 사용자는 신중하게 사용하세요.**

**편집 가능성이 꼭 필요하지 않다면 이 skill을 사용하지 마세요.** 더 가벼운 방법은 `gpt-image-2`의 이미지 편집 기능을 직접 사용해 마음에 들지 않는 PPT 페이지 이미지만 수정하는 것입니다.

**Codex에서는 “전체 액세스 권한” 사용을 권장합니다.** 그렇지 않으면 OCR, 이미지 생성, 하위 agent 분배 등의 단계가 승인 요청으로 자주 중단될 수 있습니다. 자세한 내용은 [설치 및 구성](/ko/installation.md)을 참고하세요.

이 skill은 글, 보고서, 개요 또는 아이디어에서 새로운 PPT를 직접 만드는 용도가 아닙니다. “PPT 생성”이 목적이라면 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill)을 사용하세요.

## 관련 링크

- GitHub 저장소: https://github.com/ningzimu/image-to-editable-ppt-skill
- 프로젝트 홈페이지: https://ppt-skill.ningzimu.vip
- PPT 생성 skill(자매 프로젝트): https://github.com/ningzimu/codex-ppt-skill
- 설계 및 조정 경험: [2000 个 GitHub Star 换来的经验：好的 AI Skill 是调出来的，不是写出来的](https://mp.weixin.qq.com/s/LaxWBX-nogHPpSxlk-Vs8Q)
