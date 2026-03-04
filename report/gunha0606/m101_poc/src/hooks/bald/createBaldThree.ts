import * as THREE from "three";

type HairMaskOnly = {
  resize: (w: number, h: number) => void;
  updateHairMask: (mask01: Uint8ClampedArray, mw: number, mh: number) => void;

  // ✅ 디버그(마스크 그대로 그리기)
  debugDrawHairMaskTo: (ctx: CanvasRenderingContext2D, w: number, h: number) => void;

  // ✅ 합성용(알파 마스크로 사용)
  drawMaskTo: (ctx: CanvasRenderingContext2D, w: number, h: number) => void;

  dispose: () => void;
};

// ✅ 마스크 확장(dilate) - 범위 넓히기
function dilateBinary(src01: Uint8ClampedArray, w: number, h: number, r: number) {
  const out = new Uint8ClampedArray(w * h);
  const rad = Math.max(1, r | 0);

  for (let y = 0; y < h; y++) {
    const y0 = Math.max(0, y - rad);
    const y1 = Math.min(h - 1, y + rad);
    for (let x = 0; x < w; x++) {
      const x0 = Math.max(0, x - rad);
      const x1 = Math.min(w - 1, x + rad);

      let v = 0;
      for (let yy = y0; yy <= y1 && v === 0; yy++) {
        const row = yy * w;
        for (let xx = x0; xx <= x1; xx++) {
          if (src01[row + xx]) {
            v = 1;
            break;
          }
        }
      }
      out[y * w + x] = v;
    }
  }
  return out;
}

// ✅ 0/255 알파 페더(박스 블러)
function boxBlur255(src255: Uint8ClampedArray, w: number, h: number, r: number) {
  const rad = Math.max(1, r | 0);
  const tmp = new Uint8ClampedArray(w * h);
  const out = new Uint8ClampedArray(w * h);
  const win = 2 * rad + 1;

  // horizontal
  for (let y = 0; y < h; y++) {
    const row = y * w;
    let sum = 0;

    for (let i = -rad; i <= rad; i++) {
      const x = Math.min(w - 1, Math.max(0, i));
      sum += src255[row + x];
    }
    tmp[row] = (sum / win) | 0;

    for (let x = 1; x < w; x++) {
      const addX = Math.min(w - 1, x + rad);
      const subX = Math.max(0, x - rad - 1);
      sum += src255[row + addX] - src255[row + subX];
      tmp[row + x] = (sum / win) | 0;
    }
  }

  // vertical
  for (let x = 0; x < w; x++) {
    let sum = 0;

    for (let i = -rad; i <= rad; i++) {
      const y = Math.min(h - 1, Math.max(0, i));
      sum += tmp[y * w + x];
    }
    out[x] = (sum / win) | 0;

    for (let y = 1; y < h; y++) {
      const addY = Math.min(h - 1, y + rad);
      const subY = Math.max(0, y - rad - 1);
      sum += tmp[addY * w + x] - tmp[subY * w + x];
      out[y * w + x] = (sum / win) | 0;
    }
  }

  return out;
}

export function createBaldThree(canvas: HTMLCanvasElement): HairMaskOnly {
  // Three는 “텍스처 업데이트 관리”용으로만 남김 (렌더 안 해도 됨)
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setClearColor(0x000000, 0);

  // mask canvas -> texture
  const maskCanvas = document.createElement("canvas");
  maskCanvas.width = 512;
  maskCanvas.height = 512;
  const mctx = maskCanvas.getContext("2d")!;
  const maskTex = new THREE.CanvasTexture(maskCanvas);
  maskTex.minFilter = THREE.LinearFilter;
  maskTex.magFilter = THREE.LinearFilter;
  maskTex.generateMipmaps = false;

  // ✅ 튜닝 포인트
  const DILATE_R = 1; // 0=끔, 1~2=넓게
  const BLUR_R = 2;   // 0=끔, 1~3=경계 부드럽게

  function resize(w: number, h: number) {
    renderer.setSize(w, h, false);
  }

  function updateHairMask(mask01: Uint8ClampedArray, mw: number, mh: number) {
    if (maskCanvas.width !== mw) maskCanvas.width = mw;
    if (maskCanvas.height !== mh) maskCanvas.height = mh;

    // 1) dilation
    let m01 = mask01;
    if (DILATE_R > 0) m01 = dilateBinary(mask01, mw, mh, DILATE_R);

    // 2) alpha 0/255
    const a255 = new Uint8ClampedArray(mw * mh);
    for (let i = 0; i < mw * mh; i++) a255[i] = m01[i] ? 255 : 0;

    // 3) feather
    const aFeather = BLUR_R > 0 ? boxBlur255(a255, mw, mh, BLUR_R) : a255;

    // 4) upload RGBA (RGB는 의미 없음, alpha만 사용)
    const img = mctx.createImageData(mw, mh);
    const d = img.data;
    for (let i = 0; i < mw * mh; i++) {
      const j = i * 4;
      d[j + 0] = 255;
      d[j + 1] = 255;
      d[j + 2] = 255;
      d[j + 3] = aFeather[i];
    }

    mctx.putImageData(img, 0, 0);
    maskTex.needsUpdate = true;
  }

  function debugDrawHairMaskTo(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.globalAlpha = 1;
    ctx.drawImage(maskCanvas, 0, 0, w, h);
    ctx.restore();
  }

  function drawMaskTo(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.globalAlpha = 1;
    ctx.drawImage(maskCanvas, 0, 0, w, h); // ✅ 알파 그대로 전달
    ctx.restore();
  }

  function dispose() {
    maskTex.dispose();
    renderer.dispose();
  }

  return { resize, updateHairMask, debugDrawHairMaskTo, drawMaskTo, dispose };
}