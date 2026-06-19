# PhysicsLens Lab

카메라 영상에서 색상 마커의 위치를 추적하고 Kalman Filter로 물리량을 실시간 추정하는 실험 도구입니다. 단진자에만 묶이지 않고 자유낙하, 포물선 운동, 직선 운동, 용수철 진동, 원운동 등 여러 실험에서 위치, 속도, 가속도, 힘을 측정할 수 있습니다.

## 실행

```bash
pip install -r requirements.txt
python main.py
```

브라우저 기반 UI:

```bash
python web_server.py
```

## 실험 프리셋

| 프리셋 | 측정 물리량 | 모델 |
|---|---|---|
| `pendulum` | 각도, 각속도, 각가속도, 감쇠계수, 중력가속도 추정 | Pendulum EKF |
| `freefall` | 높이, 수직 속도, 수직 가속도, g 추정 | 2D Motion KF |
| `projectile` | x-y 위치, 속력, 가속도 크기 | 2D Motion KF |
| `linear_motion` | 위치, 속도, 가속도, 힘 | 2D Motion KF |
| `spring_mass` | 평형점 기준 변위, 속도, 가속도 | 2D Motion KF |
| `circular_motion` | 위치, 속력, 가속도 크기 | 2D Motion KF |
| `motion2d` | 범용 2D 위치, 속도, 가속도, 힘 | 2D Motion KF |

## V자 진자 보정

진자 장치가 실을 V자 형태로 고정하는 경우, `Pendulum length (m)`에는 먼저 실 한 가닥의 실제 길이를 입력합니다. 보정 과정에서 앱이 두 상단 고정점 사이 반폭을 반영해 유효 길이 `L_eff`를 자동 계산합니다.

1. `C`를 누릅니다.
2. 왼쪽 상단 고정점을 클릭합니다.
3. 오른쪽 상단 고정점을 클릭합니다.
4. 정지 상태의 추 중심을 클릭합니다.

계산식:

```text
L_eff = l * sqrt(l_px^2 - a_px^2) / l_px
```

여기서 `l`은 입력한 실 한 가닥 길이, `l_px`는 화면에서 측정한 평균 실 길이, `a_px`는 두 상단 고정점 사이 거리의 절반입니다.

## 2D 실험 보정

1. `C`를 누릅니다.
2. 원점 또는 평형점을 클릭합니다.
3. 실제 길이를 알고 있는 기준선의 끝점을 클릭합니다.
4. 기준 거리는 Advanced UI의 `Scale distance` 또는 CLI `--scale-distance`로 지정합니다.

## CLI 예시

```bash
python main.py --experiment pendulum --camera 1 --color orange --length 0.75
python main.py --experiment freefall --camera 1 --color green --scale-distance 0.5
python main.py --experiment projectile --video sample.mp4 --color red --mass 0.05
python main.py --experiment linear_motion --stream-url http://192.168.0.10:8080/video --color blue
```

## 조작

| 키 | 기능 |
|---|---|
| `P` | 마커 색상 직접 샘플링 |
| `C` | 보정 모드 |
| `R` | 필터 초기화 |
| `M` | HSV 마스크 보기 |
| `S` | CSV 저장 |
| `A` | 진자 프리셋에서 감쇠계수 추정 on/off |
| `+` / `-` | 진자 길이 5cm 조정 |
| `Q` / `ESC` | 종료 |

## 방정식 추정

웹 UI의 `방정식 추정`은 현재 진자 프리셋에서 STLSQ로 `theta_ddot = f(theta, omega)`를 산출합니다. 다른 프리셋은 CSV로 위치, 속도, 가속도 시계열을 저장한 뒤 후속 분석에 사용합니다.
