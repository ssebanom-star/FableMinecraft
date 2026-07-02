/* world.js - 청크/지형 생성/조명/메시 (전역 WorldMod) */
(function () {
  'use strict';
  const { fbm2, noise3, hash2 } = U;

  const CH = 16, CHH = 64, SEA = 28;

  const BIOMES = {
    plains: { surf: 'GRASS', fill: 'DIRT', tree: 0.003, plant: 0.06,
              disp: '평야' },
    forest: { surf: 'GRASS', fill: 'DIRT', tree: 0.05, plant: 0.05,
              disp: '숲' },
    birch: { surf: 'GRASS', fill: 'DIRT', tree: 0.045, plant: 0.04,
             disp: '자작나무 숲' },
    desert: { surf: 'SAND', fill: 'SAND', tree: 0, plant: 0.01,
              disp: '사막' },
    snowb: { surf: 'SNOW', fill: 'DIRT', tree: 0.014, plant: 0.005,
             disp: '설원' },
    mountains: { surf: 'STONE', fill: 'STONE', tree: 0.004, plant: 0.01,
                 disp: '산악' },
    swamp: { surf: 'MUD', fill: 'DIRT', tree: 0.025, plant: 0.09,
             disp: '늪지' },
    beach: { surf: 'SAND', fill: 'SAND', tree: 0, plant: 0.003,
             disp: '해변' },
    lake: { surf: 'SAND', fill: 'DIRT', tree: 0, plant: 0, disp: '호수' },
  };

  function idx(x, y, z) { return (x * CHH + y) * CH + z; }

  class World {
    constructor(seed) {
      this.seed = seed | 0;
      this.chunks = new Map();          // "cx,cz" -> chunk
      this.modified = {};               // "x,y,z" -> id
      this.containers = {};             // "x,y,z" -> {type, ...}
      this.renderDistance = 2;
    }

    // ---------- 높이/바이옴 ----------
    heightAt(x, z) {
      const s = this.seed;
      const cont = fbm2(x, z, 110, s + 11, 4);
      const hills = fbm2(x, z, 36, s + 23, 3);
      const mount = fbm2(x, z, 170, s + 47, 3);
      let h = 16 + cont * 20 + hills * 6;
      const m = Math.max(0, Math.min(1, (mount - 0.60) / 0.40));
      h += m * m * 26;
      return { h: Math.max(4, Math.min(CHH - 8, h)), m };
    }
    biomeAt(x, z) {
      const s = this.seed;
      const { h, m } = this.heightAt(x, z);
      const temp = fbm2(x, z, 130, s + 101, 3);
      const moist = fbm2(x, z, 105, s + 202, 3);
      if (h < SEA - 1) return 'lake';
      if (h <= SEA + 1) return 'beach';
      if (m > 0.35 || h > 44) return 'mountains';
      if (temp > 0.62 && moist < 0.45) return 'desert';
      if (temp < 0.34) return 'snowb';
      if (moist > 0.68 && h < 34) return 'swamp';
      if (moist > 0.52) return temp > 0.55 ? 'birch' : 'forest';
      return 'plains';
    }

    // ---------- 청크 생성 ----------
    generateChunk(cx, cz) {
      const s = this.seed, ID = BLK.ID;
      const bx = new Uint8Array(CH * CHH * CH);
      const heights = new Int16Array(CH * CH);
      const biomes = [];
      const x0 = cx * CH, z0 = cz * CH;

      for (let lx = 0; lx < CH; lx++) {
        for (let lz = 0; lz < CH; lz++) {
          const wx = x0 + lx, wz = z0 + lz;
          const { h } = this.heightAt(wx, wz);
          const hi = h | 0;
          heights[lx * CH + lz] = hi;
          const biome = this.biomeAt(wx, wz);
          biomes[lx * CH + lz] = biome;
          const bio = BIOMES[biome];

          bx[idx(lx, 0, lz)] = ID.BEDROCK;
          for (let y = 1; y <= hi; y++) {
            let bid;
            if (y < hi - 3) bid = ID.STONE;
            else if (y < hi) bid = ID[bio.fill];
            else bid = ID[bio.surf];
            if (biome === 'mountains' && y === hi && hi > 48) bid = ID.SNOW;

            // 동굴
            if (y > 3 && y < hi - 1) {
              const c = noise3(wx, y, wz, 18, s + 501) * 0.65 +
                        noise3(wx, y, wz, 9, s + 601) * 0.35;
              if (c > 0.70) { bx[idx(lx, y, lz)] = ID.AIR; continue; }
              // 광물 (돌만 대체, 희귀한 것 먼저)
              if (bid === ID.STONE) {
                const r = noise3(wx, y, wz, 3, s + 701);
                if (y < 12 && r > 0.952) bid = ID.CRYSTAL_ORE;
                else if (y < 16 && r > 0.935) bid = ID.GOLD_ORE;
                else if (y < 26 && r > 0.917) bid = ID.IRON_ORE;
                else if (y < 46 && r > 0.895) bid = ID.COAL_ORE;
              }
            }
            bx[idx(lx, y, lz)] = bid;
          }
          // 물
          for (let y = hi + 1; y <= SEA; y++) {
            bx[idx(lx, y, lz)] = ID.WATER;
          }
          if (biome === 'snowb' && hi < SEA &&
              bx[idx(lx, SEA, lz)] === ID.WATER) {
            bx[idx(lx, SEA, lz)] = ID.ICE;
          }
        }
      }

      // 장식 (나무/식물)
      for (let lx = 0; lx < CH; lx++) {
        for (let lz = 0; lz < CH; lz++) {
          const wx = x0 + lx, wz = z0 + lz;
          const biome = biomes[lx * CH + lz], bio = BIOMES[biome];
          const h = heights[lx * CH + lz];
          if (h <= SEA - 1 || h + 7 >= CHH) continue;
          const surf = bx[idx(lx, h, lz)];
          if (surf !== ID.GRASS && surf !== ID.SAND && surf !== ID.SNOW &&
              surf !== ID.MUD && surf !== ID.STONE) continue;
          const r = hash2(wx, wz, s + 900);
          if (r < bio.tree && lx >= 2 && lx <= 13 && lz >= 2 && lz <= 13) {
            this._tree(bx, lx, h + 1, lz, biome, wx, wz);
            continue;
          }
          const r2 = hash2(wx, wz, s + 901);
          if (r2 < bio.plant) {
            bx[idx(lx, h + 1, lz)] = this._plant(biome, wx, wz);
          } else if (biome === 'desert' && r2 < bio.plant + 0.006) {
            const ch = 2 + (hash2(wx, wz, s + 902) * 2 | 0);
            for (let d = 0; d < ch && h + 1 + d < CHH; d++) {
              bx[idx(lx, h + 1 + d, lz)] = ID.CACTUS;
            }
          }
        }
      }

      const chunk = { cx, cz, bx, heights, biomes, dirty: true,
                      light: null, gpu: null };
      // 저장된 변경 블록 적용
      for (const key in this.modified) {
        const [mx, my, mz] = key.split(',').map(Number);
        if (mx >= x0 && mx < x0 + CH && mz >= z0 && mz < z0 + CH &&
            my >= 0 && my < CHH) {
          bx[idx(mx - x0, my, mz - z0)] = this.modified[key];
        }
      }
      this.chunks.set(cx + ',' + cz, chunk);
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nb = this.chunks.get((cx + dx) + ',' + (cz + dz));
        if (nb) nb.dirty = true;
      }
      return chunk;
    }

    _plant(biome, wx, wz) {
      const ID = BLK.ID, r = hash2(wx, wz, this.seed + 910);
      if (biome === 'desert') return ID.DEADBUSH;
      if (biome === 'swamp') return r < .4 ? ID.MUSHROOM : ID.TALLGRASS;
      if (r < .65) return ID.TALLGRASS;
      if (r < .82) return ID.FLOWER_Y;
      if (r < .95) return ID.FLOWER_R;
      return ID.MUSHROOM;
    }

    _tree(bx, lx, y, lz, biome, wx, wz) {
      const ID = BLK.ID;
      let log = ID.OAK_LOG, leaves = ID.OAK_LEAVES;
      if (biome === 'snowb' || biome === 'mountains') {
        log = ID.SPRUCE_LOG; leaves = ID.SPRUCE_LEAVES;
      } else if (biome === 'birch') {
        log = ID.BIRCH_LOG; leaves = ID.BIRCH_LEAVES;
      }
      const th = 4 + (hash2(wx, wz, this.seed + 920) * 2 | 0);
      const top = y + th;
      for (let dy = -2; dy < 2; dy++) {
        const rad = dy < 0 ? 2 : 1;
        for (let dx = -rad; dx <= rad; dx++) {
          for (let dz = -rad; dz <= rad; dz++) {
            if (Math.abs(dx) === rad && Math.abs(dz) === rad && dy >= 0)
              continue;
            const px = lx + dx, py = top + dy, pz = lz + dz;
            if (px >= 0 && px < CH && pz >= 0 && pz < CH &&
                py >= 0 && py < CHH && bx[idx(px, py, pz)] === ID.AIR) {
              bx[idx(px, py, pz)] = leaves;
            }
          }
        }
      }
      if (top + 1 < CHH) bx[idx(lx, top + 1, lz)] = leaves;
      for (let d = 0; d < th && y + d < CHH; d++) {
        bx[idx(lx, y + d, lz)] = log;
      }
    }

    // ---------- 블록 접근 ----------
    getBlock(x, y, z) {
      x = Math.floor(x); y = Math.floor(y); z = Math.floor(z);
      if (y < 0 || y >= CHH) return 0;
      const cx = Math.floor(x / CH), cz = Math.floor(z / CH);
      const c = this.chunks.get(cx + ',' + cz);
      if (!c) return 0;
      return c.bx[idx(x - cx * CH, y, z - cz * CH)];
    }
    isSolid(x, y, z) {
      const b = BLK.B[this.getBlock(x, y, z)];
      return b && b.solid;
    }
    setBlock(x, y, z, id, record) {
      x = Math.floor(x); y = Math.floor(y); z = Math.floor(z);
      if (y < 0 || y >= CHH) return false;
      const cx = Math.floor(x / CH), cz = Math.floor(z / CH);
      const c = this.chunks.get(cx + ',' + cz);
      if (record !== false) this.modified[x + ',' + y + ',' + z] = id;
      if (!c) return true;
      const lx = x - cx * CH, lz = z - cz * CH;
      c.bx[idx(lx, y, lz)] = id;
      c.dirty = true;
      if (lx === 0) this._dirty(cx - 1, cz);
      if (lx === CH - 1) this._dirty(cx + 1, cz);
      if (lz === 0) this._dirty(cx, cz - 1);
      if (lz === CH - 1) this._dirty(cx, cz + 1);
      return true;
    }
    _dirty(cx, cz) {
      const c = this.chunks.get(cx + ',' + cz);
      if (c) c.dirty = true;
    }

    surfaceHeight(x, z) {
      const cx = Math.floor(x / CH), cz = Math.floor(z / CH);
      const c = this.chunks.get(cx + ',' + cz);
      if (!c) return Math.floor(this.heightAt(x, z).h);
      const lx = Math.floor(x) - cx * CH, lz = Math.floor(z) - cz * CH;
      for (let y = CHH - 1; y > 0; y--) {
        const b = BLK.B[c.bx[idx(lx, y, lz)]];
        if (b.solid) return y;
      }
      return 0;
    }
    lightAt(x, y, z) {
      const cx = Math.floor(x / CH), cz = Math.floor(z / CH);
      const c = this.chunks.get(cx + ',' + cz);
      if (!c || !c.light) return 15;
      y = Math.floor(y);
      if (y < 0 || y >= CHH) return 15;
      return c.light[idx(Math.floor(x) - cx * CH, y, Math.floor(z) - cz * CH)];
    }

    // ---------- 스트리밍 ----------
    loadAround(px, pz, budget) {
      const pcx = Math.floor(px / CH), pcz = Math.floor(pz / CH);
      const rd = this.renderDistance;
      const need = [];
      for (let dx = -rd; dx <= rd; dx++) {
        for (let dz = -rd; dz <= rd; dz++) {
          if (!this.chunks.has((pcx + dx) + ',' + (pcz + dz))) {
            need.push([dx * dx + dz * dz, pcx + dx, pcz + dz]);
          }
        }
      }
      need.sort((a, b) => a[0] - b[0]);
      let made = 0;
      for (const [, cx, cz] of need) {
        if (made >= budget) break;
        this.generateChunk(cx, cz);
        made++;
      }
      return made;
    }
    unloadFar(px, pz, onUnload) {
      const pcx = Math.floor(px / CH), pcz = Math.floor(pz / CH);
      const lim = this.renderDistance + 1;
      for (const [key, c] of this.chunks) {
        if (Math.abs(c.cx - pcx) > lim || Math.abs(c.cz - pcz) > lim) {
          if (onUnload) onUnload(c);
          this.chunks.delete(key);
        }
      }
    }

    // ---------- 조명 ----------
    computeLight(c) {
      const light = new Uint8Array(CH * CHH * CH);
      const B = BLK.B;
      const queue = [];
      for (let lx = 0; lx < CH; lx++) {
        for (let lz = 0; lz < CH; lz++) {
          let sky = 15;
          for (let y = CHH - 1; y >= 0; y--) {
            const i = idx(lx, y, lz);
            light[i] = sky;
            const b = B[c.bx[i]];
            if (BLK.OPAQUE[c.bx[i]]) sky = 0;
            else if (b.liquid || b.name.endsWith('leaves')) {
              sky = Math.max(0, sky - 2);
            }
            if (b.light > 0) {
              if (b.light > light[i]) light[i] = b.light;
              queue.push([lx, y, lz, b.light]);
            }
          }
        }
      }
      // 블록빛 BFS (청크 내부)
      let head = 0;
      while (head < queue.length) {
        const [x, y, z, lv] = queue[head++];
        const nl = lv - 1;
        if (nl <= 0) continue;
        const dirs = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]];
        for (const [dx, dy, dz] of dirs) {
          const nx = x + dx, ny = y + dy, nz = z + dz;
          if (nx < 0 || nx >= CH || ny < 0 || ny >= CHH ||
              nz < 0 || nz >= CH) continue;
          const i = idx(nx, ny, nz);
          if (BLK.OPAQUE[c.bx[i]]) continue;
          if (light[i] >= nl) continue;
          light[i] = nl;
          queue.push([nx, ny, nz, nl]);
        }
      }
      c.light = light;
    }

    // ---------- 메시 생성 (보이는 면만) ----------
    buildMesh(c) {
      this.computeLight(c);
      const B = BLK.B, OP = BLK.OPAQUE, AL = BLK.ALPHA;
      const x0 = c.cx * CH, z0 = c.cz * CH;
      const solid = { pos: [], col: [], uv: [] };
      const alpha = { pos: [], col: [], uv: [] };
      const bx = c.bx, light = c.light;

      const FACES = [
        [0, 1, 0, [[0,1,0],[0,1,1],[1,1,1],[1,1,0]], 1.0],
        [0, -1, 0, [[0,0,0],[1,0,0],[1,0,1],[0,0,1]], .45],
        [1, 0, 0, [[1,0,0],[1,1,0],[1,1,1],[1,0,1]], .8],
        [-1, 0, 0, [[0,0,1],[0,1,1],[0,1,0],[0,0,0]], .8],
        [0, 0, 1, [[1,0,1],[1,1,1],[0,1,1],[0,0,1]], .65],
        [0, 0, -1, [[0,0,0],[0,1,0],[1,1,0],[1,0,0]], .65],
      ];
      const self = this;
      function nbAt(wx, wy, wz, lx, ly, lz) {
        if (lx >= 0 && lx < CH && ly >= 0 && ly < CHH &&
            lz >= 0 && lz < CH) return bx[idx(lx, ly, lz)];
        return self.getBlock(wx, wy, wz);
      }
      function faceLight(lx, ly, lz) {
        if (lx >= 0 && lx < CH && ly >= 0 && ly < CHH && lz >= 0 && lz < CH)
          return .16 + .84 * light[idx(lx, ly, lz)] / 15;
        return 1;
      }
      function quad(t, pts, r, g, b, a, uv4) {
        const order = [0, 1, 2, 0, 2, 3];
        for (const o of order) {
          t.pos.push(pts[o][0], pts[o][1], pts[o][2]);
          t.col.push(r, g, b, a);
          t.uv.push(uv4[o][0], uv4[o][1]);
        }
      }
      function faceUVs(tileIdx, dx, dy, dz, corners) {
        const [u0, v0, span] = TEX.uv(tileIdx);
        return corners.map(cn => {
          let u, w;
          if (dy !== 0) { u = cn[0]; w = cn[2]; }
          else if (dx !== 0) { u = cn[2]; w = cn[1]; }
          else { u = cn[0]; w = cn[1]; }
          return [u0 + u * span, v0 + w * span];
        });
      }

      for (let lx = 0; lx < CH; lx++) {
        for (let ly = 0; ly < CHH; ly++) {
          for (let lz = 0; lz < CH; lz++) {
            const id = bx[idx(lx, ly, lz)];
            if (id === 0) continue;
            const def = B[id];
            const wx = x0 + lx, wy = ly, wz = z0 + lz;

            if (def.cross) {
              const lv = faceLight(lx, ly, lz);
              const [u0, v0, span] = TEX.uv((TEX.MAP[id] || [0, 0, 0])[1]);
              const cuv = [[u0, v0], [u0, v0 + span],
                           [u0 + span, v0 + span], [u0 + span, v0]];
              quad(solid, [[wx+.15,wy,wz+.15],[wx+.15,wy+1,wz+.15],
                           [wx+.85,wy+1,wz+.85],[wx+.85,wy,wz+.85]],
                   lv, lv, lv, 1, cuv);
              quad(solid, [[wx+.85,wy,wz+.15],[wx+.85,wy+1,wz+.15],
                           [wx+.15,wy+1,wz+.85],[wx+.15,wy,wz+.85]],
                   lv, lv, lv, 1, cuv);
              continue;
            }

            const isAlpha = AL[id];
            for (const [dx, dy, dz, corners, shade] of FACES) {
              const nid = nbAt(wx+dx, wy+dy, wz+dz, lx+dx, ly+dy, lz+dz);
              if (OP[nid]) continue;
              if (isAlpha && def.liquid && B[nid].liquid) continue;
              if (isAlpha && nid === id) continue;
              const lv = faceLight(lx+dx, ly+dy, lz+dz);
              const tiles = TEX.MAP[id] || [0, 0, 0];
              const tileIdx = dy > 0 ? tiles[0] : dy < 0 ? tiles[2]
                : tiles[1];
              const s = shade * lv;
              const a = def.liquid ? .62 : 1;   // 유리/얼음은 타일 알파 사용
              const pts = corners.map(cn => {
                let vy = cn[1];
                if (def.liquid && vy === 1) vy = .85;
                return [wx + cn[0], wy + vy, wz + cn[2]];
              });
              quad(isAlpha ? alpha : solid, pts, s, s, s, a,
                   faceUVs(tileIdx, dx, dy, dz, corners));
            }
          }
        }
      }
      c.dirty = false;
      return {
        solid: solid.pos.length ? {
          pos: new Float32Array(solid.pos),
          col: new Float32Array(solid.col),
          uv: new Float32Array(solid.uv) } : null,
        alpha: alpha.pos.length ? {
          pos: new Float32Array(alpha.pos),
          col: new Float32Array(alpha.col),
          uv: new Float32Array(alpha.uv) } : null,
      };
    }

    findSpawn() {
      for (let r = 0; r < 64; r += 8) {
        for (const [x, z] of [[r, 0], [-r, 0], [0, r], [0, -r], [r, r]]) {
          const { h } = this.heightAt(x, z);
          if (h > SEA + 1) return [x + .5, Math.floor(h) + 2, z + .5];
        }
      }
      return [.5, SEA + 10, .5];
    }

    getContainer(x, y, z, kind) {
      const key = Math.floor(x) + ',' + Math.floor(y) + ',' + Math.floor(z);
      if (!this.containers[key]) {
        if (kind === 'chest') {
          this.containers[key] = { type: 'chest', slots: Array(27).fill(null) };
        } else {
          // queue: 제련 대기 재료 id 목록, out: {id: 개수}, burn: 남은 연소(초)
          this.containers[key] = { type: 'furnace', burn: 0, progress: 0,
                                   queue: [], out: {} };
        }
      }
      return this.containers[key];
    }
    removeContainer(x, y, z) {
      delete this.containers[
        Math.floor(x) + ',' + Math.floor(y) + ',' + Math.floor(z)];
    }
  }

  window.WorldMod = { World, CH, CHH, SEA, BIOMES };
})();
