/* util.js - 노이즈 / 행렬 / 레이캐스트 (전역 U) */
(function () {
  'use strict';

  // ---------- 해시 기반 난수 ----------
  function hash2(ix, iz, seed) {
    let h = (Math.imul(ix, 374761393) + Math.imul(iz, 668265263) +
             Math.imul(seed, 144665)) | 0;
    h ^= h >>> 13;
    h = Math.imul(h, 1274126177);
    h ^= h >>> 16;
    return (h >>> 8) / 16777216;
  }
  function hash3(ix, iy, iz, seed) {
    let h = (Math.imul(ix, 374761393) + Math.imul(iy, 1103515245) +
             Math.imul(iz, 668265263) + Math.imul(seed, 144665)) | 0;
    h ^= h >>> 13;
    h = Math.imul(h, 1274126177);
    h ^= h >>> 16;
    return (h >>> 8) / 16777216;
  }
  function smooth(t) { return t * t * (3 - 2 * t); }

  // ---------- 2D value noise + fBm ----------
  function noise2(x, z, scale, seed) {
    const gx = x / scale, gz = z / scale;
    const x0 = Math.floor(gx), z0 = Math.floor(gz);
    const tx = smooth(gx - x0), tz = smooth(gz - z0);
    const a = hash2(x0, z0, seed), b = hash2(x0 + 1, z0, seed);
    const c = hash2(x0, z0 + 1, seed), d = hash2(x0 + 1, z0 + 1, seed);
    return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * tz;
  }
  function fbm2(x, z, scale, seed, oct) {
    let total = 0, amp = 1, freq = 1, max = 0;
    for (let i = 0; i < oct; i++) {
      total += noise2(x, z, scale / freq, seed + i * 1013) * amp;
      max += amp; amp *= 0.5; freq *= 2;
    }
    return total / max;
  }

  // ---------- 3D value noise ----------
  function noise3(x, y, z, scale, seed) {
    const gx = x / scale, gy = y / scale, gz = z / scale;
    const x0 = Math.floor(gx), y0 = Math.floor(gy), z0 = Math.floor(gz);
    const tx = smooth(gx - x0), ty = smooth(gy - y0), tz = smooth(gz - z0);
    const c000 = hash3(x0, y0, z0, seed), c100 = hash3(x0 + 1, y0, z0, seed);
    const c010 = hash3(x0, y0 + 1, z0, seed),
          c110 = hash3(x0 + 1, y0 + 1, z0, seed);
    const c001 = hash3(x0, y0, z0 + 1, seed),
          c101 = hash3(x0 + 1, y0, z0 + 1, seed);
    const c011 = hash3(x0, y0 + 1, z0 + 1, seed),
          c111 = hash3(x0 + 1, y0 + 1, z0 + 1, seed);
    const a = c000 + (c100 - c000) * tx, b = c010 + (c110 - c010) * tx;
    const c = c001 + (c101 - c001) * tx, d = c011 + (c111 - c011) * tx;
    const e = a + (b - a) * ty, f = c + (d - c) * ty;
    return e + (f - e) * tz;
  }

  // ---------- mat4 (column-major) ----------
  function mat4Identity() {
    return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
  }
  function mat4Perspective(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
    const m = new Float32Array(16);
    m[0] = f / aspect; m[5] = f;
    m[10] = (far + near) * nf; m[11] = -1;
    m[14] = 2 * far * near * nf;
    return m;
  }
  function mat4Multiply(a, b) {
    const o = new Float32Array(16);
    for (let c = 0; c < 4; c++) {
      for (let r = 0; r < 4; r++) {
        o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] +
                       a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      }
    }
    return o;
  }
  // 시점 행렬: pitch/yaw(도) + 위치
  function mat4View(pos, yawDeg, pitchDeg) {
    const yaw = yawDeg * Math.PI / 180, pitch = pitchDeg * Math.PI / 180;
    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    // 카메라 기저 벡터 (yaw: +z 가 정면 기준, python 버전과 동일 규약)
    const fx = sy * cp, fy = -sp, fz = cy * cp;      // forward
    const rx = cy, ry = 0, rz = -sy;                 // right
    const ux = fy * rz - fz * ry,                    // up = forward x right
          uy = fz * rx - fx * rz,
          uz = fx * ry - fy * rx;
    const m = new Float32Array(16);
    m[0] = rx; m[4] = ry; m[8] = rz;
    m[1] = ux; m[5] = uy; m[9] = uz;
    m[2] = -fx; m[6] = -fy; m[10] = -fz;
    m[12] = -(rx * pos[0] + ry * pos[1] + rz * pos[2]);
    m[13] = -(ux * pos[0] + uy * pos[1] + uz * pos[2]);
    m[14] = fx * pos[0] + fy * pos[1] + fz * pos[2];
    m[15] = 1;
    return m;
  }
  function mat4Model(px, py, pz, sx, sy, sz, yawDeg) {
    const a = (yawDeg || 0) * Math.PI / 180;
    const c = Math.cos(a), s = Math.sin(a);
    return new Float32Array([
      c * sx, 0, -s * sx, 0,
      0, sy, 0, 0,
      s * sz, 0, c * sz, 0,
      px, py, pz, 1]);
  }

  // ---------- 복셀 레이캐스트 (DDA) ----------
  function raycast(ox, oy, oz, dx, dy, dz, maxDist, isHit) {
    const len = Math.hypot(dx, dy, dz);
    if (len < 1e-9) return null;
    dx /= len; dy /= len; dz /= len;
    let ix = Math.floor(ox), iy = Math.floor(oy), iz = Math.floor(oz);
    const stepX = dx > 0 ? 1 : -1, stepY = dy > 0 ? 1 : -1,
          stepZ = dz > 0 ? 1 : -1;
    const tMax = (p, ip, d, st) => Math.abs(d) < 1e-9 ? Infinity
      : (st > 0 ? (ip + 1 - p) / d : (ip - p) / d);
    let tmx = tMax(ox, ix, dx, stepX), tmy = tMax(oy, iy, dy, stepY),
        tmz = tMax(oz, iz, dz, stepZ);
    const tdx = Math.abs(1 / dx), tdy = Math.abs(1 / dy),
          tdz = Math.abs(1 / dz);
    let prev = [ix, iy, iz], t = 0;
    if (isHit(ix, iy, iz)) return { hit: [ix, iy, iz], prev: prev };
    while (t <= maxDist) {
      prev = [ix, iy, iz];
      if (tmx < tmy && tmx < tmz) { ix += stepX; t = tmx; tmx += tdx; }
      else if (tmy < tmz) { iy += stepY; t = tmy; tmy += tdy; }
      else { iz += stepZ; t = tmz; tmz += tdz; }
      if (t > maxDist) break;
      if (isHit(ix, iy, iz)) return { hit: [ix, iy, iz], prev: prev };
    }
    return null;
  }

  const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v;
  const distSq = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 +
                           (a[2] - b[2]) ** 2;

  window.U = { hash2, hash3, noise2, fbm2, noise3,
               mat4Identity, mat4Perspective, mat4Multiply, mat4View,
               mat4Model, raycast, clamp, distSq };
})();
