# 물리 시스템 지배방정식 자동 역추론 (Neural ODE + Symbolic Regression)

> 카메라로 진자(또는 진동)를 찍으면 → 추적 → **Neural ODE로 동역학 학습** → **기호회귀로 명시적 방정식 도출**.
> `θ̈ = -(g/L)sin(θ) - γω` 같은 운동방정식을 데이터에서 역추론한다.
> 팀 **버그도 기능입니다** (2026 STEM+I 해커톤)

---

## ⚡ 빠른 시작 (팀원용 — 이것만 따라하면 됨)

### 1) 코드 받기
```bash
git clone https://github.com/onlineschoolentry/-22.git
cd -22/physics_kalman
```

### 2) 라이브러리 설치 (한 번만)
```bash
pip install -r requirements-ml.txt
```
> torch가 제일 무거워(~200MB) 처음만 좀 걸림. Julia/PySR 설치 불필요(gplearn 폴백).

### 3) 실행
- **Windows**: `start_local_program.bat` **더블클릭** → 브라우저가 자동으로 열림
- 또는 터미널에서:
  ```bash
  python launcher.py
  ```
  → 브라우저에서 **http://127.0.0.1:8843** 열림

### 4) 설치 잘 됐나 1초 확인
```bash
python -c "import numpy,scipy,pandas,sympy,cv2,torch,torchdiffeq,gplearn; print('OK')"
```
`OK` 나오면 끝.

---

## 🧪 사용법 (4가지)

### A. 라이브 (카메라로 바로)
1. 브라우저 화면에서 **Start** (카메라 시작)
2. **Sample Color** → 추(마커) 클릭 (색 지정)
3. **Calibrate** → 진자: 줄 매단 점 클릭 → 추 클릭
4. 진자를 **크게(30°+) 흔들기** (10~20초)
5. 발견:
   - **Fit Model** = 빠른 STLSQ (즉시)
   - **Neural ODE** = 풀 파이프라인 (1~2분 학습, 방정식 + 3방법 교차검증)
6. **Export CSV** 로 데이터 저장 가능

### B. 영상으로 (OpenCV 추적)
녹화한 영상 → 각도 시계열:
```bash
python cv_tracker.py --video pendulum.mp4 --out theta.csv
```
→ 창이 뜨면 **피벗 클릭 → 추 클릭**(추 클릭이 색도 샘플링) → 자동 추적 → `theta.csv` 저장

### C. 발견 (CSV → 방정식)
```bash
python discover_pipeline.py --csv theta.csv
```
→ Neural ODE 학습 → 기호회귀 → `θ̈ = ...` 출력 + g/L

### D. 합성 검증 (정답 아는 상태에서 정확도 확인)
```bash
python discover_pipeline.py --synthetic
```

---

## 📁 파일 구조 (뭐가 뭔지)

| 파일 | 역할 |
|---|---|
| `start_local_program.bat` | **더블클릭 실행** (Windows) |
| `launcher.py` | 로컬 서버 띄우고 브라우저 열기 |
| `web_server.py` | 백엔드 (웹 서빙 + 발견 API) |
| `web/` | 프론트엔드 (app.js, index.html, styles.css) — 카메라·추적·대시보드 |
| `cv_tracker.py` | **OpenCV** 영상 추적 → θ(t) CSV (파이프라인 ①단계) |
| `smoother.py` | 운동학 칼만 스무더 (깨끗한 θ,ω,α) |
| `neural_ode.py` | **Neural ODE** (PyTorch + torchdiffeq) — 벡터필드 학습 |
| `discover_pipeline.py` | **Neural ODE → 기호회귀** 전체 파이프라인 |
| `equation_discovery.py` | STLSQ(SINDy) — 교차검증 baseline |
| `results.png`, `generalization.png` | 발표/보고서용 결과 그림 |

---

## 🔗 파이프라인 흐름 (계획서 4단계)
```
카메라/영상
  ① 색 추적 (cv_tracker.py = OpenCV / web = 브라우저)  → 각도 θ(t)
  ② 칼만 스무더 (smoother.py)                          → 깨끗한 [θ, ω]
  ③ Neural ODE (neural_ode.py, torchdiffeq RK4)        → 벡터필드 f(θ,ω) 학습
  ④ 기호회귀 (discover_pipeline.py, PySR→gplearn)       → 명시적 방정식
        ↓
   θ̈ = -(g/L)sin(θ) - γω   +  g/L·γ 추출 + 주기 교차검증
```

## 📐 지원 실험
- **진자**(pendulum): `θ̈ = -(g/L)sin(θ) - γω` (비선형) — g/L 추출
- **용수철/진동**(spring): `ẍ = -(k/m)x` (선형, 훅의 법칙) — k/m 추출

---

## ❓ 자주 나는 문제
| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError` | `pip install -r requirements-ml.txt` 다시 |
| **Neural ODE 버튼 안 됨** | torch 설치 확인. **로컬 실행에서만 됨** |
| 카메라 안 열림 | 반드시 **http://127.0.0.1:8843** (또는 localhost)로 접속 |
| 색 추적 안 됨 | 드롭다운 색 말고 **Sample Color로 마커 직접 클릭** |
| 트래킹이 작게 나옴 | 스윙 평면을 **카메라와 평행하게** (앞뒤로 흔들면 압축됨) |
| 비선형(sin) 발견 안 됨 | 진폭 **30~40°** 필요 (작으면 sin≈θ라 구분 불가) |
| `gplearn` sklearn 에러 | 코드에 호환 패치 있음. 그래도 나면 `pip install -U gplearn` |

## 🛠 기술 스택
Python · **PyTorch + torchdiffeq** (Neural ODE) · **PySR/gplearn** (기호회귀) · **OpenCV** (추적) · NumPy/SciPy/SymPy · 브라우저 JS(실시간 UI)

## 📝 핵심 결과 (검증됨)
- 합성: Neural ODE가 g/L 0.95% 오차로 복원, 기호회귀가 sin(θ) 선택
- 실데이터 (진폭 40°, 60fps): `θ̈ = -39.03·sin(θ) - 0.071·ω` → g/L Neural ODE **39.03** / STLSQ **38.45** / 주기 **36.97** (3방법 일치)
- 일반화: 학습 안 한 초기조건(내삽) 예측 0.05° 오차
- 전처리: 칼만 스무더가 유한차분 대비 가속도 55배 정확
