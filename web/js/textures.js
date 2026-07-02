/* textures.js - 절차적 텍스처 아틀라스 (Canvas 생성, 전역 TEX) */
(function () {
  'use strict';

  const TILE = 16, GRID = 16, PX = TILE * GRID;
  const MAP = {};            // block_id -> [top, side, bottom]
  const alloc = {};          // key -> index
  let next = 0;
  let ctx = null, img = null;

  function keyNum(key) {
    let h = 0;
    for (const ch of key) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0;
    return h;
  }
  function rnd(k, x, y) { return U.hash2(x | 0, y | 0, k); }

  function c255(c) {
    return [Math.round(c[0] * 255), Math.round(c[1] * 255),
            Math.round(c[2] * 255)];
  }
  function put(ox, oy, x, y, r, g, b, a) {
    const i = ((oy + y) * PX + ox + x) * 4;
    img.data[i] = Math.max(0, Math.min(255, r | 0));
    img.data[i + 1] = Math.max(0, Math.min(255, g | 0));
    img.data[i + 2] = Math.max(0, Math.min(255, b | 0));
    img.data[i + 3] = a === undefined ? 255 : a;
  }

  function tile(key, fn) {
    if (key in alloc) return alloc[key];
    const idx = next++;
    alloc[key] = idx;
    const ox = (idx % GRID) * TILE, oy = ((idx / GRID) | 0) * TILE;
    const k = keyNum(key);
    fn((x, y, c, f, a) =>
      put(ox, oy, x, y, c[0] * f, c[1] * f, c[2] * f, a), k);
    return idx;
  }

  // ---------------- 패턴 ----------------
  const speckle = (c, v) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, c, 1 + (rnd(k, x, y) - .5) * 2 * v);
  };
  const grassTop = (g) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, g, .88 + rnd(k, x, y) * .28);
    for (let i = 0; i < 10; i++)
      P((rnd(k + 1, i, 0) * TILE) | 0, (rnd(k + 2, i, 0) * TILE) | 0, g, 1.35);
  };
  const grassSide = (d, g) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, d, .9 + rnd(k, x, y) * .2);
    for (let x = 0; x < TILE; x++) {
      const depth = 3 + (rnd(k + 3, x, 0) * 3) | 0;
      for (let y = 0; y < depth; y++)
        P(x, y, g, .9 + rnd(k + 4, x, y) * .3);
    }
  };
  const bark = (c) => (P, k) => {
    for (let x = 0; x < TILE; x++) {
      const s = .75 + rnd(k + 5, x, 0) * .45;
      for (let y = 0; y < TILE; y++)
        P(x, y, c, s * (.9 + rnd(k, x, y) * .2));
    }
  };
  const rings = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5)) | 0;
      P(x, y, c, (d % 2 ? .8 : 1.15) * (.92 + rnd(k, x, y) * .16));
    }
  };
  const leaves = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      const r = rnd(k, x, y);
      if (r < .10) P(x, y, c, 0, 0);
      else if (r < .30) P(x, y, c, .65);
      else P(x, y, c, .85 + r * .45);
    }
  };
  const planks = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) {
      const b = (y / 4) | 0;
      for (let x = 0; x < TILE; x++) {
        let f = .9 + rnd(k, x + b * 31, y) * .22;
        if (y % 4 === 3) f *= .6;
        if ((x + b * 5) % 8 === 0) f *= .8;
        P(x, y, c, f);
      }
    }
  };
  const cobble = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      const cell = .8 + rnd(k + 6, (x / 5) | 0, (y / 5) | 0) * .4;
      const edge = (x % 5 === 0 || y % 5 === 0) ? .55 : 1;
      P(x, y, c, cell * edge * (.92 + rnd(k, x, y) * .16));
    }
  };
  const stoneBricks = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      let f = .85 + rnd(k + 7, (x / 8) | 0, (y / 8) | 0) * .3;
      if (x % 8 === 0 || y % 8 === 0) f = .5;
      P(x, y, c, f * (.94 + rnd(k, x, y) * .12));
    }
  };
  const ore = (stone, oc, glow) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, stone, .9 + rnd(k, x, y) * .2);
    for (let i = 0; i < 5; i++) {
      const bx = 1 + (rnd(k + 8, i, 0) * 12) | 0;
      const by = 1 + (rnd(k + 9, i, 0) * 12) | 0;
      const sz = 2 + (rnd(k + 10, i, 0) * 2) | 0;
      for (let dy = 0; dy < sz; dy++) for (let dx = 0; dx < sz; dx++)
        if (rnd(k + 11, bx + dx, by + dy) < .8)
          P(Math.min(15, bx + dx), Math.min(15, by + dy), oc, 1);
      P(bx, by, oc, glow ? 1.5 : 1.3);
    }
  };
  const glassP = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      if (x === 0 || x === 15 || y === 0 || y === 15) P(x, y, c, 1.1, 220);
      else if ((x + y) % 7 === 0 && x < 8) P(x, y, c, 1.3, 150);
      else P(x, y, c, 1, 70);
    }
  };
  const waterP = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, c, (y % 4 === 0 ? 1.15 : 1) *
        (.85 + rnd(k, x, (y / 2) | 0) * .3));
  };
  const glow = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      const r = rnd(k, x, y);
      P(x, y, c, r > .72 ? 1.25 : .85 + r * .4);
    }
  };
  const cactusP = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, c, (x % 4 === 0 ? .75 : 1) * (.9 + rnd(k, x, y) * .2));
    for (let i = 0; i < 6; i++)
      P((rnd(k + 12, i, 0) * TILE) | 0, (rnd(k + 13, i, 0) * TILE) | 0,
        [235, 240, 210], 1);
  };
  const furnaceSide = (c) => (P, k) => {
    cobble(c)(P, k);
    for (let y = 9; y < 14; y++) for (let x = 4; x < 12; x++)
      P(x, y, [25, 22, 20], 1);
    for (let x = 5; x < 11; x += 2) {
      P(x, 12, [250, 140, 30], 1);
      P(x + 1, 11, [255, 200, 60], 1);
    }
  };
  const chestSide = (c) => (P, k) => {
    planks(c)(P, k);
    for (let i = 0; i < TILE; i++) {
      P(i, 0, c, .5); P(i, 15, c, .5); P(0, i, c, .5); P(15, i, c, .5);
    }
    for (let y = 6; y < 10; y++) for (let x = 6; x < 10; x++)
      P(x, y, [200, 200, 205], 1);
    P(7, 8, [90, 90, 95], 1); P(8, 8, [90, 90, 95], 1);
  };
  const wbTop = (c) => (P, k) => {
    planks(c)(P, k);
    for (let i = 0; i < TILE; i++) {
      P(i, 5, c, .5); P(i, 10, c, .5); P(5, i, c, .5); P(10, i, c, .5);
    }
  };
  const torchP = () => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, [0, 0, 0], 0, 0);
    for (let y = 6; y < 14; y++) {
      P(7, y, [110, 85, 50], 1); P(8, y, [95, 70, 40], 1);
    }
    for (let y = 3; y < 6; y++) for (let x = 6; x < 10; x++)
      P(x, y, [255, 210, 90], 1);
    P(7, 2, [255, 245, 200], 1); P(8, 2, [255, 245, 200], 1);
    P(7, 4, [250, 150, 40], 1);
  };
  const plant = (kind, c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, [0, 0, 0], 0, 0);
    if (kind === 'grass') {
      for (let i = 0; i < 6; i++) {
        const x = 2 + (rnd(k, i, 0) * 12) | 0;
        const h = 5 + (rnd(k + 14, i, 0) * 9) | 0;
        for (let y = TILE - h; y < TILE; y++) {
          const xx = x + (y < TILE - h + 2 && i % 2 ? 1 : 0);
          if (xx >= 0 && xx < TILE)
            P(xx, y, c, .8 + rnd(k, xx, y) * .5);
        }
      }
    } else if (kind === 'flower') {
      for (let y = 8; y < TILE; y++) P(7, y, [60, 120, 45], 1);
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++)
        if (Math.abs(dx) + Math.abs(dy) <= 2) P(7 + dx, 6 + dy, c, 1);
      P(7, 6, c, 1.5);
    } else if (kind === 'mushroom') {
      for (let y = 9; y < TILE; y++) {
        P(7, y, [225, 215, 190], 1); P(8, y, [205, 195, 170], 1);
      }
      for (let x = 4; x < 12; x++) for (let y = 5; y < 9; y++)
        if (4 + ((Math.abs(x - 7) / 2) | 0) <= y)
          P(x, y, c, .9 + rnd(k, x, y) * .3);
    } else {   // bush
      for (let i = 0; i < 5; i++) {
        const x = 3 + (rnd(k, i, 0) * 10) | 0;
        for (let y = 6 + i; y < TILE; y++) {
          const xx = x + (y % 3) - 1;
          if (xx >= 0 && xx < TILE)
            P(xx, y, c, .75 + rnd(k, xx, y) * .4);
        }
      }
    }
  };
  const danger = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      if ((x + y) % 8 < 2) P(x, y, [240, 205, 60], 1);
      else P(x, y, c, .9 + rnd(k, x, y) * .2);
    }
  };
  const bedrockP = () => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
      const v = 35 + rnd(k, x, y) * 65;
      P(x, y, [v, v, v + 4], 1);
    }
  };
  const sandstoneP = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, c, (((y / 4) | 0) % 2 ? .92 : 1.06) *
        (.94 + rnd(k, x, y) * .12));
  };
  const iceP = (c) => (P, k) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, c, .95 + rnd(k, x, y) * .15, 235);
    for (let i = 0; i < 8; i++)
      P((rnd(k + 15, i, 0) * TILE) | 0, (rnd(k + 16, i, 0) * TILE) | 0,
        [240, 250, 255], 1, 235);
  };
  const white = () => (P) => {
    for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++)
      P(x, y, [255, 255, 255], 1);
  };

  // ---------------- 블록 -> 타일 ----------------
  function assign(b) {
    const n = b.name;
    const top = c255(b.top), side = c255(b.col), bot = c255(b.bottom);
    const STONE = [133, 133, 138];
    const spk = (key, c, v) => tile(key, speckle(c, v || .1));

    if (n === 'grass') {
      return [tile('grass_top', grassTop(top)),
              tile('grass_side', grassSide(side, top)),
              spk('dirt', c255(BLK.B[BLK.ID.DIRT].col))];
    }
    if (n.endsWith('_log')) {
      const t = tile(n + 't', rings(top)), s = tile(n + 's', bark(side));
      return [t, s, t];
    }
    if (n.endsWith('leaves')) { const t = tile(n, leaves(side)); return [t, t, t]; }
    if (n === 'planks') { const t = tile(n, planks(side)); return [t, t, t]; }
    if (n === 'cobble') { const t = tile(n, cobble(side)); return [t, t, t]; }
    if (n === 'stone_bricks') {
      const t = tile(n, stoneBricks(side)); return [t, t, t];
    }
    if (n.endsWith('_ore')) {
      const t = tile(n, ore(STONE, side, b.light > 0)); return [t, t, t];
    }
    if (n === 'glass') { const t = tile(n, glassP(side)); return [t, t, t]; }
    if (n === 'ice') { const t = tile(n, iceP(side)); return [t, t, t]; }
    if (n === 'water') { const t = tile(n, waterP(side)); return [t, t, t]; }
    if (n === 'glowstone' || n === 'slime') {
      const t = tile(n, glow(side)); return [t, t, t];
    }
    if (n === 'cactus') {
      const t = tile(n, cactusP(side));
      return [spk(n + 't', top, .08), t, t];
    }
    if (n === 'furnace') {
      const t = spk('furn_top', top, .08);
      return [t, tile('furn_side', furnaceSide(side)), t];
    }
    if (n === 'chest') {
      const t = tile('chest_top', planks(top));
      return [t, tile('chest_side', chestSide(side)), t];
    }
    if (n === 'workbench') {
      return [tile('wb_top', wbTop(top)),
              tile('wb_side', chestSide(side)),
              tile('planks', planks(side))];
    }
    if (n === 'torch') { const t = tile(n, torchP()); return [t, t, t]; }
    if (n === 'tallgrass') {
      const t = tile(n, plant('grass', side)); return [t, t, t];
    }
    if (n === 'flower_r' || n === 'flower_y') {
      const t = tile(n, plant('flower', side)); return [t, t, t];
    }
    if (n === 'mushroom') {
      const t = tile(n, plant('mushroom', side)); return [t, t, t];
    }
    if (n === 'deadbush') {
      const t = tile(n, plant('bush', side)); return [t, t, t];
    }
    if (n === 'boom') {
      const t = spk('boom_top', top, .15);
      return [t, tile('boom_side', danger(side)), t];
    }
    if (n === 'bedrock') { const t = tile(n, bedrockP()); return [t, t, t]; }
    if (n === 'sandstone') {
      const t = tile(n, sandstoneP(side)); return [t, t, t];
    }
    if (n === 'gravel') {
      const t = tile(n, speckle(side, .28)); return [t, t, t];
    }
    return [spk(n + 't', top, .09), spk(n + 's', side, .09),
            spk(n + 'b', bot, .09)];
  }

  function buildCanvas() {
    const canvas = document.createElement('canvas');
    canvas.width = PX; canvas.height = PX;
    ctx = canvas.getContext('2d');
    img = ctx.createImageData(PX, PX);
    next = 0;
    tile('white', white());          // 0번: 흰색 (엔티티 큐브용)
    for (const b of BLK.B) {
      if (b.name === 'air') continue;
      MAP[b.id] = assign(b);
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  // 타일 UV (블리딩 방지 인셋, v 는 GL 규약: 0=아래)
  function uv(idx) {
    const col = idx % GRID, row = (idx / GRID) | 0;
    const inset = 0.35;
    return [
      (col * TILE + inset) / PX,
      ((GRID - 1 - row) * TILE + inset) / PX,
      (TILE - 2 * inset) / PX,
    ];
  }

  window.TEX = { MAP, buildCanvas, uv, GRID, TILE };
})();
