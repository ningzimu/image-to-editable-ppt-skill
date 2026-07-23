# 빠른 시작

## 대상 사용자

이 페이지는 Image to Editable PPT를 처음 사용하는 사람을 위한 안내입니다. 하나 이상의 슬라이드 이미지, PDF 또는 이미지 기반 `.pptx`를 준비한 다음 agent가 `image-to-editable-ppt` skill을 사용해 편집 가능한 PowerPoint로 변환하도록 하면 됩니다.

## 시작 전 확인 사항

- **사용량**: 변환에는 token이 많이 듭니다. ChatGPT Pro 사용자에게 권장하며 Plus 사용자는 신중하게 사용하세요. 10페이지짜리 PPT 하나를 복원하는 데 5시간 한도를 모두 사용할 수도 있습니다. 처음에는 한 페이지로 시험해 보는 것이 좋습니다.
- **권한**: Codex에서는 “전체 액세스 권한” 사용을 권장합니다. 그렇지 않으면 승인 요청이 흐름을 자주 중단할 수 있습니다. [설치 및 구성](/ko/installation.md)을 참고하세요.
- **OCR Token(권장)**: 무료 바이두 AI Studio Access Token을 신청하면 텍스트 복원 품질을 크게 높일 수 있습니다. 최초 사용 시 AI가 한 번 요청하므로 Token을 전달하면 됩니다. [설치 및 구성](/ko/installation.md)을 참고하세요.

## 가장 간단한 사용 방법

먼저 [설치 및 구성](/ko/installation.md)을 참고해 skill을 설치하세요. 그다음 Codex에서 직접 사용하면 됩니다. 이미지, PDF, `.pptx`를 대화창에 붙여 넣거나 첨부할 수 있고 로컬 경로를 제공할 수도 있습니다.

```text
$image-to-editable-ppt 이 이미지를 편집 가능한 PPT로 변환해 주세요.
```

다중 페이지 입력도 같은 방식입니다.

```text
$image-to-editable-ppt <path-to-deck.pdf>를 편집 가능한 PPT로 변환해 주세요.
```

skill을 명시적으로 선택할 수 있는 다른 agent에서는 해당 문법으로 `image-to-editable-ppt`를 선택하면 됩니다.

## 첫 사용 권장 사항

- 먼저 단일 이미지로 전체 흐름을 실행해 결과와 소요 시간이 기대에 맞는지 확인한 후 다중 페이지 작업을 시작하세요.
- 변환 시작 전에 AI가 OCR Token을 요청하면 1분 정도 투자해 신청하고 제공하는 것을 권장합니다. 설정하지 않아도 실행되지만 텍스트 복원 품질이 낮아질 수 있습니다.
- 변환 중에는 가능한 한 컴퓨터 앞에 머무르세요. 전체 액세스 권한을 사용하지 않으면 일부 단계에서 수동 승인이 필요할 수 있습니다.
- 결과를 받은 뒤 PowerPoint로 열어 텍스트, 도형, 이미지 에셋을 따로 편집할 수 있는지 확인하고 `final/validation.json`에서 검증 결과를 살펴보세요.

## 변환 결과

작업이 끝나면 독립 출력 디렉터리 `output/image-to-editable-ppt/{job-id}/`에 다음 파일이 생성됩니다.

- `final/{origin}_edited.pptx`: 최종 편집 가능 PowerPoint 파일
- `final/validation.json`: 최종 deck 검증 결과
- `final/run_summary.json`: 이번 변환 요약
- `pages/page_NNN/`: 페이지별 재구성 작업 공간(원본 이미지, 미리보기, 에셋 등의 중간 산출물)

전체 디렉터리 구조는 [표준 워크플로](/ko/workflow.md)를 참고하세요.
