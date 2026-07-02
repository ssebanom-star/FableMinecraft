/* main.js - 게임 루프 / 입력 / 저장 (진입점) */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const SAVE_KEY = 'blockworld_web_save';
  const DAY_LENGTH = 300;   // 하루 길이(초)

  // =================================================================
  // 게임 객체
  // =================================================================
  class Game {
    constructor(renderer, seed, mode, saveData) {
      this.renderer = renderer;
      this.world = new WorldMod.World(seed);
      this.world.renderDistance = IS_TOUCH ? 2 : 3;
      this.drops = new EntMod.Drops(this.world);
      this.mobs = new EntMod.Mobs(this.world);
      this.projectiles = new EntMod.Projectiles();
      this.time = 0.05;         // 0.0=06:00, 0.5=18:00
      this.day = 1;
      this.autosave = 60;

      if (saveData) {
        this.world.modified = saveData.modified || {};
        this.world.containers = saveData.containers || {};
        this.time = saveData.time || 0.05;
        this.day = saveData.day || 1;
      }

      const spawn = this.world.findSpawn();
      this.player = new PlayerMod.Player(this, spawn, mode);

      if (saveData) {
        const p = this.player;
        p.pos = saveData.pos || spawn;
        p.spawn = saveData.spawn || spawn.slice();
        p.yaw = saveData.yaw || 0;
        p.pitch = saveData.pitch || 0;
        p.hp = saveData.hp !== undefined ? saveData.hp : 20;
        p.hunger = saveData.hunger !== undefined ? saveData.hunger : 20;
        p.stamina = saveData.stamina !== undefined ? saveData.stamina : 100;
        p.oxygen = saveData.oxygen !== undefined ? saveData.oxygen : 100;
        p.slots = saveData.slots || p.slots;
        p.sel = saveData.sel || 0;
        p.mode = saveData.mode || 'survival';
      }

      // 초기 청크 동기 로드
      this.world.loadAround(this.player.pos[0], this.player.pos[2], 999);
      this.rebuildDirty(999);

      // 스폰이 지형 속이면 위로
      const h = this.world.surfaceHeight(this.player.pos[0],
                                         this.player.pos[2]);
      if (this.player.pos[1] < h + 1) this.player.pos[1] = h + 1.5;

      this.ui = new UIManager(this);
      this.ui.setCreativeButtons(this.player.mode === 'creative');
    }

    isDay() { return this.time < 0.5; }
    brightness() {
      const t = this.time;
      if (t < 0.45) return 1;
      if (t < 0.55) return 1 - (t - 0.45) / 0.10 * 0.75;
      if (t < 0.95) return 0.25;
      return 0.25 + (t - 0.95) / 0.05 * 0.75;
    }
    skyColor() {
      const b = this.brightness();
      const t = Math.max(0, Math.min(1, (b - 0.25) / 0.75));
      const day = [0.45, 0.70, 0.95], night = [0.02, 0.03, 0.08];
      return [night[0] + (day[0] - night[0]) * t,
              night[1] + (day[1] - night[1]) * t,
              night[2] + (day[2] - night[2]) * t];
    }
    clockString() {
      const hours = (this.time * 24 + 6) % 24;
      const h = hours | 0, m = ((hours - h) * 60) | 0;
      return this.day + '일차 ' + String(h).padStart(2, '0') + ':' +
             String(m).padStart(2, '0');
    }

    nearBlock(id, r) {
      const [px, py, pz] = this.player.pos;
      for (let x = -r; x <= r; x++) {
        for (let y = -r; y <= r; y++) {
          for (let z = -r; z <= r; z++) {
            if (this.world.getBlock(px + x, py + y, pz + z) === id) {
              return true;
            }
          }
        }
      }
      return false;
    }

    rebuildDirty(budget) {
      const pcx = Math.floor(this.player.pos[0] / 16);
      const pcz = Math.floor(this.player.pos[2] / 16);
      const dirty = [];
      for (const c of this.world.chunks.values()) {
        if (c.dirty) {
          dirty.push([(c.cx - pcx) ** 2 + (c.cz - pcz) ** 2, c]);
        }
      }
      dirty.sort((a, b) => a[0] - b[0]);
      let done = 0;
      for (const [, c] of dirty) {
        if (done >= budget) break;
        const mesh = this.world.buildMesh(c);
        this.renderer.uploadChunk(c, mesh);
        done++;
      }
      return done;
    }

    update(dt) {
      // 시간
      this.time += dt / DAY_LENGTH;
      if (this.time >= 1) { this.time -= 1; this.day++; }

      if (!this.player.dead && !this.ui.isOpen()) this.player.update(dt);
      else if (!this.player.dead) {
        // 패널 열림: 물리만 유지
        this.player.input.mx = this.player.input.mz = 0;
        this.player.input.breaking = false;
        this.player.update(dt);
      }

      const [px, , pz] = this.player.pos;
      this.world.loadAround(px, pz, 1);
      this.rebuildDirty(2);
      this._unloadTimer = (this._unloadTimer || 0) - dt;
      if (this._unloadTimer <= 0) {
        this._unloadTimer = 3;
        this.world.unloadFar(px, pz, (c) => this.renderer.deleteChunk(c));
      }

      this.drops.update(dt, this.player);
      this.mobs.update(this, dt);
      this.projectiles.update(this, dt);

      // 화로
      for (const key in this.world.containers) {
        const st = this.world.containers[key];
        if (st.type !== 'furnace') continue;
        if (st.queue.length && st.burn > 0) {
          st.burn = Math.max(0, st.burn - dt);
          st.progress += dt;
          if (st.progress >= SMELT_TIME) {
            st.progress = 0;
            const out = st.queue.shift();
            st.out[out] = (st.out[out] || 0) + 1;
          }
        } else {
          st.progress = 0;
          if (st.burn > 0) st.burn = Math.max(0, st.burn - dt * 0.2);
        }
      }

      // 자동 저장
      this.autosave -= dt;
      if (this.autosave <= 0) { this.autosave = 60; this.save(); }
    }

    useAction() {
      if (this.player.dead || this.ui.isOpen()) return;
      const res = this.player.use();
      if (res === 'workbench') {
        this.ui.open('invoverlay');
        this.ui._tab('craft');
      } else if (res && res.startsWith('furnace:')) {
        const [x, y, z] = res.slice(8).split(',').map(Number);
        this.ui.openFurnace(this.world.getContainer(x, y, z, 'furnace'));
      } else if (res && res.startsWith('chest:')) {
        const [x, y, z] = res.slice(6).split(',').map(Number);
        this.ui.openChest(this.world.getContainer(x, y, z, 'chest'));
      }
    }

    explode(pos, radius, maxDmg) {
      const [ex, ey, ez] = pos;
      const r = Math.ceil(radius);
      for (let dx = -r; dx <= r; dx++) {
        for (let dy = -r; dy <= r; dy++) {
          for (let dz = -r; dz <= r; dz++) {
            if (dx * dx + dy * dy + dz * dz > radius * radius) continue;
            const bx = Math.floor(ex + dx), by = Math.floor(ey + dy),
                  bz = Math.floor(ez + dz);
            const id = this.world.getBlock(bx, by, bz);
            if (!id) continue;
            const def = BLK.B[id];
            if (def.hard < 0) continue;
            this.world.setBlock(bx, by, bz, 0);
            if (id === BLK.ID.BOOM) {
              this.explode([bx + .5, by + .5, bz + .5], radius * .8, maxDmg);
              continue;
            }
            if (Math.random() < 0.3) {
              for (const [iid, cnt, prob] of def.drops) {
                if (Math.random() < prob) {
                  this.drops.spawn(iid, cnt, [bx + .5, by + .5, bz + .5]);
                }
              }
            }
          }
        }
      }
      // 범위 피해
      const hurt = (targetPos, applyFn, body) => {
        const d2 = U.distSq(pos, targetPos);
        const rr = radius * 1.5;
        if (d2 > rr * rr) return;
        const fall = Math.max(0, 1 - Math.sqrt(d2) / rr);
        const dmg = Math.floor(maxDmg * fall);
        if (dmg > 0) applyFn(dmg);
        if (body) {
          const dx = targetPos[0] - pos[0], dz = targetPos[2] - pos[2];
          const d = Math.hypot(dx, dz) || 1;
          body.vel[0] += dx / d * 8 * fall;
          body.vel[1] += 5 * fall;
          body.vel[2] += dz / d * 8 * fall;
        }
      };
      hurt(this.player.pos, (d) => this.damagePlayer(d), this.player.body);
      for (const m of this.mobs.list.slice()) {
        hurt(m.pos, (d) => m.hurt(d, this), m.body);
      }
    }

    damagePlayer(n, srcPos) {
      const p = this.player;
      if (p.mode === 'creative') return;
      p.damage(Math.max(1, n));
      if (srcPos) {
        const dx = p.pos[0] - srcPos[0], dz = p.pos[2] - srcPos[2];
        const d = Math.hypot(dx, dz) || 1;
        p.body.vel[0] += dx / d * 5;
        p.body.vel[1] += 3;
        p.body.vel[2] += dz / d * 5;
      }
    }

    onPlayerDeath() { this.ui.showDeath(); }

    save() {
      const p = this.player;
      try {
        localStorage.setItem(SAVE_KEY, JSON.stringify({
          seed: this.world.seed, time: this.time, day: this.day,
          pos: p.pos, spawn: p.spawn, yaw: p.yaw, pitch: p.pitch,
          hp: p.hp, hunger: p.hunger, stamina: p.stamina, oxygen: p.oxygen,
          slots: p.slots, sel: p.sel, mode: p.mode,
          modified: this.world.modified,
          containers: this.world.containers,
        }));
      } catch (e) { /* 저장 공간 부족 등 */ }
    }
  }

  // =================================================================
  // 부트스트랩
  // =================================================================
  const canvas = $('glcanvas');
  let renderer = null, game = null;

  function startGame(seed, mode, saveData) {
    $('menu').style.display = 'none';
    $('loading').style.display = 'flex';
    setTimeout(() => {
      try {
        if (!renderer) renderer = new Renderer(canvas);
        game = new Game(renderer, seed, mode, saveData);
        setupInput();
        $('loading').style.display = 'none';
      } catch (e) {
        $('loading').textContent = '오류: ' + e.message;
        throw e;
      }
    }, 50);
  }

  // 메뉴
  const saved = (() => {
    try { return JSON.parse(localStorage.getItem(SAVE_KEY)); }
    catch (e) { return null; }
  })();
  if (saved && saved.seed !== undefined) {
    $('btn-continue').style.display = 'block';
    $('btn-continue').addEventListener('click', () => {
      startGame(saved.seed, saved.mode, saved);
    });
  }
  function newGame(mode) {
    const txt = $('seed-input').value.trim();
    let seed;
    if (!txt) seed = (Math.random() * 2147483647) | 0;
    else if (/^-?\d+$/.test(txt)) seed = parseInt(txt, 10) | 0;
    else {
      seed = 0;
      for (const ch of txt) seed = (Math.imul(seed, 31) + ch.charCodeAt(0)) | 0;
    }
    try { localStorage.removeItem(SAVE_KEY); } catch (e) {}
    startGame(seed, mode, null);
  }
  $('btn-new-surv').addEventListener('click', () => newGame('survival'));
  $('btn-new-crea').addEventListener('click', () => newGame('creative'));

  // =================================================================
  // 입력 (키보드/마우스)
  // =================================================================
  let inputReady = false;
  function setupInput() {
    if (inputReady) return;
    inputReady = true;
    const p = () => game.player;

    // --- 키보드 ---
    const keys = {};
    window.addEventListener('keydown', (e) => {
      if (game.ui.isOpen() &&
          !['Escape', 'KeyE'].includes(e.code)) return;
      keys[e.code] = true;
      syncKeys();
      if (e.code >= 'Digit1' && e.code <= 'Digit9') {
        p().sel = parseInt(e.code.slice(5), 10) - 1;
      } else if (e.code === 'KeyE') {
        if (game.ui.overlayOpen === 'invoverlay') game.ui.closeAll();
        else if (!game.ui.isOpen()) game.ui.openInventory();
      } else if (e.code === 'KeyQ') {
        if (!game.ui.isOpen()) p().dropOne();
      } else if (e.code === 'KeyC') {
        p().mode = p().mode === 'survival' ? 'creative' : 'survival';
        game.ui.setCreativeButtons(p().mode === 'creative');
        game.ui.toast(p().mode === 'creative' ? '크리에이티브 모드'
                                              : '서바이벌 모드');
      } else if (e.code === 'KeyF') {
        if (!game.ui.isOpen()) game.useAction();
      } else if (e.code === 'F3') {
        e.preventDefault();
        game.ui.debugOn = !game.ui.debugOn;
      } else if (e.code === 'Escape') {
        if (game.ui.isOpen()) game.ui.closeAll();
        else game.ui.openPause();
      }
    });
    window.addEventListener('keyup', (e) => {
      keys[e.code] = false;
      syncKeys();
    });
    function syncKeys() {
      const inp = p().input;
      inp.mz = (keys.KeyW ? 1 : 0) - (keys.KeyS ? 1 : 0);
      inp.mx = (keys.KeyD ? 1 : 0) - (keys.KeyA ? 1 : 0);
      inp.jump = !!keys.Space;
      inp.sprint = !!(keys.ShiftLeft || keys.ShiftRight);
      inp.sneak = !!(keys.ControlLeft || keys.ControlRight);
      inp.down = !!(keys.ControlLeft || keys.ControlRight);
    }

    // --- 마우스 (데스크톱) ---
    if (!IS_TOUCH) {
      canvas.addEventListener('click', () => {
        if (!game.ui.isOpen() && !document.pointerLockElement) {
          canvas.requestPointerLock();
        }
      });
      window.addEventListener('mousemove', (e) => {
        if (document.pointerLockElement !== canvas) return;
        p().yaw += e.movementX * 0.12;
        p().pitch = U.clamp(p().pitch + e.movementY * 0.12, -89, 89);
      });
      window.addEventListener('mousedown', (e) => {
        if (document.pointerLockElement !== canvas) return;
        if (e.button === 0) p().input.breaking = true;
        else if (e.button === 2) game.useAction();
      });
      window.addEventListener('mouseup', (e) => {
        if (e.button === 0) p().input.breaking = false;
      });
      window.addEventListener('wheel', (e) => {
        if (game.ui.isOpen()) return;
        p().sel = ((p().sel + (e.deltaY > 0 ? 1 : -1)) % 9 + 9) % 9;
      }, { passive: true });
    }
    window.addEventListener('contextmenu', (e) => e.preventDefault());
    window.addEventListener('beforeunload', () => { if (game) game.save(); });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && game) game.save();
    });
  }

  // =================================================================
  // 메인 루프
  // =================================================================
  let last = 0, fpsAcc = 0, fpsN = 0, fps = 0;
  function frame(now) {
    requestAnimationFrame(frame);
    if (!game) return;
    let dt = Math.min(0.1, (now - last) / 1000 || 0.016);
    last = now;
    fpsAcc += dt; fpsN++;
    if (fpsAcc >= 0.5) { fps = Math.round(fpsN / fpsAcc); fpsAcc = 0; fpsN = 0; }

    game.update(dt);

    const pl = game.player;
    const amb = Math.max(0.22, game.brightness());
    const sky = game.skyColor();
    game.renderer.beginFrame(pl.eyePos(), pl.yaw, pl.pitch,
                             IS_TOUCH ? 70 : 80, sky, amb, 0.004);
    game.renderer.drawChunks(game.world.chunks);
    game.drops.draw(game.renderer);
    game.mobs.draw(game.renderer, game);
    game.projectiles.draw(game.renderer);
    game.renderer.drawAlphaChunks(game.world.chunks);

    game.ui.updateHUD(dt, fps);
  }
  requestAnimationFrame(frame);
})();
