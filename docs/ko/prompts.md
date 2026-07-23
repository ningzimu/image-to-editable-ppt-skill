# 예시 프롬프트

아래 프롬프트는 Codex의 `$` 문법을 기준으로 합니다. 다른 agent에서는 해당 skill 선택 문법을 사용하세요. 이미지, PDF, `.pptx`를 대화창에 직접 붙여 넣거나 첨부할 수 있고 로컬 경로를 제공할 수도 있습니다.

## 단일 이미지를 편집 가능한 PPT로 변환

```text
$image-to-editable-ppt 이 이미지를 편집 가능한 PPT로 변환해 주세요.
```

## 여러 이미지를 하나의 PPT로 변환

```text
$image-to-editable-ppt 이 이미지들을 하나의 편집 가능한 PPT로 변환하고, 내가 제공한 순서대로 페이지를 배치해 주세요.
```

## PDF를 편집 가능한 PPT로 변환

```text
$image-to-editable-ppt <path-to-deck.pdf>를 편집 가능한 PPT로 변환해 주세요.
```

## 이미지 기반 PPT를 편집 가능한 PPT로 변환

```text
$image-to-editable-ppt <path-to-image-based.pptx>를 편집 가능한 PPT로 변환하고 각 페이지의 발표자 노트를 유지해 주세요.
```

## OCR Token 구성

```text
제가 신청한 바이두 AI Studio Access Token은 <token>입니다. 텍스트 보정에 사용하도록 editppt에 구성해 주세요.
```

## 타사 이미지 API 폴백 구성

```text
타사 이미지 생성 API를 구성해야 합니다. base URL은 <https://xxx/v1>, 모델명은 <model-name>, API key는 <key>입니다. editppt의 사용자 수준 설정에 기록해 주세요.
```

## 변환 품질 확인

```text
각 페이지의 원본 이미지와 변환된 페이지를 비교해 누락된 텍스트, 위치 오류 또는 에셋 누락이 있는지 확인하고 검증 결과를 요약해 주세요.
```

## 완료되지 않은 작업 계속하기

```text
방금 변환이 중단되었습니다. output/image-to-editable-ppt/ 아래의 가장 최근 작업 실행 상태를 확인하고 처리되지 않은 페이지부터 계속 진행해 주세요.
```
