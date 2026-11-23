# v1.0.0 공개 절차

기존 저장소는 비공개 `tkcjsrn1/sheet-music-helper-dev`로 유지한다. 새 `tkcjsrn1/sheet-music-helper`에 MIT 소스의 새 이력과 v1.0.0 릴리스를 올린다.

## 1. 비공개 저장소 이름 변경과 원격 갱신

- [ ] 최종 공개 후보의 커밋·EXE·SHA256을 확정하고, [공개 경로와 SHA256 목록](PUBLIC_FILES.json)을 그 소스 기준으로 갱신한다. PDF 모듈과 의존성, MIT LICENSE, 채택한 아이콘을 포함한 허용 범위를 확인한다.
- [ ] **사용자**가 기존 비공개 저장소 상단의 **Settings → General → Repository name**에서 `sheet-music-helper-dev`를 입력하고 **Rename**을 누른다. 새 주소에서 **Private** 표시와 기존 이슈·PR을 확인한다. [GitHub 이름 변경 안내](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository)
- [ ] CLI와 Codex의 기존 작업 사본에서 각각 아래 명령을 실행한다. `git remote -v`에 fetch·push 주소 모두 `sheet-music-helper-dev`로 나온 뒤에 새 저장소를 만든다. 별도 push 주소가 설정돼 있으면 마지막 명령도 실행한다.

  ```powershell
  git remote set-url origin https://github.com/tkcjsrn1/sheet-music-helper-dev.git
  git remote -v
  git ls-remote --exit-code origin refs/heads/main
  git fetch origin main
  # 별도 push 주소가 설정된 경우
  git remote set-url --push origin https://github.com/tkcjsrn1/sheet-music-helper-dev.git
  git remote -v
  ```

## 2. 공개용 첫 커밋과 새 저장소

- [ ] 새 빈 폴더에 [허용 목록](PUBLIC_FILES.md)의 파일만 복사한다. 공개 README, MIT LICENSE, 사용 안내, SmartScreen, 릴리스 노트와 제3자 고지를 목록의 대상 경로에 둔다. 원본·샘플 악보 이미지, 골든 원본, 권리 미확인 자료, 개인 설정, 기존 `.git`을 제외한다. 파일명과 바이트 해시를 목록과 대조한다.
- [ ] **새 폴더에서만** Git을 초기화한다. 스테이징 파일 전부를 허용 목록과 대조한 뒤 첫 커밋을 만든다. `git rev-list --count HEAD` 결과가 1인지 확인한다.

  ```powershell
  git init --initial-branch=main
  git add --all
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "Initial public release"
  git rev-list --count HEAD
  ```

- [ ] **사용자**가 GitHub 우측 상단의 **+ → New repository**를 누른다. **Owner**를 `tkcjsrn1`, **Repository name**을 `sheet-music-helper`, **Visibility**를 **Private**으로 설정한다. README·.gitignore·license 자동 추가를 끈 상태에서 **Create repository**를 누른다. [GitHub 저장소 생성 안내](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [ ] 새 폴더에만 공개용 원격을 추가하고 첫 커밋을 푸시한다. GitHub 파일 탭에서 MIT LICENSE, README 및 문서의 경로와 첫 커밋 1개를 확인한다.

  ```powershell
  git remote add origin https://github.com/tkcjsrn1/sheet-music-helper.git
  git remote -v
  git push -u origin main
  ```

## 3. 릴리스 초안

- [ ] ZIP의 EXE 해시가 단독 EXE와 일치하는지 확인한다. ZIP에는 실제 번들의 제3자 고지를 넣는다. 내부 경로가 담긴 빌드 정보가 있다면 공개 가능한 내용을 담은 산출물로 교체하고 ZIP 해시를 다시 계산한다. 단독 EXE와 ZIP의 파일명별 SHA256을 `SHA256SUMS.txt`로 만든다.
- [ ] 새 저장소의 **Releases → Draft a new release**에서 새 태그 `v1.0.0`을 선택하고 첫 커밋이 있는 `main`을 대상으로 지정한다. 제목은 `악보헬퍼 v1.0.0`으로 쓰고 [릴리스 본문](RELEASE_NOTES.md)을 붙인다. EXE·ZIP·SHA256SUMS.txt를 첨부하고 **Save draft**로 저장한다.
- [ ] 첨부 파일명·해시, README의 다운로드 링크, 본문의 `v1.0.0` 소스 링크를 확인한다. ZIP과 단독 EXE가 최종 검증 산출물인지 확인한다. [GitHub 릴리스 안내](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

## 4. 사용자 결정 후 공개

- [ ] **사용자**가 **새** `sheet-music-helper`에서 **Settings → General → Danger Zone → Change repository visibility → Change visibility → Make public**을 연다. 확인 화면의 저장소 이름이 `tkcjsrn1/sheet-music-helper`인지 확인하고, 화면에 표시된 영향 안내를 읽은 뒤 **Make this repository public**으로 확정한다. [GitHub 공개 범위 안내](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [ ] 새 저장소의 **Releases**에서 v1.0.0 초안을 열고 첨부를 확인한 뒤 **Publish release**를 누른다. 로그인하지 않은 창에서 릴리스, 소스, Issues와 첨부가 열리는지 확인한다.
- [ ] 실제로 내려받은 ZIP·EXE의 SHA256과 SmartScreen 표시를 확인한다. 실제 스피커 음색과 체감 시차, 사용자 악보의 계이름 줄 및 저장 → 종료 → 재열기를 확인한다. [SmartScreen 안내](SMARTSCREEN.md)
