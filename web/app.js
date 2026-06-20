const video = document.getElementById("video");
const canvas = document.getElementById("videoCanvas");
const ctx = canvas.getContext("2d", { willReadFrequently: true });

const els = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  cameraPanel: document.querySelector(".cameraPanel"),
  startCamera: document.getElementById("startCamera"),
  uploadVideo: document.getElementById("uploadVideo"),
  videoFile: document.getElementById("videoFile"),
  slowmo: document.getElementById("slowmo"),
  pickColor: document.getElementById("pickColor"),
  calibrate: document.getElementById("calibrate"),
  reset: document.getElementById("reset"),
  saveCsv: document.getElementById("saveCsv"),
  discover: document.getElementById("discover"),
  experiment: document.getElementById("experiment"),
  modeTitle: document.getElementById("modeTitle"),
  modeSummary: document.getElementById("modeSummary"),
  modeMetrics: document.getElementById("modeMetrics"),
  color: document.getElementById("color"),
  lengthLabel: document.getElementById("lengthLabel"),
  length: document.getElementById("length"),
  massLabel: document.getElementById("massLabel"),
  mass: document.getElementById("mass"),
  scaleDistanceLabel: document.getElementById("scaleDistanceLabel"),
  scaleDistance: document.getElementById("scaleDistance"),
  lambdaLabel: document.getElementById("lambdaLabel"),
  lambdaThreshold: document.getElementById("lambdaThreshold"),
  readout: document.getElementById("readout"),
  equationOutput: document.getElementById("equationOutput"),
  discoverNeural: document.getElementById("discoverNeural"),
  plotTheta: document.getElementById("plotTheta"),
  plotOmega: document.getElementById("plotOmega"),
  plotAlpha: document.getElementById("plotAlpha"),
  plotPhase: document.getElementById("plotPhase"),
};

const colorPresets = {
  orange: [[5, 120, 120], [25, 255, 255]],
  green: [[35, 100, 100], [85, 255, 255]],
  red: [[0, 120, 100], [10, 255, 255]],
  blue: [[100, 120, 80], [130, 255, 255]],
  yellow: [[20, 100, 100], [35, 255, 255]],
  magenta: [[140, 80, 80], [170, 255, 255]],
  pink: [[140, 60, 120], [172, 255, 255]],
};

const experimentProfiles = {
  pendulum: {
    estimator: "pendulum",
    name: "Pendulum EKF",
    summary: "CALIB: left anchor -> right anchor -> bob at rest",
    metrics: ["theta", "omega", "alpha", "gamma", "L_eff"],
    primary: ["theta", "rad"],
    velocity: ["omega", "rad/s"],
    acceleration: ["alpha", "rad/s^2"],
    readout: "pendulum",
    equation: "STLSQ濡?theta_ddot = f(theta, omega)瑜?異붿젙?⑸땲??",
  },
  freefall: {
    estimator: "motion2d",
    name: "Free Fall",
    summary: "CALIB: origin -> scale reference",
    metrics: ["y", "vy", "ay", "g_est", "g_error"],
    primary: ["y", "m"],
    velocity: ["vy", "m/s"],
    acceleration: ["ay", "m/s^2"],
    readout: "vertical",
    equation: "媛?띾룄 ay???됯퇏媛믪쑝濡?以묐젰媛?띾룄 g瑜?寃?좏빀?덈떎.",
  },
  projectile: {
    estimator: "motion2d",
    name: "Projectile",
    summary: "CALIB: origin -> scale reference",
    metrics: ["x", "y", "speed", "range", "height", "mean ay"],
    primary: ["x", "m"],
    velocity: ["speed", "m/s"],
    acceleration: ["|a|", "m/s^2"],
    readout: "motion2d",
    equation: "x-y 沅ㅼ쟻, ?띾룄, 媛?띾룄 蹂?붾? ?ㅼ떆媛?痢≪젙?⑸땲??",
  },
  linear_motion: {
    estimator: "motion2d",
    name: "Linear Cart",
    summary: "CALIB: origin -> scale reference",
    metrics: ["x", "vx", "ax", "mean ax", "F"],
    primary: ["x", "m"],
    velocity: ["vx", "m/s"],
    acceleration: ["ax", "m/s^2"],
    readout: "motion2d",
    equation: "吏덈웾 ?낅젰媛믪쑝濡?F = ma瑜??④퍡 怨꾩궛?⑸땲??",
  },
  spring_mass: {
    estimator: "motion2d",
    name: "Spring-Mass",
    summary: "CALIB: equilibrium -> scale reference",
    metrics: ["x", "vx", "ax", "T", "omega", "k"],
    primary: ["x", "m"],
    velocity: ["vx", "m/s"],
    acceleration: ["ax", "m/s^2"],
    readout: "motion2d",
    equation: "?됲삎??湲곗? 蹂?? ?띾룄, 媛?띾룄 ?쒓퀎?댁쓣 痢≪젙?⑸땲??",
  },
  circular_motion: {
    estimator: "motion2d",
    name: "Circular Motion",
    summary: "CALIB: center/origin -> scale reference",
    metrics: ["r", "speed", "v^2/r", "|a|"],
    primary: ["x", "m"],
    velocity: ["speed", "m/s"],
    acceleration: ["|a|", "m/s^2"],
    readout: "motion2d",
    equation: "?띾젰怨?媛?띾룄 ?ш린濡?援ъ떖媛?띾룄 異붿꽭瑜??뺤씤?⑸땲??",
  },
  motion2d: {
    estimator: "motion2d",
    name: "Generic 2D",
    summary: "CALIB: origin -> scale reference",
    metrics: ["x", "y", "vx", "vy", "ax", "ay", "F"],
    primary: ["x", "m"],
    velocity: ["vx", "m/s"],
    acceleration: ["ax", "m/s^2"],
    readout: "motion2d",
    equation: "踰붿슜 2D ?꾩튂, ?띾룄, 媛?띾룄, ??痢≪젙 紐⑤뱶?낅땲??",
  },
};

const cleanExperimentProfiles = {
  pendulum: {
    estimator: "pendulum",
    name: "Pendulum EKF",
    summary: "CALIB: left anchor -> right anchor -> bob at rest",
    metrics: ["theta", "omega", "alpha", "gamma", "L_eff"],
    primary: ["theta", "rad"],
    velocity: ["omega", "rad/s"],
    acceleration: ["alpha", "rad/s^2"],
    readout: "pendulum",
  },
  freefall: {
    estimator: "motion2d",
    name: "Free Fall",
    summary: "CALIB: release point -> vertical scale endpoint",
    metrics: ["y_down", "vy", "g_fit", "g_error", "R2"],
    primary: ["y_down", "m"],
    velocity: ["vy_down", "m/s"],
    acceleration: ["g_fit", "m/s^2"],
    readout: "vertical",
  },
  projectile: {
    estimator: "motion2d",
    name: "Projectile",
    summary: "CALIB: launch point -> scale endpoint",
    metrics: ["x", "y", "v0", "range", "height", "g_fit"],
    primary: ["x", "m"],
    velocity: ["speed", "m/s"],
    acceleration: ["|a|", "m/s^2"],
    readout: "motion2d",
  },
  linear_motion: {
    estimator: "motion2d",
    name: "Linear Cart",
    summary: "CALIB: origin -> scale reference",
    metrics: ["x", "vx", "ax", "mean ax", "F"],
    primary: ["x", "m"],
    velocity: ["vx", "m/s"],
    acceleration: ["ax", "m/s^2"],
    readout: "motion2d",
  },
  spring_mass: {
    estimator: "motion2d",
    name: "Spring-Mass",
    summary: "CALIB: equilibrium -> scale reference",
    metrics: ["x", "vx", "ax", "T", "omega", "k"],
    primary: ["x", "m"],
    velocity: ["vx", "m/s"],
    acceleration: ["ax", "m/s^2"],
    readout: "motion2d",
  },
  circular_motion: {
    estimator: "motion2d",
    name: "Circular Motion",
    summary: "CALIB: center/origin -> scale reference",
    metrics: ["r", "speed", "v^2/r", "|a|"],
    primary: ["x", "m"],
    velocity: ["speed", "m/s"],
    acceleration: ["|a|", "m/s^2"],
    readout: "motion2d",
  },
  motion2d: {
    estimator: "motion2d",
    name: "Generic 2D",
    summary: "CALIB: origin -> scale reference",
    metrics: ["x", "y", "vx", "vy", "ax", "ay", "F"],
    primary: ["x", "m"],
    velocity: ["vx", "m/s"],
    acceleration: ["ax", "m/s^2"],
    readout: "motion2d",
  },
};

const app = {
  stream: null,
  videoFileMode: false,
  videoObjectUrl: null,
  videoLoopHandle: null,
  videoLoadToken: 0,
  lastMediaTime: null,
  running: false,
  lastTs: null,
  frameCount: 0,
  fps: 0,
  fpsTimer: performance.now(),
  fpsCount: 0,
  calibration: null,
  pivot: null,
  vLeft: null,
  vRight: null,
  restAngle: 0,
  stringPixels: 0,
  origin: null,
  scaleStart: null,
  pixelsPerMeter: 300,
  history: [],
  estimator: null,
  lastMeasurement: null,
  neuralResult: null,
  // Marker color picked by click (overrides the preset dropdown when set).
  markerHsv: null,
  targetSeed: null,
  targetSeedFrames: 0,
  selectionPausedVideo: false,
  picking: false,
  // Spatial lock: stick to the blob near the last position, ignore far
  // same-color objects. Released after the target is lost for a while.
  lastPos: null,
  smoothPos: null,
  lostFrames: 0,
  maxJump: 110,
  reacquireAfter: 60,
};

function profile() {
  return cleanExperimentProfiles[els.experiment.value] || cleanExperimentProfiles.motion2d;
}

function experimentNote() {
  const notes = {
    pendulum: "Pendulum mode fits theta_ddot = f(theta, omega).",
    freefall: "Free-fall mode fits y = y0 + v0*t + 0.5*g*t^2 with downward y positive.",
    projectile: "Projectile mode fits x(t) and y(t) to estimate launch velocity and g.",
    linear_motion: "Linear cart mode reports mean acceleration and F = ma.",
    spring_mass: "Spring-mass mode estimates period T, angular frequency omega, and k = m omega^2.",
    circular_motion: "Circular mode compares measured acceleration with v^2/r.",
    motion2d: "Generic 2D mode exports position, velocity, acceleration, and force time series.",
  };
  return notes[els.experiment.value] || notes.motion2d;
}

function updateExperimentUi() {
  const p = profile();
  const pendulum = isPendulumMode();

  els.modeTitle.textContent = p.name;
  els.modeSummary.textContent = p.summary;
  els.modeMetrics.innerHTML = "";
  p.metrics.forEach((metric) => {
    const chip = document.createElement("span");
    chip.className = "metricChip";
    chip.textContent = metric;
    els.modeMetrics.appendChild(chip);
  });

  els.lengthLabel.classList.toggle("hidden", !pendulum);
  els.lambdaLabel.classList.toggle("hidden", !pendulum);
  els.massLabel.classList.toggle("hidden", pendulum);
  els.scaleDistanceLabel.classList.toggle("hidden", pendulum);
  els.discover.disabled = !(pendulum || isBallisticsMode());
  els.discover.title = pendulum
    ? "Fit pendulum equation"
    : isBallisticsMode()
      ? "Fit trajectory model"
      : "Model fitting is available for pendulum, free-fall, and projectile modes.";
}

class PendulumEKF {
  constructor(dt = 1 / 30) {
    this.dt = dt;
    this.reset();
  }

  reset() {
    this.x = [0, 0, 0.05];
    this.P = diag([0.01, 1.0, 0.5]);
    this.Q = diag([1e-7, 5e-4, 1e-7]);
    this.R = 5e-4;
    this.t = 0;
    this.prevTheta = null;
    this.prevNumOmega = null;
    this.initialized = false;
  }

  setDt(dt) {
    this.dt = clamp(dt, 1 / 2000, 0.5);
  }

  deriv(x) {
    const L = Number(els.length.value) || 0.7;
    const g = 9.81;
    const [th, om, gamma] = x;
    return [om, -(g / L) * Math.sin(th) - gamma * om, 0];
  }

  transition(x) {
    const dt = this.dt;
    const k1 = this.deriv(x);
    const k2 = this.deriv(addVec(x, scaleVec(k1, 0.5 * dt)));
    const k3 = this.deriv(addVec(x, scaleVec(k2, 0.5 * dt)));
    const k4 = this.deriv(addVec(x, scaleVec(k3, dt)));
    return x.map((v, i) => v + (dt / 6) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]));
  }

  jacobian() {
    const L = Number(els.length.value) || 0.7;
    const g = 9.81;
    const [th, om, gamma] = this.x;
    const dt = this.dt;
    return [
      [1, dt, 0],
      [-(g / L) * Math.cos(th) * dt, 1 - gamma * dt, -om * dt],
      [0, 0, 1],
    ];
  }

  predict() {
    const F = this.jacobian();
    this.x = this.transition(this.x);
    this.P = addMat(matMul(matMul(F, this.P), transpose(F)), this.Q);
  }

  update(thetaMeasured) {
    if (!this.initialized) {
      this.x[0] = thetaMeasured;
      this.prevTheta = thetaMeasured;
      this.initialized = true;
    }
    this.predict();
    const y = thetaMeasured - this.x[0];
    const S = this.P[0][0] + this.R;
    const K = [this.P[0][0] / S, this.P[1][0] / S, this.P[2][0] / S];
    for (let i = 0; i < 3; i++) this.x[i] += K[i] * y;

    const nextP = cloneMat(this.P);
    for (let i = 0; i < 3; i++) {
      for (let j = 0; j < 3; j++) nextP[i][j] = this.P[i][j] - K[i] * this.P[0][j];
    }
    this.P = nextP;

    const [theta, omega, gamma] = this.x;
    const L = Number(els.length.value) || 0.7;
    const alpha = -(9.81 / L) * Math.sin(theta) - gamma * omega;
    const numOmega = this.prevTheta === null ? 0 : (thetaMeasured - this.prevTheta) / this.dt;
    const numAlpha = this.prevNumOmega === null ? 0 : (numOmega - this.prevNumOmega) / this.dt;
    this.prevTheta = thetaMeasured;
    this.prevNumOmega = numOmega;
    this.t += this.dt;

    return {
      time: this.t,
      primary: theta,
      velocity: omega,
      acceleration: alpha,
      measured: thetaMeasured,
      numVelocity: numOmega,
      numAcceleration: numAlpha,
      primaryStd: Math.sqrt(Math.max(this.P[0][0], 0)),
      velocityStd: Math.sqrt(Math.max(this.P[1][1], 0)),
      innovation: y,
      gamma,
      gammaStd: Math.sqrt(Math.max(this.P[2][2], 0)),
    };
  }
}

class Motion2DKF {
  constructor(dt = 1 / 30) {
    this.dt = dt;
    this.reset();
  }

  reset() {
    this.x = [0, 0, 0, 0, 0, 0];
    this.P = diag([0.1, 0.1, 2, 2, 5, 5]);
    this.Q = diag([1e-5, 1e-5, 1e-3, 1e-3, 5e-2, 5e-2]);
    this.R = [[2e-4, 0], [0, 2e-4]];
    this.t = 0;
    this.prevX = null;
    this.prevY = null;
    this.prevNumVx = null;
    this.prevNumVy = null;
    this.initialized = false;
  }

  setDt(dt) {
    this.dt = clamp(dt, 1 / 2000, 0.5);
  }

  F() {
    const dt = this.dt;
    return [
      [1, 0, dt, 0, 0.5 * dt * dt, 0],
      [0, 1, 0, dt, 0, 0.5 * dt * dt],
      [0, 0, 1, 0, dt, 0],
      [0, 0, 0, 1, 0, dt],
      [0, 0, 0, 0, 1, 0],
      [0, 0, 0, 0, 0, 1],
    ];
  }

  predict() {
    const F = this.F();
    this.x = matVec(F, this.x);
    this.P = addMat(matMul(matMul(F, this.P), transpose(F)), this.Q);
  }

  update(xMeasured, yMeasured) {
    if (!this.initialized) {
      this.x[0] = xMeasured;
      this.x[1] = yMeasured;
      this.prevX = xMeasured;
      this.prevY = yMeasured;
      this.initialized = true;
    }
    this.predict();
    const H = [
      [1, 0, 0, 0, 0, 0],
      [0, 1, 0, 0, 0, 0],
    ];
    const z = [xMeasured, yMeasured];
    const y = subVec(z, matVec(H, this.x));
    const S = addMat(matMul(matMul(H, this.P), transpose(H)), this.R);
    const K = matMul(matMul(this.P, transpose(H)), inv2(S));
    this.x = addVec(this.x, matVec(K, y));
    this.P = matMul(subMat(identity(6), matMul(K, H)), this.P);

    const [x, yPos, vx, vy, ax, ay] = this.x;
    const numVx = this.prevX === null ? 0 : (xMeasured - this.prevX) / this.dt;
    const numVy = this.prevY === null ? 0 : (yMeasured - this.prevY) / this.dt;
    const numAx = this.prevNumVx === null ? 0 : (numVx - this.prevNumVx) / this.dt;
    const numAy = this.prevNumVy === null ? 0 : (numVy - this.prevNumVy) / this.dt;
    this.prevX = xMeasured;
    this.prevY = yMeasured;
    this.prevNumVx = numVx;
    this.prevNumVy = numVy;
    this.t += this.dt;

    return {
      time: this.t,
      primary: x,
      velocity: vx,
      acceleration: ax,
      measured: xMeasured,
      measuredY: yMeasured,
      numVelocity: numVx,
      numVelocityY: numVy,
      numAcceleration: numAx,
      numAccelerationY: numAy,
      primaryStd: Math.sqrt(Math.max(this.P[0][0], 0)),
      velocityStd: Math.sqrt(Math.max(this.P[2][2], 0)),
      innovation: Math.hypot(y[0], y[1]),
      y: yPos,
      vy,
      ay,
      speed: Math.hypot(vx, vy),
      force: (Number(els.mass.value) || 0.05) * Math.hypot(ax, ay),
    };
  }
}

function setStatus(text, ok = false) {
  els.statusText.textContent = text;
  if (els.statusDot) els.statusDot.classList.toggle("ok", ok);
}

function isPendulumMode() {
  return profile().estimator === "pendulum";
}

function isFreefallMode() {
  return els.experiment.value === "freefall";
}

function isProjectileMode() {
  return els.experiment.value === "projectile";
}

function isBallisticsMode() {
  return isFreefallMode() || isProjectileMode();
}

function currentEstimator() {
  const want = profile().estimator;
  if (!app.estimator || app.estimator.kind !== want) {
    app.estimator = want === "pendulum" ? new PendulumEKF() : new Motion2DKF();
    app.estimator.kind = want;
    app.history = [];
  }
  return app.estimator;
}

async function startCamera() {
  stopVideoFileMode();
  if (app.stream) app.stream.getTracks().forEach((track) => track.stop());
  app.videoFileMode = false;
  app.stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  });
  video.srcObject = app.stream;
  await video.play();
  app.running = true;
  setStatus("RUN", true);
  requestAnimationFrame(loop);
}

async function startVideoFile(file) {
  stopVideoFileMode({ keepVideoElement: true, keepLoadToken: true });
  const loadToken = ++app.videoLoadToken;
  if (app.stream) {
    app.stream.getTracks().forEach((track) => track.stop());
    app.stream = null;
  }
  app.videoFileMode = true;
  app.running = true;
  app.lastMediaTime = null;
  resetExperiment();
  video.srcObject = null;
  video.pause();
  if (app.videoObjectUrl) URL.revokeObjectURL(app.videoObjectUrl);
  app.videoObjectUrl = URL.createObjectURL(file);
  video.removeAttribute("src");
  video.load();
  video.src = app.videoObjectUrl;
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  // Loop so the user can set color + calibration while it replays, then Reset
  // and capture one clean pass. The loop seam has dt<0 and is skipped.
  video.loop = true;
  video.playbackRate = 0.6; // keep per-frame processing from dropping frames
  setStatus("LOADING VIDEO", false);
  drawCanvasMessage(`Loading video: ${file.name}`);

  const support = video.canPlayType(file.type || "video/mp4");
  if (file.type && support === "") {
    els.equationOutput.textContent = [
      `This browser may not support the selected video type: ${file.type}`,
      "Use H.264 MP4 if the file does not open.",
      "Phone .MOV files often use HEVC, which Chrome on Windows may reject.",
    ].join("\n");
  }

  try {
    await waitForVideoReady(video, 10000);
    if (loadToken !== app.videoLoadToken) return;
    resizeCanvas();
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    setStatus("VIDEO READY", true);
    els.equationOutput.textContent = [
      `Video loaded: ${file.name}`,
      `duration: ${Number.isFinite(video.duration) ? video.duration.toFixed(2) : "-"} s`,
      "Set marker color and calibration, then Reset for a clean pass.",
    ].join("\n");

    try {
      await video.play();
      setStatus("VIDEO RUN", true);
    } catch (err) {
      setStatus("VIDEO READY", true);
      els.equationOutput.textContent += `\nPlayback did not auto-start: ${err.message}`;
    }
    app.videoLoopHandle = requestAnimationFrame(videoLoop);
  } catch (err) {
    app.videoFileMode = false;
    setStatus("VIDEO ERROR", false);
    drawCanvasMessage("Video could not be loaded. Try H.264 MP4.");
    els.equationOutput.textContent = [
      `Video load failed: ${err.message}`,
      "",
      "Recommended format: MP4 / H.264 / AAC.",
      "If this came from a phone, export or convert it as H.264 instead of HEVC.",
    ].join("\n");
    throw err;
  }
}

function videoLoop() {
  if (!app.videoFileMode) return;
  if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    app.videoLoopHandle = requestAnimationFrame(videoLoop);
    return;
  }
  const slow = Math.max(1, Number(els.slowmo.value) || 1);
  const mediaTime = video.currentTime;
  if (app.lastMediaTime !== null && mediaTime < app.lastMediaTime - 0.05 && isBallisticsMode() && app.history.length > 10) {
    video.pause();
    setStatus("PASS DONE", true);
    app.videoLoopHandle = requestAnimationFrame(videoLoop);
    return;
  }
  if (app.lastMediaTime === null || mediaTime !== app.lastMediaTime) {
    resizeCanvas();
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const result = trackMarker();
    app.lastMeasurement = result;
    drawOverlay(result);
    if (result.detected && app.lastMediaTime !== null) {
      const dt = (mediaTime - app.lastMediaTime) / slow; // video time -> real time
      if (dt > 0) {
        const est = currentEstimator();
        est.setDt(dt);
        const row = updateModel(est, result);
        if (row) {
          app.history.push(row);
          if (app.history.length > 6000) app.history.shift();
        }
      }
    }
    app.lastMediaTime = mediaTime;
    drawPlots();
    updateReadout(result);
  }
  app.videoLoopHandle = requestAnimationFrame(videoLoop);
}

function stopVideoFileMode(options = {}) {
  if (!options.keepLoadToken) app.videoLoadToken += 1;
  if (app.videoLoopHandle !== null) {
    cancelAnimationFrame(app.videoLoopHandle);
    app.videoLoopHandle = null;
  }
  app.videoFileMode = false;
  app.lastMediaTime = null;
  video.pause();
  if (!options.keepVideoElement) {
    video.removeAttribute("src");
    video.load();
    if (app.videoObjectUrl) {
      URL.revokeObjectURL(app.videoObjectUrl);
      app.videoObjectUrl = null;
    }
  }
}

function waitForVideoReady(target, timeoutMs = 10000) {
  if (target.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => cleanup(() => reject(new Error("Timed out while loading video metadata/data."))), timeoutMs);
    const onReady = () => cleanup(resolve);
    const onError = () => cleanup(() => reject(new Error(videoErrorMessage(target.error))));
    const cleanup = (done) => {
      window.clearTimeout(timeout);
      target.removeEventListener("loadeddata", onReady);
      target.removeEventListener("canplay", onReady);
      target.removeEventListener("error", onError);
      done();
    };
    target.addEventListener("loadeddata", onReady, { once: true });
    target.addEventListener("canplay", onReady, { once: true });
    target.addEventListener("error", onError, { once: true });
    target.load();
  });
}

function videoErrorMessage(error) {
  if (!error) return "Unknown media error.";
  const names = {
    1: "Video loading was aborted.",
    2: "Network error while loading video.",
    3: "Video decode failed. The codec may be unsupported.",
    4: "Video source is not supported by this browser.",
  };
  return names[error.code] || `Media error code ${error.code}.`;
}

function drawCanvasMessage(message) {
  resizeCanvas();
  ctx.fillStyle = "#020304";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#e7edf3";
  ctx.font = "16px Consolas, monospace";
  ctx.fillText(message, 24, 42);
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(320, Math.floor(rect.width));
  const h = Math.max(240, Math.floor(rect.height));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
}

function loop(ts) {
  if (!app.running) return;
  if (app.videoFileMode) return; // video mode is driven by requestVideoFrameCallback
  resizeCanvas();
  const dt = app.lastTs ? (ts - app.lastTs) / 1000 : 1 / 30;
  app.lastTs = ts;
  app.fpsCount += 1;
  if (ts - app.fpsTimer > 1000) {
    app.fps = app.fpsCount / ((ts - app.fpsTimer) / 1000);
    app.fpsCount = 0;
    app.fpsTimer = ts;
  }

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const result = trackMarker();
  app.lastMeasurement = result;
  drawOverlay(result);

  if (result.detected) {
    const est = currentEstimator();
    est.setDt(dt);
    const row = updateModel(est, result);
    if (row) {
      app.history.push(row);
      if (app.history.length > 3000) app.history.shift();
    }
  }

  drawPlots();
  updateReadout(result);
  requestAnimationFrame(loop);
}

function updateModel(est, result) {
  if (isPendulumMode()) {
    if (!app.pivot || app.calibration) return null;
    const angle = pendulumAngle(result.x, result.y);
    return est.update(angle);
  }

  if (!app.origin || app.calibration) return null;
  const coords = motionCoordinates(result);
  return est.update(coords.x, coords.y);
}

function motionCoordinates(result) {
  const x = (result.x - app.origin.x) / app.pixelsPerMeter;
  const yPixels = result.y - app.origin.y;
  const y = isFreefallMode() ? yPixels / app.pixelsPerMeter : -yPixels / app.pixelsPerMeter;
  return { x, y };
}

function trackMarker() {
  const W = canvas.width;
  const Hh = canvas.height;
  const data = ctx.getImageData(0, 0, W, Hh).data;
  const step = Math.max(2, Math.floor(Math.min(W, Hh) / 360));

  let x0 = 0;
  let y0 = 0;
  let x1 = W;
  let y1 = Hh;
  const locked = app.lastPos && app.lostFrames <= app.reacquireAfter;

  const cols = Math.max(1, Math.ceil((x1 - x0) / step));
  const rows = Math.max(1, Math.ceil((y1 - y0) / step));
  const mask = new Uint8Array(cols * rows);
  const quality = new Uint16Array(cols * rows);

  for (let gy = 0; gy < rows; gy++) {
    const y = Math.min(Hh - 1, y0 + gy * step);
    for (let gx = 0; gx < cols; gx++) {
      const x = Math.min(W - 1, x0 + gx * step);
      const i = (y * W + x) * 4;
      const q = colorQuality(rgbToHsv(data[i], data[i + 1], data[i + 2]));
      if (q > 0) {
        const mi = gy * cols + gx;
        mask[mi] = 1;
        quality[mi] = q;
      }
    }
  }

  const blob = bestBlob(mask, quality, cols, rows, x0, y0, step, locked, W, Hh);
  if (app.targetSeedFrames > 0) app.targetSeedFrames -= 1;
  if (!blob || blob.count < 8) {
    app.lostFrames += 1;
    if (app.lostFrames > app.reacquireAfter) app.lastPos = null;
    return { detected: false, area: blob ? blob.count * step * step : 0 };
  }

  const refined = refineSubpixelCentroid(data, W, Hh, blob, step);
  let cx = refined?.x ?? blob.x;
  let cy = refined?.y ?? blob.y;
  if (app.smoothPos) {
    const jump = Math.hypot(cx - app.smoothPos.x, cy - app.smoothPos.y);
    const alpha = locked && jump <= app.maxJump ? 0.68 : 1.0;
    cx = app.smoothPos.x * (1 - alpha) + cx * alpha;
    cy = app.smoothPos.y * (1 - alpha) + cy * alpha;
  }
  app.smoothPos = { x: cx, y: cy };
  app.lastPos = { x: cx, y: cy };
  app.lostFrames = 0;
  return {
    detected: true,
    x: cx,
    y: cy,
    area: blob.count * step * step,
    confidence: refined?.confidence ?? blob.confidence,
    subpixel: Boolean(refined),
  };
}

function bestBlob(mask, quality, cols, rows, x0, y0, step, locked, frameW, frameH) {
  const seen = new Uint8Array(mask.length);
  const qx = [];
  const qy = [];
  let best = null;

  for (let gy = 0; gy < rows; gy++) {
    for (let gx = 0; gx < cols; gx++) {
      const start = gy * cols + gx;
      if (!mask[start] || seen[start]) continue;

      let head = 0;
      let count = 0;
      let sx = 0;
      let sy = 0;
      let sw = 0;
      let qsum = 0;
      let minX = gx;
      let maxX = gx;
      let minY = gy;
      let maxY = gy;
      qx.length = 0;
      qy.length = 0;
      qx.push(gx);
      qy.push(gy);
      seen[start] = 1;

      while (head < qx.length) {
        const cx = qx[head];
        const cy = qy[head];
        const qi = cy * cols + cx;
        const qw = Math.max(quality[qi], 1);
        head += 1;
        count += 1;
        sx += (x0 + cx * step) * qw;
        sy += (y0 + cy * step) * qw;
        sw += qw;
        qsum += qw;
        minX = Math.min(minX, cx);
        maxX = Math.max(maxX, cx);
        minY = Math.min(minY, cy);
        maxY = Math.max(maxY, cy);

        for (const [nx, ny] of [[cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]]) {
          if (nx < 0 || nx >= cols || ny < 0 || ny >= rows) continue;
          const ni = ny * cols + nx;
          if (!mask[ni] || seen[ni]) continue;
          seen[ni] = 1;
          qx.push(nx);
          qy.push(ny);
        }
      }

      if (count < 8) continue;
      const bx = sx / Math.max(sw, 1);
      const by = sy / Math.max(sw, 1);
      const width = (maxX - minX + 1) * step;
      const height = (maxY - minY + 1) * step;
      const aspect = Math.max(width, height) / Math.max(Math.min(width, height), step);
      if (aspect > 8) continue;
      if (width > frameW * 0.7 || height > frameH * 0.7) continue;

      const boxCells = (maxX - minX + 1) * (maxY - minY + 1);
      const density = count / Math.max(boxCells, 1);
      if (density < 0.05) continue;

      const avgQ = qsum / Math.max(count, 1) / 1000;
      const aspectScore = 1 / aspect;
      const densityScore = clamp((density - 0.12) / 0.55, 0, 1);
      const areaScore = Math.sqrt(count);
      let score = areaScore * 42 + avgQ * 120 + densityScore * 50 + aspectScore * 40;
      if (locked && app.lastPos) {
        const d = Math.hypot(bx - app.lastPos.x, by - app.lastPos.y);
        score += Math.max(0, 85 - d * 0.55);
      }
      if (app.targetSeed) {
        const d = Math.hypot(bx - app.targetSeed.x, by - app.targetSeed.y);
        if (app.targetSeedFrames > 0 && d > 400) continue;
        score += app.targetSeedFrames > 0
          ? Math.max(0, 320 - d * 1.05)
          : Math.max(0, 120 - d * 0.45);
      }

      if (!best || score > best.score) {
        best = {
          x: bx,
          y: by,
          count,
          score,
          confidence: avgQ,
          minX: x0 + minX * step,
          maxX: x0 + maxX * step,
          minY: y0 + minY * step,
          maxY: y0 + maxY * step,
        };
      }
    }
  }
  return best;
}

function refineSubpixelCentroid(data, W, Hh, blob, step) {
  const margin = Math.max(4, step * 2);
  const x0 = Math.max(0, Math.floor(blob.minX - margin));
  const x1 = Math.min(W - 1, Math.ceil(blob.maxX + margin));
  const y0 = Math.max(0, Math.floor(blob.minY - margin));
  const y1 = Math.min(Hh - 1, Math.ceil(blob.maxY + margin));
  let sw = 0;
  let sx = 0;
  let sy = 0;
  let count = 0;

  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) {
      const i = (y * W + x) * 4;
      const q = colorQuality(rgbToHsv(data[i], data[i + 1], data[i + 2]));
      if (q <= 0) continue;
      const w = q * q;
      sx += x * w;
      sy += y * w;
      sw += w;
      count += 1;
    }
  }
  if (count < 12 || sw <= 0) return null;
  return {
    x: sx / sw,
    y: sy / sw,
    confidence: Math.sqrt(sw / count) / 1000,
    count,
  };
}

function inBand(hsv, lo, hi) {
  return (
    hsv[0] >= lo[0] && hsv[0] <= hi[0] &&
    hsv[1] >= lo[1] && hsv[1] <= hi[1] &&
    hsv[2] >= lo[2] && hsv[2] <= hi[2]
  );
}

function matchColor(hsv) {
  return colorQuality(hsv) > 0;
}

function colorQuality(hsv) {
  // A picked color (with optional hue-wraparound second band) overrides presets.
  if (app.markerHsv) {
    const m = app.markerHsv;
    const matched = inBand(hsv, m.lo, m.hi) || (m.lo2 && inBand(hsv, m.lo2, m.hi2));
    if (!matched) return 0;
    const hScore = clamp(1 - hueDistance(hsv[0], m.h) / Math.max(m.hTol, 1), 0, 1);
    const sScore = clamp((hsv[1] - m.sLo) / Math.max(255 - m.sLo, 1), 0, 1);
    const vScore = clamp((hsv[2] - m.vLo) / Math.max(255 - m.vLo, 1), 0, 1);
    return Math.round((0.58 * hScore + 0.27 * sScore + 0.15 * vScore) * 1000);
  }

  if (els.color.value === "red") {
    const d = Math.min(hsv[0], 180 - hsv[0]);
    if (d > 14 || hsv[1] < 85 || hsv[2] < 55) return 0;
    const hScore = clamp(1 - d / 14, 0, 1);
    const sScore = clamp((hsv[1] - 85) / 170, 0, 1);
    const vScore = clamp((hsv[2] - 55) / 200, 0, 1);
    return Math.round((0.52 * hScore + 0.30 * sScore + 0.18 * vScore) * 1000);
  }

  const [lo, hi] = colorPresets[els.color.value] || colorPresets.orange;
  if (!inBand(hsv, lo, hi)) return 0;
  const hMid = (lo[0] + hi[0]) / 2;
  const hTol = Math.max((hi[0] - lo[0]) / 2, 1);
  const hScore = clamp(1 - Math.abs(hsv[0] - hMid) / hTol, 0, 1);
  const sScore = clamp((hsv[1] - lo[1]) / Math.max(255 - lo[1], 1), 0, 1);
  const vScore = clamp((hsv[2] - lo[2]) / Math.max(255 - lo[2], 1), 0, 1);
  return Math.round((0.55 * hScore + 0.25 * sScore + 0.20 * vScore) * 1000);
}

function hueDistance(a, b) {
  const d = Math.abs(a - b);
  return Math.min(d, 180 - d);
}

function pickColorAt(px, py) {
  drawCurrentSourceFrame();
  const half = 12;
  const x0 = Math.max(0, Math.round(px) - half);
  const y0 = Math.max(0, Math.round(py) - half);
  const w = Math.min(canvas.width, Math.round(px) + half) - x0;
  const h = Math.min(canvas.height, Math.round(py) + half) - y0;
  if (w <= 0 || h <= 0) return false;

  const d = ctx.getImageData(x0, y0, w, h).data;
  const centerHues = [];
  const centerX = Math.round(px) - x0;
  const centerY = Math.round(py) - y0;
  for (let yy = Math.max(0, centerY - 2); yy <= Math.min(h - 1, centerY + 2); yy++) {
    for (let xx = Math.max(0, centerX - 2); xx <= Math.min(w - 1, centerX + 2); xx++) {
      const i = (yy * w + xx) * 4;
      const hsv = rgbToHsv(d[i], d[i + 1], d[i + 2]);
      if (hsv[1] >= 45 && hsv[2] >= 35) centerHues.push(hsv[0]);
    }
  }
  const centerHue = centerHues.length ? circularHueMean(centerHues) : null;
  const hs = [];
  const ss = [];
  const vs = [];
  for (let i = 0; i < d.length; i += 4) {
    const hsv = rgbToHsv(d[i], d[i + 1], d[i + 2]);
    if (hsv[1] < 55 || hsv[2] < 35) continue;
    if (centerHue !== null && hueDistance(hsv[0], centerHue) > 22) continue;
    hs.push(hsv[0]);
    ss.push(hsv[1]);
    vs.push(hsv[2]);
  }
  if (hs.length < 8) {
    for (let i = 0; i < d.length; i += 4) {
      const hsv = rgbToHsv(d[i], d[i + 1], d[i + 2]);
      hs.push(hsv[0]);
      ss.push(hsv[1]);
      vs.push(hsv[2]);
    }
  }
  const median = (arr) => {
    arr.sort((a, b) => a - b);
    return arr[Math.floor(arr.length / 2)];
  };
  const hMed = circularHueMean(hs);
  const sMed = median(ss);
  const vMed = median(vs);

  if (!Number.isFinite(hMed) || !Number.isFinite(sMed) || !Number.isFinite(vMed)) {
    setStatus("BAD SAMPLE", false);
    return false;
  }

  // Hue is illumination-invariant, so keep it tight; brightness/saturation swing
  // a lot as the bob moves between lit and shadowed parts of its arc, so allow a
  // wide V (and looser S) floor. The tight hue + connected-component + spatial
  // lock keep background out despite the permissive brightness range.
  const hTol = 16;
  const sLo = Math.max(40, sMed - 110);
  const vLo = Math.max(25, vMed - 150);
  const loH = hMed - hTol;
  const hiH = hMed + hTol;

  const m = { lo: null, hi: null, lo2: null, hi2: null, h: hMed, hTol, sLo, vLo };
  if (loH < 0) {
    m.lo = [0, sLo, vLo];
    m.hi = [hiH, 255, 255];
    m.lo2 = [180 + loH, sLo, vLo];
    m.hi2 = [180, 255, 255];
  } else if (hiH > 180) {
    m.lo = [loH, sLo, vLo];
    m.hi = [180, 255, 255];
    m.lo2 = [0, sLo, vLo];
    m.hi2 = [hiH - 180, 255, 255];
  } else {
    m.lo = [loH, sLo, vLo];
    m.hi = [hiH, 255, 255];
  }
  app.markerHsv = m;
  app.targetSeed = { x: px, y: py };
  app.targetSeedFrames = 90;
  app.lastPos = { x: px, y: py };
  app.smoothPos = { x: px, y: py };
  app.lostFrames = 0;
  drawSampleFeedback(px, py);
  setStatus(`SAMPLED H=${Math.round(hMed)} S=${Math.round(sMed)} V=${Math.round(vMed)}`, true);
  return true;
}

function drawCurrentSourceFrame() {
  resizeCanvas();
  if ((app.videoFileMode || app.stream) && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  }
}

function drawSampleFeedback(px, py) {
  ctx.save();
  ctx.strokeStyle = "#2cff61";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(px, py, 18, 0, Math.PI * 2);
  ctx.stroke();
  drawCross(px, py, 9);
  ctx.restore();
}

function circularHueMean(values) {
  if (!values.length) return 0;
  let sx = 0;
  let sy = 0;
  for (const h of values) {
    const a = h * Math.PI / 90;
    sx += Math.cos(a);
    sy += Math.sin(a);
  }
  let angle = Math.atan2(sy / values.length, sx / values.length);
  if (angle < 0) angle += Math.PI * 2;
  return angle * 90 / Math.PI;
}

function rgbToHsv(r, g, b) {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  const s = max === 0 ? 0 : d / max;
  return [h / 2, s * 255, max * 255];
}

function drawOverlay(result) {
  ctx.save();
  ctx.lineWidth = 2;
  ctx.font = "16px Segoe UI";
  if (app.vLeft) {
    ctx.strokeStyle = "#ffee00";
    drawCross(app.vLeft.x, app.vLeft.y, 11);
    ctx.fillStyle = "#ffee00";
    ctx.fillText("L", app.vLeft.x + 10, app.vLeft.y - 8);
  }
  if (app.vRight) {
    ctx.strokeStyle = "#ffee00";
    drawCross(app.vRight.x, app.vRight.y, 11);
    ctx.fillStyle = "#ffee00";
    ctx.fillText("R", app.vRight.x + 10, app.vRight.y - 8);
  }
  if (app.pivot) {
    ctx.strokeStyle = "#ffee00";
    drawCross(app.pivot.x, app.pivot.y, 13);
    ctx.fillStyle = "#ffee00";
    ctx.fillText("PIVOT", app.pivot.x + 12, app.pivot.y - 10);
  }
  if (app.origin) {
    ctx.strokeStyle = "#ffee00";
    drawCross(app.origin.x, app.origin.y, 13);
    ctx.fillStyle = "#ffee00";
    ctx.fillText("ORIGIN", app.origin.x + 12, app.origin.y - 10);
  }
  if (result.detected) {
    ctx.strokeStyle = "#36ff47";
    ctx.fillStyle = "#36ff47";
    ctx.beginPath();
    ctx.arc(result.x, result.y, 12, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(result.x, result.y, 3, 0, Math.PI * 2);
    ctx.fill();

    if (isPendulumMode() && app.pivot) {
      ctx.strokeStyle = "#d7d7d7";
      ctx.beginPath();
      if (app.vLeft && app.vRight) {
        ctx.moveTo(app.vLeft.x, app.vLeft.y);
        ctx.lineTo(result.x, result.y);
        ctx.moveTo(app.vRight.x, app.vRight.y);
        ctx.lineTo(result.x, result.y);
      } else {
        ctx.moveTo(app.pivot.x, app.pivot.y);
        ctx.lineTo(result.x, result.y);
      }
      ctx.stroke();
      ctx.fillText(`theta=${radToDeg(pendulumAngle(result.x, result.y)).toFixed(1)} deg`, result.x + 18, result.y - 10);
    } else {
      ctx.fillText(`x=${Math.round(result.x)}, y=${Math.round(result.y)}`, result.x + 18, result.y - 10);
    }
  }

  if (app.calibration) {
    ctx.fillStyle = "#ffee00";
    ctx.font = "22px Segoe UI";
    ctx.fillText(experimentCalibrationMessage(), 14, 34);
  } else if (app.picking) {
    ctx.fillStyle = "#ff5cf0";
    ctx.font = "22px Segoe UI";
    ctx.fillText("SAMPLE MARKER", 14, 34);
  }
  ctx.restore();
}

function drawCross(x, y, r) {
  ctx.beginPath();
  ctx.moveTo(x - r, y);
  ctx.lineTo(x + r, y);
  ctx.moveTo(x, y - r);
  ctx.lineTo(x, y + r);
  ctx.stroke();
}

function calibrationMessage() {
  if (app.calibration === "pendulumLeftAnchor") return "[蹂댁젙] ?쇱そ ?곷떒 怨좎젙?먯쓣 ?대┃";
  if (app.calibration === "pendulumRightAnchor") return "[蹂댁젙] ?ㅻⅨ履??곷떒 怨좎젙?먯쓣 ?대┃";
  if (app.calibration === "pendulumBob") return "[蹂댁젙] ?뺤? ?곹깭 異?以묒떖???대┃";
  if (app.calibration === "motionOrigin") return "[蹂댁젙] ?먯젏/?됲삎?먯쓣 ?대┃";
  if (app.calibration === "motionScale") return "[蹂댁젙] 湲곗? 嫄곕━ ?앹젏???대┃";
  return "";
}

function experimentCalibrationMessage() {
  if (app.calibration === "pendulumLeftAnchor") return "[蹂댁젙] ?쇱そ 怨좎젙?먯쓣 ?대┃";
  if (app.calibration === "pendulumRightAnchor") return "[蹂댁젙] ?ㅻⅨ履?怨좎젙?먯쓣 ?대┃";
  if (app.calibration === "pendulumBob") return "[蹂댁젙] ?뺤???異붿쓽 以묒떖???대┃";
  if (app.calibration === "motionOrigin" && isFreefallMode()) return "[蹂댁젙] ?숉븯 ?쒖옉??怨?以묒떖???대┃";
  if (app.calibration === "motionScale" && isFreefallMode()) return "[蹂댁젙] ?꾨옒履?嫄곕━ 湲곗??먯쓣 ?대┃";
  if (app.calibration === "motionOrigin" && isProjectileMode()) return "[蹂댁젙] 諛쒖궗 ?쒖옉??怨?以묒떖???대┃";
  if (app.calibration === "motionScale" && isProjectileMode()) return "[蹂댁젙] 嫄곕━ 湲곗? ?앹젏???대┃";
  if (app.calibration === "motionOrigin") return "[蹂댁젙] ?먯젏/?됲삎?먯쓣 ?대┃";
  if (app.calibration === "motionScale") return "[蹂댁젙] 湲곗? 嫄곕━ ?앹젏???대┃";
  return "";
}

function pendulumAngle(x, y) {
  if (!app.pivot) return 0;
  return wrapPi(Math.atan2(x - app.pivot.x, y - app.pivot.y) - app.restAngle);
}

function updateReadout(result) {
  const last = app.history[app.history.length - 1];
  const lines = [];
  const p = profile();
  lines.push(`mode: ${p.name}`);
  lines.push(`samples: ${app.history.length}`);
  lines.push(`fps: ${app.fps.toFixed(1)}`);
  lines.push(`track: ${result.detected ? "locked" : "lost"}`);
  if (last) {
    if (p.readout === "pendulum") {
      lines.push(`theta: ${last.primary.toFixed(4)} rad`);
      lines.push(`omega: ${last.velocity.toFixed(4)} rad/s`);
      lines.push(`alpha: ${last.acceleration.toFixed(4)} rad/s^2`);
      lines.push(`gamma: ${last.gamma.toFixed(5)}`);
      if (app.vLeft && app.vRight) lines.push(`L_eff: ${Number(els.length.value).toFixed(3)} m`);
    } else if (els.experiment.value === "freefall") {
      appendFreefallReadout(lines, last);
    } else if (els.experiment.value === "projectile") {
      appendProjectileReadout(lines, last);
    } else if (els.experiment.value === "linear_motion") {
      appendLinearReadout(lines, last);
    } else if (els.experiment.value === "spring_mass") {
      appendSpringReadout(lines, last);
    } else if (els.experiment.value === "circular_motion") {
      appendCircularReadout(lines, last);
    } else {
      lines.push(`x: ${last.primary.toFixed(4)} m`);
      lines.push(`y: ${last.y.toFixed(4)} m`);
      lines.push(`vx: ${last.velocity.toFixed(4)} m/s`);
      lines.push(`vy: ${last.vy.toFixed(4)} m/s`);
      lines.push(`speed: ${last.speed.toFixed(4)} m/s`);
      lines.push(`ax: ${last.acceleration.toFixed(4)} m/s^2`);
      lines.push(`ay: ${last.ay.toFixed(4)} m/s^2`);
      lines.push(`force: ${last.force.toFixed(4)} N`);
    }
  }
  els.readout.textContent = lines.join("\n");
}

function appendFreefallReadout(lines, last) {
  const fit = freefallFit();
  lines.push(`y_down: ${last.y.toFixed(4)} m`);
  lines.push(`vy_down: ${last.vy.toFixed(4)} m/s`);
  lines.push(`ay_kalman: ${last.ay.toFixed(4)} m/s^2`);
  lines.push(`g_fit: ${fmt(fit.g)} m/s^2`);
  lines.push(`v0_fit: ${fmt(fit.v0)} m/s`);
  lines.push(`R2: ${fmt(fit.r2)}`);
  const gErr = Number.isFinite(fit.g) ? ((fit.g - 9.81) / 9.81) * 100 : NaN;
  lines.push(`g_error: ${fmt(gErr)} %`);
  lines.push(`t_span: ${fmt(fit.tSpan, 3)} s`);
}

function appendProjectileReadout(lines, last) {
  const rows = app.history.slice(-500);
  const xs = rows.map((r) => r.primary);
  const ys = rows.map((r) => r.y);
  const fit = projectileFit();
  lines.push(`x: ${last.primary.toFixed(4)} m`);
  lines.push(`y: ${last.y.toFixed(4)} m`);
  lines.push(`speed: ${last.speed.toFixed(4)} m/s`);
  lines.push(`range: ${fmt(max(xs) - min(xs))} m`);
  lines.push(`height: ${fmt(max(ys) - min(ys))} m`);
  lines.push(`v0_fit: ${fmt(fit.v0)} m/s`);
  lines.push(`g_fit: ${fmt(fit.g)} m/s^2`);
  lines.push(`R2_y: ${fmt(fit.r2y)}`);
}

function appendLinearReadout(lines, last) {
  const rows = app.history.slice(-120);
  const axMean = mean(rows.map((r) => r.acceleration));
  const mass = Number(els.mass.value) || 0;
  lines.push(`x: ${last.primary.toFixed(4)} m`);
  lines.push(`vx: ${last.velocity.toFixed(4)} m/s`);
  lines.push(`ax: ${last.acceleration.toFixed(4)} m/s^2`);
  lines.push(`mean ax: ${fmt(axMean)} m/s^2`);
  lines.push(`F=ma: ${fmt(mass * axMean)} N`);
}

function appendSpringReadout(lines, last) {
  const rows = app.history.slice(-900);
  const period = estimatePeriod(rows.map((r) => r.time), rows.map((r) => r.primary));
  const omega = Number.isFinite(period) && period > 0 ? (2 * Math.PI) / period : NaN;
  const mass = Number(els.mass.value) || 0;
  lines.push(`x: ${last.primary.toFixed(4)} m`);
  lines.push(`vx: ${last.velocity.toFixed(4)} m/s`);
  lines.push(`ax: ${last.acceleration.toFixed(4)} m/s^2`);
  lines.push(`T: ${fmt(period)} s`);
  lines.push(`omega: ${fmt(omega)} rad/s`);
  lines.push(`k=mw^2: ${fmt(mass * omega * omega)} N/m`);
}

function appendCircularReadout(lines, last) {
  const rows = app.history.slice(-240);
  const radii = rows.map((r) => Math.hypot(r.primary, r.y));
  const speeds = rows.map((r) => r.speed);
  const rMean = mean(radii);
  const vMean = mean(speeds);
  const acModel = rMean > 1e-6 ? (vMean * vMean) / rMean : NaN;
  const acMeasured = mean(rows.map((r) => Math.hypot(r.acceleration, r.ay || 0)));
  lines.push(`r: ${fmt(rMean)} m`);
  lines.push(`speed: ${last.speed.toFixed(4)} m/s`);
  lines.push(`mean speed: ${fmt(vMean)} m/s`);
  lines.push(`v^2/r: ${fmt(acModel)} m/s^2`);
  lines.push(`|a| measured: ${fmt(acMeasured)} m/s^2`);
}

function mean(values) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return NaN;
  return finite.reduce((s, v) => s + v, 0) / finite.length;
}

function min(values) {
  const finite = values.filter(Number.isFinite);
  return finite.length ? Math.min(...finite) : NaN;
}

function max(values) {
  const finite = values.filter(Number.isFinite);
  return finite.length ? Math.max(...finite) : NaN;
}

function fmt(value, digits = 4) {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function freefallFit() {
  const rows = app.history.filter((r) => Number.isFinite(r.time) && Number.isFinite(r.y));
  const fit = fitQuadratic(rows, (r) => r.y);
  return {
    g: fit.a,
    v0: fit.v0,
    y0: fit.p0,
    r2: fit.r2,
    tSpan: fit.tSpan,
  };
}

function projectileFit() {
  const rows = app.history.filter((r) => Number.isFinite(r.time) && Number.isFinite(r.primary) && Number.isFinite(r.y));
  const xFit = fitLinear(rows, (r) => r.primary);
  const yFit = fitQuadratic(rows, (r) => r.y);
  const v0 = Number.isFinite(xFit.v) && Number.isFinite(yFit.v0) ? Math.hypot(xFit.v, yFit.v0) : NaN;
  return {
    vx0: xFit.v,
    vy0: yFit.v0,
    v0,
    g: Number.isFinite(yFit.a) ? -yFit.a : NaN,
    r2x: xFit.r2,
    r2y: yFit.r2,
    tSpan: Math.max(xFit.tSpan || 0, yFit.tSpan || 0),
  };
}

function fitQuadratic(rows, valueOf) {
  if (rows.length < 6) return emptyFit();
  const t0 = rows[0].time;
  const sums = {
    n: 0, t: 0, t2: 0, t3: 0, t4: 0, y: 0, ty: 0, t2y: 0,
  };
  const values = [];
  for (const r of rows) {
    const t = r.time - t0;
    const y = valueOf(r);
    if (!Number.isFinite(t) || !Number.isFinite(y)) continue;
    const q = 0.5 * t * t;
    sums.n += 1;
    sums.t += t;
    sums.t2 += t * t;
    sums.t3 += t * t * t;
    sums.t4 += t * t * t * t;
    sums.y += y;
    sums.ty += t * y;
    sums.t2y += q * y;
    values.push({ t, y });
  }
  if (sums.n < 6) return emptyFit();
  const A = [
    [sums.n, sums.t, 0.5 * sums.t2],
    [sums.t, sums.t2, 0.5 * sums.t3],
    [0.5 * sums.t2, 0.5 * sums.t3, 0.25 * sums.t4],
  ];
  const b = [sums.y, sums.ty, sums.t2y];
  const beta = solve3(A, b);
  if (!beta) return emptyFit();
  const [p0, v0, a] = beta;
  const yMean = sums.y / sums.n;
  let ssRes = 0;
  let ssTot = 0;
  for (const p of values) {
    const yHat = p0 + v0 * p.t + 0.5 * a * p.t * p.t;
    ssRes += (p.y - yHat) ** 2;
    ssTot += (p.y - yMean) ** 2;
  }
  return { p0, v0, a, r2: ssTot > 1e-12 ? 1 - ssRes / ssTot : NaN, tSpan: values[values.length - 1].t - values[0].t };
}

function fitLinear(rows, valueOf) {
  if (rows.length < 3) return { p0: NaN, v: NaN, r2: NaN, tSpan: NaN };
  const t0 = rows[0].time;
  const values = [];
  let n = 0, st = 0, sy = 0, stt = 0, sty = 0;
  for (const r of rows) {
    const t = r.time - t0;
    const y = valueOf(r);
    if (!Number.isFinite(t) || !Number.isFinite(y)) continue;
    n += 1; st += t; sy += y; stt += t * t; sty += t * y;
    values.push({ t, y });
  }
  const det = n * stt - st * st;
  if (n < 3 || Math.abs(det) < 1e-12) return { p0: NaN, v: NaN, r2: NaN, tSpan: NaN };
  const p0 = (sy * stt - st * sty) / det;
  const v = (n * sty - st * sy) / det;
  const yMean = sy / n;
  let ssRes = 0;
  let ssTot = 0;
  for (const p of values) {
    const yHat = p0 + v * p.t;
    ssRes += (p.y - yHat) ** 2;
    ssTot += (p.y - yMean) ** 2;
  }
  return { p0, v, r2: ssTot > 1e-12 ? 1 - ssRes / ssTot : NaN, tSpan: values[values.length - 1].t - values[0].t };
}

function solve3(A, b) {
  const M = A.map((row, i) => row.concat([b[i]]));
  for (let col = 0; col < 3; col++) {
    let pivot = col;
    for (let r = col + 1; r < 3; r++) {
      if (Math.abs(M[r][col]) > Math.abs(M[pivot][col])) pivot = r;
    }
    if (Math.abs(M[pivot][col]) < 1e-12) return null;
    if (pivot !== col) [M[pivot], M[col]] = [M[col], M[pivot]];
    const div = M[col][col];
    for (let c = col; c < 4; c++) M[col][c] /= div;
    for (let r = 0; r < 3; r++) {
      if (r === col) continue;
      const factor = M[r][col];
      for (let c = col; c < 4; c++) M[r][c] -= factor * M[col][c];
    }
  }
  return [M[0][3], M[1][3], M[2][3]];
}

function emptyFit() {
  return { p0: NaN, v0: NaN, a: NaN, r2: NaN, tSpan: NaN };
}

function estimatePeriod(times, values) {
  if (times.length < 20 || values.length < 20) return NaN;
  const centered = values.map((v) => v - mean(values));
  const peaks = [];
  const amp = Math.max(...centered.map(Math.abs));
  const threshold = Math.max(amp * 0.25, 0.002);
  for (let i = 1; i < centered.length - 1; i++) {
    if (centered[i] > threshold && centered[i] > centered[i - 1] && centered[i] >= centered[i + 1]) {
      peaks.push(times[i]);
    }
  }
  if (peaks.length < 2) return NaN;
  const intervals = [];
  for (let i = 1; i < peaks.length; i++) intervals.push(peaks[i] - peaks[i - 1]);
  return mean(intervals);
}

function drawPlots() {
  const p = profile();
  drawLinePlot(els.plotTheta, `${p.primary[0]} (${p.primary[1]})`, plotSeries("primary"), "#ffb000", secondarySeries("primary"), "#777");
  drawLinePlot(els.plotOmega, `${p.velocity[0]} (${p.velocity[1]})`, plotSeries("velocity"), "#2cc7ff", secondarySeries("velocity"), "#ff5b5b");
  drawLinePlot(els.plotAlpha, `${p.acceleration[0]} (${p.acceleration[1]})`, plotSeries("acceleration"), "#61d861", secondarySeries("acceleration"), "#ff5b5b");
  drawPhasePlot(els.plotPhase);
}

function plotSeries(kind) {
  const p = profile();
  if (p.readout === "vertical") {
    if (kind === "primary") return app.history.map((r) => r.y);
    if (kind === "velocity") return app.history.map((r) => r.vy);
    return app.history.map((r) => r.ay);
  }
  if (["projectile", "circular_motion"].includes(els.experiment.value)) {
    if (kind === "velocity") return app.history.map((r) => r.speed);
    if (kind === "acceleration") return app.history.map((r) => Math.hypot(r.acceleration, r.ay || 0));
  }
  return app.history.map((r) => {
    if (kind === "primary") return r.primary;
    if (kind === "velocity") return r.velocity;
    return r.acceleration;
  });
}

function secondarySeries(kind) {
  const p = profile();
  if (p.readout === "vertical") {
    if (kind === "primary") return app.history.map((r) => r.measuredY);
    if (kind === "velocity") return app.history.map((r) => r.numVelocityY);
    return app.history.map((r) => r.numAccelerationY);
  }
  if (["projectile", "circular_motion"].includes(els.experiment.value)) return [];
  if (kind === "primary") return app.history.map((r) => r.measured);
  if (kind === "velocity") return app.history.map((r) => r.numVelocity);
  return app.history.map((r) => r.numAcceleration);
}

function drawLinePlot(plotCanvas, title, data, color, data2, color2) {
  fitPlotCanvas(plotCanvas);
  const c = plotCanvas.getContext("2d");
  const w = plotCanvas.width;
  const h = plotCanvas.height;
  c.clearRect(0, 0, w, h);
  c.fillStyle = "#181b1f";
  c.fillRect(0, 0, w, h);
  c.strokeStyle = "#30363d";
  c.strokeRect(0, 0, w, h);
  c.fillStyle = "#e7edf3";
  c.font = "14px Segoe UI";
  c.fillText(title, 10, 22);
  const d = data.slice(-360);
  const e = data2.slice(-360);
  if (d.length < 2) return;
  const all = d.concat(e);
  let min = Math.min(...all);
  let max = Math.max(...all);
  const margin = Math.max((max - min) * 0.15, 0.01);
  min -= margin;
  max += margin;
  drawSeries(c, d, min, max, color, w, h);
  if (e.length >= 2) drawSeries(c, e, min, max, color2, w, h);
}

function drawSeries(c, data, min, max, color, w, h) {
  c.strokeStyle = color;
  c.lineWidth = 2;
  c.beginPath();
  data.forEach((v, i) => {
    const x = 36 + (i / Math.max(data.length - 1, 1)) * (w - 48);
    const y = 30 + (1 - (v - min) / Math.max(max - min, 1e-9)) * (h - 44);
    if (i === 0) c.moveTo(x, y);
    else c.lineTo(x, y);
  });
  c.stroke();
}

function drawPhasePlot(plotCanvas) {
  fitPlotCanvas(plotCanvas);
  const c = plotCanvas.getContext("2d");
  const w = plotCanvas.width;
  const h = plotCanvas.height;
  c.clearRect(0, 0, w, h);
  c.fillStyle = "#181b1f";
  c.fillRect(0, 0, w, h);
  c.strokeStyle = "#30363d";
  c.strokeRect(0, 0, w, h);
  c.fillStyle = "#e7edf3";
  c.font = "14px Segoe UI";
  const p = profile();
  const neural = app.neuralResult;
  const phaseTitle = neural?.mode === "projectile" ? "y-vy phase" : `${p.primary[0]}-${p.velocity[0]} phase`;
  c.fillText(phaseTitle, 10, 22);
  const rows = app.history.slice(-500);
  if (rows.length < 2) return;
  const start = Math.max(app.history.length - rows.length, 0);
  const xs = neural?.mode === "projectile"
    ? rows.map((r) => r.y)
    : plotSeries("primary").slice(start);
  const ys = neural?.mode === "projectile"
    ? rows.map((r) => r.vy)
    : plotSeries("velocity").slice(start);
  let minX = Math.min(...xs), maxX = Math.max(...xs);
  let minY = Math.min(...ys), maxY = Math.max(...ys);
  if (neural?.prediction?.pos?.length) {
    minX = Math.min(minX, ...neural.prediction.pos);
    maxX = Math.max(maxX, ...neural.prediction.pos);
    minY = Math.min(minY, ...neural.prediction.vel);
    maxY = Math.max(maxY, ...neural.prediction.vel);
  }
  if (neural?.vector_field?.length) {
    minX = Math.min(minX, ...neural.vector_field.map((v) => v.pos));
    maxX = Math.max(maxX, ...neural.vector_field.map((v) => v.pos));
    minY = Math.min(minY, ...neural.vector_field.map((v) => v.vel));
    maxY = Math.max(maxY, ...neural.vector_field.map((v) => v.vel));
  }
  const mx = Math.max((maxX - minX) * 0.15, 0.01);
  const my = Math.max((maxY - minY) * 0.15, 0.01);
  minX -= mx; maxX += mx; minY -= my; maxY += my;
  const px = (x) => 36 + ((x - minX) / Math.max(maxX - minX, 1e-9)) * (w - 54);
  const py = (y) => 34 + (1 - (y - minY) / Math.max(maxY - minY, 1e-9)) * (h - 52);

  if (neural?.vector_field?.length) {
    drawVectorField(c, neural.vector_field, px, py);
  }
  if (neural?.prediction?.pos?.length) {
    c.strokeStyle = "#2cc7ff";
    c.lineWidth = 2;
    c.beginPath();
    neural.prediction.pos.forEach((xv, i) => {
      const x = px(xv);
      const y = py(neural.prediction.vel[i]);
      if (i === 0) c.moveTo(x, y);
      else c.lineTo(x, y);
    });
    c.stroke();
  }

  c.strokeStyle = "#ffdf4d";
  c.lineWidth = 2;
  c.beginPath();
  rows.forEach((_, i) => {
    const x = px(xs[i]);
    const y = py(ys[i]);
    if (i === 0) c.moveTo(x, y);
    else c.lineTo(x, y);
  });
  c.stroke();
}

function drawVectorField(c, vectors, px, py) {
  const mags = vectors.map((v) => Math.hypot(v.dpos, v.dvel)).filter(Number.isFinite);
  const scale = Math.max(...mags, 1e-9);
  c.strokeStyle = "rgba(216, 225, 234, 0.42)";
  c.lineWidth = 1;
  for (const v of vectors) {
    const x = px(v.pos);
    const y = py(v.vel);
    const len = 10;
    const dx = (v.dpos / scale) * len;
    const dy = -(v.dvel / scale) * len;
    c.beginPath();
    c.moveTo(x - dx * 0.5, y - dy * 0.5);
    c.lineTo(x + dx * 0.5, y + dy * 0.5);
    c.stroke();
  }
}

function fitPlotCanvas(plotCanvas) {
  const rect = plotCanvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(200, Math.floor(rect.width * dpr));
  const h = Math.max(140, Math.floor(rect.height * dpr));
  if (plotCanvas.width !== w || plotCanvas.height !== h) {
    plotCanvas.width = w;
    plotCanvas.height = h;
  }
}

function clearAllPlots() {
  const p = profile();
  clearPlot(els.plotTheta, `${p.primary[0]} (${p.primary[1]})`);
  clearPlot(els.plotOmega, `${p.velocity[0]} (${p.velocity[1]})`);
  clearPlot(els.plotAlpha, `${p.acceleration[0]} (${p.acceleration[1]})`);
  clearPlot(els.plotPhase, `${p.primary[0]}-${p.velocity[0]} phase`);
}

function clearPlot(plotCanvas, title) {
  fitPlotCanvas(plotCanvas);
  const c = plotCanvas.getContext("2d");
  c.clearRect(0, 0, plotCanvas.width, plotCanvas.height);
  c.fillStyle = "#181b1f";
  c.fillRect(0, 0, plotCanvas.width, plotCanvas.height);
  c.strokeStyle = "#30363d";
  c.strokeRect(0, 0, plotCanvas.width, plotCanvas.height);
  c.fillStyle = "#e7edf3";
  c.font = "14px Segoe UI";
  c.fillText(title, 10, 22);
}

function startCalibration() {
  app.picking = false;
  pauseVideoForSelection();
  if (isPendulumMode()) {
    app.calibration = "pendulumLeftAnchor";
    app.vLeft = null;
    app.vRight = null;
    app.pivot = null;
  } else {
    app.calibration = "motionOrigin";
  }
  setStatus("CAL", false);
}

function startPickColor() {
  app.picking = true;
  app.calibration = null;
  pauseVideoForSelection();
  setStatus("SAMPLE", false);
}

function pauseVideoForSelection() {
  if (!app.videoFileMode || video.paused) {
    app.selectionPausedVideo = false;
    return;
  }
  video.pause();
  app.selectionPausedVideo = true;
  drawCurrentSourceFrame();
}

function resumeVideoAfterSelection() {
  if (!app.videoFileMode || !app.selectionPausedVideo) return;
  app.selectionPausedVideo = false;
  video.play().catch(() => setStatus("VIDEO PAUSED", false));
}

function handleCanvasClick(ev) {
  if (!app.calibration && !app.picking) return;
  const rect = canvas.getBoundingClientRect();
  const p = {
    x: ((ev.clientX - rect.left) / rect.width) * canvas.width,
    y: ((ev.clientY - rect.top) / rect.height) * canvas.height,
  };

  if (app.picking) {
    const ok = pickColorAt(p.x, p.y);
    app.picking = false;
    if (ok) resumeVideoAfterSelection();
    return;
  }

  if (app.calibration === "pendulumLeftAnchor") {
    app.vLeft = p;
    app.calibration = "pendulumRightAnchor";
    return;
  }
  if (app.calibration === "pendulumRightAnchor") {
    app.vRight = p;
    app.pivot = midpoint(app.vLeft, app.vRight);
    app.calibration = "pendulumBob";
    return;
  }
  if (app.calibration === "pendulumBob") {
    pickColorAt(p.x, p.y);
    app.stringPixels = Math.hypot(p.x - app.pivot.x, p.y - app.pivot.y);
    app.restAngle = Math.atan2(p.x - app.pivot.x, p.y - app.pivot.y);
    updatePendulumLengthFromCalibration(p);
    app.calibration = null;
    resetExperiment();
    // Seed the spatial lock at the clicked bob (after reset, which clears it) so
    // tracking grabs the bob and ignores larger same-hue regions like the face.
    app.lastPos = { x: p.x, y: p.y };
    app.smoothPos = { x: p.x, y: p.y };
    app.lostFrames = 0;
    setStatus("RUN", true);
    resumeVideoAfterSelection();
    return;
  }
  if (app.calibration === "motionOrigin") {
    app.origin = p;
    app.scaleStart = p;
    app.calibration = "motionScale";
    return;
  }
  if (app.calibration === "motionScale") {
    const distPx = Math.hypot(p.x - app.scaleStart.x, p.y - app.scaleStart.y);
    const distM = Number(els.scaleDistance.value) || 1;
    app.pixelsPerMeter = distPx > 0 ? distPx / distM : app.pixelsPerMeter;
    app.calibration = null;
    resetExperiment();
    setStatus("RUN", true);
    resumeVideoAfterSelection();
  }
}

function midpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function updatePendulumLengthFromCalibration(bob) {
  if (!app.vLeft || !app.vRight || !app.pivot || !bob) return;
  const halfSpanPx = Math.hypot(app.vRight.x - app.vLeft.x, app.vRight.y - app.vLeft.y) / 2;
  const oneStringPx = (Math.hypot(bob.x - app.vLeft.x, bob.y - app.vLeft.y) + Math.hypot(bob.x - app.vRight.x, bob.y - app.vRight.y)) / 2;
  const effectivePx = Math.sqrt(Math.max(oneStringPx * oneStringPx - halfSpanPx * halfSpanPx, 0));
  app.stringPixels = effectivePx || app.stringPixels;
  const enteredStringLengthM = Number(els.length.value) || 0.7;
  const lengthM = oneStringPx > 0 ? enteredStringLengthM * (app.stringPixels / oneStringPx) : enteredStringLengthM;
  if (Number.isFinite(lengthM) && lengthM >= 0.1) {
    els.length.value = lengthM.toFixed(3);
  }
}

function resetExperiment() {
  app.history = [];
  app.estimator = null;
  app.neuralResult = null;
  app.lastPos = null;
  app.smoothPos = null;
  app.lostFrames = 0;
  app.lastMediaTime = null;
  if (app.videoFileMode && isBallisticsMode() && video.readyState >= HTMLMediaElement.HAVE_METADATA) {
    video.currentTime = 0;
    if (!app.selectionPausedVideo) {
      video.play().catch(() => setStatus("VIDEO PAUSED", false));
    }
  }
  currentEstimator();
  clearAllPlots();
  updateReadout({ detected: false });
}

function resetExperimentSession() {
  app.calibration = null;
  app.picking = false;
  app.pivot = null;
  app.vLeft = null;
  app.vRight = null;
  app.restAngle = 0;
  app.stringPixels = 0;
  app.origin = null;
  app.scaleStart = null;
  app.pixelsPerMeter = 300;
  app.markerHsv = null;
  app.targetSeed = null;
  app.targetSeedFrames = 0;
  app.lastMeasurement = null;
  app.neuralResult = null;
  app.selectionPausedVideo = false;
  resetExperimentInputs();
  resetExperiment();
  setStatus("MODE RESET", false);
}

function resetExperimentInputs() {
  els.length.value = "0.22";
  els.mass.value = "0.05";
  els.scaleDistance.value = "1.0";
  els.lambdaThreshold.value = "0.30";
}

function csvText() {
  const headers = [
    "time",
    "experiment",
    "primary_kalman",
    "velocity_kalman",
    "acceleration_kalman",
    "primary_measured",
    "velocity_numerical",
    "acceleration_numerical",
    "primary_std",
    "velocity_std",
    "innovation",
    "gamma",
    "gamma_std",
    "x_kalman",
    "y_kalman",
    "vx_kalman",
    "vy_kalman",
    "ax_kalman",
    "ay_kalman",
    "speed",
    "force",
    "primary_measured_y",
    "velocity_y_numerical",
    "acceleration_y_numerical",
    "fit_g",
    "fit_v0",
    "fit_vx0",
    "fit_vy0",
    "fit_r2",
    "fit_t_span",
  ];
  const lines = [headers.join(",")];
  const freeFit = isFreefallMode() ? freefallFit() : null;
  const projFit = isProjectileMode() ? projectileFit() : null;
  for (const r of app.history) {
    const fit = isFreefallMode() ? {
      g: freeFit.g,
      v0: freeFit.v0,
      vx0: "",
      vy0: freeFit.v0,
      r2: freeFit.r2,
      tSpan: freeFit.tSpan,
    } : isProjectileMode() ? {
      g: projFit.g,
      v0: projFit.v0,
      vx0: projFit.vx0,
      vy0: projFit.vy0,
      r2: projFit.r2y,
      tSpan: projFit.tSpan,
    } : {};
    lines.push([
      r.time,
      els.experiment.value,
      r.primary,
      r.velocity,
      r.acceleration,
      r.measured,
      r.numVelocity,
      r.numAcceleration,
      r.primaryStd,
      r.velocityStd,
      r.innovation,
      r.gamma ?? "",
      r.gammaStd ?? "",
      r.primary ?? "",
      r.y ?? "",
      r.velocity ?? "",
      r.vy ?? "",
      r.acceleration ?? "",
      r.ay ?? "",
      r.speed ?? "",
      r.force ?? "",
      r.measuredY ?? "",
      r.numVelocityY ?? "",
      r.numAccelerationY ?? "",
      fit.g ?? "",
      fit.v0 ?? "",
      fit.vx0 ?? "",
      fit.vy0 ?? "",
      fit.r2 ?? "",
      fit.tSpan ?? "",
    ].map((v) => typeof v === "number" ? v.toFixed(8) : v).join(","));
  }
  return lines.join("\n");
}

function saveCsv() {
  if (!app.history.length) return;
  const blob = new Blob([csvText()], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${els.experiment.value}_web_data_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function discoverEquation() {
  if (!isPendulumMode()) {
    els.equationOutput.textContent = `${profile().name}: ${experimentNote()}\nCSV export includes the measured time series.`;
    return;
  }
  if (app.history.length < 80) {
    els.equationOutput.textContent = "?섑뵆??遺議깊빀?덈떎. 理쒖냼 8~12珥??뺣룄 湲곕줉?????ㅼ떆 ?ㅽ뻾?섏꽭??";
    return;
  }
  els.equationOutput.textContent = "遺꾩꽍 以?..";
  try {
    const res = await fetch("/api/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lambda_threshold: Number(els.lambdaThreshold.value) || 0.3,
        rows: app.history,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "analysis failed");
    els.equationOutput.textContent = [
      data.equation,
      "",
      `train RMSE: ${data.train_rmse.toFixed(6)}`,
      `test RMSE : ${data.test_rmse.toFixed(6)}`,
      `sigma_hat : ${data.sigma_meas.toFixed(6)}`,
      `q_jerk    : ${data.q_jerk.toExponential(3)}`,
    ].join("\n");
  } catch (err) {
    els.equationOutput.textContent = `遺꾩꽍 ?ㅽ뙣: ${err.message}\nweb_server.py濡??ㅽ뻾 以묒씤吏 ?뺤씤?섏꽭??`;
  }
}

async function discoverNeural() {
  const neuralModes = {
    pendulum: { mode: "pendulum", series: "measured" },
    spring_mass: { mode: "spring", series: "measured" },
    freefall: { mode: "freefall", series: "y" },
    projectile: { mode: "projectile", series: "y" },
    linear_motion: { mode: "linear", series: "measured" },
  };
  const spec = neuralModes[els.experiment.value] || null;
  const mode = spec?.mode || null;
  if (!mode) {
    els.equationOutput.textContent = `${profile().name}: Neural ODE discovery is available for pendulum, spring-mass, free-fall, projectile, and linear cart modes.`;
    return;
  }
  if (app.history.length < 100) {
    els.equationOutput.textContent = "Not enough samples. Record 10+ seconds, then try Neural ODE again.";
    return;
  }
  els.equationOutput.textContent = "Training Neural ODE... this can take 1-2 minutes.";
  try {
    const res = await fetch("/api/discover_neural", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frac: 0.5, mode, series: spec.series, rows: app.history }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "analysis failed");
    const isSpring = data.mode === "spring";
    app.neuralResult = data;
    els.equationOutput.textContent = [
      `[Neural ODE + ${data.symbolic_backend || "symbolic regression"}]`,
      data.equation,
      "",
      `${data.const_name} cross-check:`,
      `  Neural ODE + SR    : ${fmt(data.const_neural_ode, 2)}`,
      `  STLSQ (SINDy)      : ${fmt(data.const_stlsq, 2)}`,
      `  Period (2pi/T)^2   : ${fmt(data.const_period, 2)}`,
      `damping / v term     : ${fmt(data.damping, 4)}`,
      `amplitude/span       : ${fmt(data.amplitude, isSpring ? 3 : 2)}${data.mode === "pendulum" ? " deg" : ""}`,
      "phase plot overlay   : vector field + Neural ODE prediction",
    ].join("\n");
    drawPlots();
  } catch (err) {
    app.neuralResult = null;
    els.equationOutput.textContent =
      `Neural ODE failed: ${err.message}\nInstall ML deps with requirements-ml.txt and run locally.`;
  }
}

async function fitExperimentModel() {
  if (isFreefallMode()) {
    const fit = freefallFit();
    if (!Number.isFinite(fit.g)) {
      els.equationOutput.textContent = "Not enough free-fall samples. Calibrate, sample the marker, then record one clean drop.";
      return;
    }
    const err = ((fit.g - 9.81) / 9.81) * 100;
    els.equationOutput.textContent = [
      "Free fall fit: y_down = y0 + v0*t + 0.5*g*t^2",
      "",
      `g_fit  : ${fit.g.toFixed(4)} m/s^2`,
      `v0_fit : ${fit.v0.toFixed(4)} m/s`,
      `g_error: ${err.toFixed(2)} %`,
      `R2     : ${fit.r2.toFixed(4)}`,
      `t_span : ${fit.tSpan.toFixed(3)} s`,
    ].join("\n");
    return;
  }
  if (isProjectileMode()) {
    const fit = projectileFit();
    if (!Number.isFinite(fit.g)) {
      els.equationOutput.textContent = "Not enough projectile samples. Calibrate, sample the marker, then record one clean throw.";
      return;
    }
    els.equationOutput.textContent = [
      "Projectile fit: x = x0 + vx0*t, y = y0 + vy0*t - 0.5*g*t^2",
      "",
      `vx0    : ${fit.vx0.toFixed(4)} m/s`,
      `vy0    : ${fit.vy0.toFixed(4)} m/s`,
      `v0     : ${fit.v0.toFixed(4)} m/s`,
      `g_fit  : ${fit.g.toFixed(4)} m/s^2`,
      `R2_x   : ${fit.r2x.toFixed(4)}`,
      `R2_y   : ${fit.r2y.toFixed(4)}`,
      `t_span : ${fit.tSpan.toFixed(3)} s`,
    ].join("\n");
    return;
  }
  if (!isPendulumMode()) {
    els.equationOutput.textContent = `${profile().name}: ${experimentNote()}\nCSV export includes the measured time series.`;
    return;
  }
  if (app.history.length < 80) {
    els.equationOutput.textContent = "Not enough samples. Record at least 8-12 seconds, then try again.";
    return;
  }
  els.equationOutput.textContent = "Fitting model...";
  try {
    const res = await fetch("/api/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lambda_threshold: Number(els.lambdaThreshold.value) || 0.3,
        rows: app.history,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "analysis failed");
    els.equationOutput.textContent = [
      data.equation,
      "",
      `train RMSE: ${data.train_rmse.toFixed(6)}`,
      `test RMSE : ${data.test_rmse.toFixed(6)}`,
      `sigma_hat : ${data.sigma_meas.toFixed(6)}`,
      `q_jerk    : ${data.q_jerk.toExponential(3)}`,
    ].join("\n");
  } catch (err) {
    els.equationOutput.textContent = `Fit failed: ${err.message}\nCheck that web_server.py is running.`;
  }
}

function wrapPi(v) {
  while (v > Math.PI) v -= 2 * Math.PI;
  while (v < -Math.PI) v += 2 * Math.PI;
  return v;
}

function radToDeg(v) {
  return v * 180 / Math.PI;
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function diag(values) {
  return values.map((v, i) => values.map((_, j) => i === j ? v : 0));
}

function identity(n) {
  return diag(Array(n).fill(1));
}

function cloneMat(A) {
  return A.map((row) => row.slice());
}

function transpose(A) {
  return A[0].map((_, i) => A.map((row) => row[i]));
}

function matMul(A, B) {
  const out = Array.from({ length: A.length }, () => Array(B[0].length).fill(0));
  for (let i = 0; i < A.length; i++) {
    for (let k = 0; k < B.length; k++) {
      for (let j = 0; j < B[0].length; j++) out[i][j] += A[i][k] * B[k][j];
    }
  }
  return out;
}

function matVec(A, x) {
  return A.map((row) => row.reduce((s, v, i) => s + v * x[i], 0));
}

function addMat(A, B) {
  return A.map((row, i) => row.map((v, j) => v + B[i][j]));
}

function subMat(A, B) {
  return A.map((row, i) => row.map((v, j) => v - B[i][j]));
}

function addVec(a, b) {
  return a.map((v, i) => v + b[i]);
}

function subVec(a, b) {
  return a.map((v, i) => v - b[i]);
}

function scaleVec(a, s) {
  return a.map((v) => v * s);
}

function inv2(A) {
  const det = A[0][0] * A[1][1] - A[0][1] * A[1][0];
  const d = Math.abs(det) < 1e-12 ? 1e-12 : det;
  return [
    [A[1][1] / d, -A[0][1] / d],
    [-A[1][0] / d, A[0][0] / d],
  ];
}

function handleSelectedVideoFile(file) {
  if (!file) return;
  startVideoFile(file).catch((err) => setStatus(err.message, false));
}

els.startCamera.addEventListener("click", () => startCamera().catch((err) => setStatus(err.message, false)));
els.uploadVideo.addEventListener("click", () => setStatus("SELECT FILE", false));
els.uploadVideo.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" || ev.key === " ") {
    ev.preventDefault();
    setStatus("SELECT FILE", false);
    els.videoFile.click();
  }
});
els.videoFile.addEventListener("change", (ev) => {
  const file = ev.target.files && ev.target.files[0];
  handleSelectedVideoFile(file);
  ev.target.value = "";
});
els.cameraPanel.addEventListener("dragover", (ev) => {
  ev.preventDefault();
  setStatus("DROP VIDEO", false);
});
els.cameraPanel.addEventListener("drop", (ev) => {
  ev.preventDefault();
  const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
  handleSelectedVideoFile(file);
});
els.pickColor.addEventListener("click", startPickColor);
els.calibrate.addEventListener("click", startCalibration);
els.reset.addEventListener("click", resetExperiment);
els.saveCsv.addEventListener("click", saveCsv);
els.discover.addEventListener("click", fitExperimentModel);
els.discoverNeural.addEventListener("click", discoverNeural);
canvas.addEventListener("click", handleCanvasClick);
els.experiment.addEventListener("change", () => {
  resetExperimentSession();
  updateExperimentUi();
  els.equationOutput.textContent = experimentNote();
});
els.color.addEventListener("change", () => {
  app.markerHsv = null;
  app.targetSeed = null;
  app.targetSeedFrames = 0;
  resetExperiment();
  setStatus(`COLOR ${els.color.value.toUpperCase()}`, false);
});
document.addEventListener("keydown", (ev) => {
  if (ev.key.toLowerCase() === "p") startPickColor();
  if (ev.key.toLowerCase() === "c") startCalibration();
  if (ev.key.toLowerCase() === "r") resetExperiment();
  if (ev.key.toLowerCase() === "s") saveCsv();
});

currentEstimator();
updateExperimentUi();
els.equationOutput.textContent = experimentNote();
setStatus("OFF", false);
