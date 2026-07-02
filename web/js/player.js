/* player.js - 물리 + 플레이어 + 인벤토리 (전역 PlayerMod) */
(function () {
  'use strict';
  const { clamp } = U;
  const GRAVITY = 24, EYE = 1.62;

  // ---------------- 복셀 AABB 물리 ----------------
  function collides(world, x, y, z, hw, h) {
    const x0 = Math.floor(x - hw), x1 = Math.floor(x + hw);
    const y0 = Math.floor(y), y1 = Math.floor(y + h - 1e-4);
    const z0 = Math.floor(z - hw), z1 = Math.floor(z + hw);
    for (let bx = x0; bx <= x1; bx++) {
      for (let by = y0; by <= y1; by++) {
        for (let bz = z0; bz <= z1; bz++) {
          if (world.isSolid(bx, by, bz)) return true;
        }
      }
    }
    return false;
  }

  function makeBody(hw, h) {
    return { hw, h, vel: [0, 0, 0], grounded: false, inWater: false,
             headInWater: false, groundBlock: 0 };
  }

  function moveBody(world, body, pos, dt) {
    let [x, y, z] = pos;
    const [vx, vy, vz] = body.vel;
    const { hw, h } = body;
    body.grounded = false;
    body.hitWall = false;

    let nx = x + vx * dt;
    if (vx !== 0 && collides(world, nx, y, z, hw, h)) {
      const step = 0.05 * Math.sign(vx);
      while (Math.abs(nx - x) > 0.001 && collides(world, nx, y, z, hw, h)) {
        nx -= step;
        if ((vx > 0 && nx < x) || (vx < 0 && nx > x)) { nx = x; break; }
      }
      if (collides(world, nx, y, z, hw, h)) nx = x;
      body.vel[0] = 0; body.hitWall = true;
    }
    x = nx;

    let nz = z + vz * dt;
    if (vz !== 0 && collides(world, x, y, nz, hw, h)) {
      const step = 0.05 * Math.sign(vz);
      while (Math.abs(nz - z) > 0.001 && collides(world, x, y, nz, hw, h)) {
        nz -= step;
        if ((vz > 0 && nz < z) || (vz < 0 && nz > z)) { nz = z; break; }
      }
      if (collides(world, x, y, nz, hw, h)) nz = z;
      body.vel[2] = 0; body.hitWall = true;
    }
    z = nz;

    let ny = y + vy * dt;
    if (vy !== 0 && collides(world, x, ny, z, hw, h)) {
      if (vy < 0) {
        ny = Math.floor(ny) + 1;
        while (collides(world, x, ny, z, hw, h)) {
          ny += 1;
          if (ny > y + 1) { ny = y; break; }
        }
        body.grounded = true;
      } else {
        ny = y;
      }
      body.vel[1] = 0;
    }
    y = ny;

    if (body.vel[1] <= 0 && collides(world, x, y - 0.05, z, hw, h)) {
      body.grounded = true;
    }
    body.groundBlock = world.getBlock(x, y - 0.5, z);

    const feet = BLK.B[world.getBlock(x, y + 0.2, z)];
    const head = BLK.B[world.getBlock(x, y + h - 0.2, z)];
    body.inWater = feet.liquid || head.liquid;
    body.headInWater = head.liquid;
    return [x, y, z];
  }

  function applyGravity(body, dt) {
    const g = GRAVITY * (body.inWater ? 0.35 : 1);
    body.vel[1] -= g * dt;
    const lim = body.inWater ? 10 : 42;
    if (body.vel[1] < -lim) body.vel[1] = -lim;
  }

  // ---------------- 인벤토리 ----------------
  const INV_SIZE = 36;
  function makeStack(id, cnt) {
    const it = BLK.ITEMS[id];
    if (!it) return null;
    const s = { id, cnt: cnt || 1 };
    if (it.dur > 0) s.dur = it.dur;
    return s;
  }
  function addItem(slots, id, cnt) {
    const it = BLK.ITEMS[id];
    if (!it) return cnt;
    let left = cnt;
    if (!it.dur) {
      for (const s of slots) {
        if (s && s.id === id && s.cnt < it.stack) {
          const take = Math.min(it.stack - s.cnt, left);
          s.cnt += take; left -= take;
          if (left <= 0) return 0;
        }
      }
    }
    for (let i = 0; i < slots.length; i++) {
      if (!slots[i]) {
        const take = Math.min(it.stack, left);
        slots[i] = makeStack(id, take);
        left -= take;
        if (left <= 0) return 0;
      }
    }
    return left;
  }
  function countItem(slots, id) {
    let n = 0;
    for (const s of slots) if (s && s.id === id) n += s.cnt;
    return n;
  }
  function removeItem(slots, id, cnt) {
    if (countItem(slots, id) < cnt) return false;
    let left = cnt;
    for (let i = 0; i < slots.length; i++) {
      const s = slots[i];
      if (s && s.id === id) {
        const take = Math.min(s.cnt, left);
        s.cnt -= take; left -= take;
        if (s.cnt <= 0) slots[i] = null;
        if (left <= 0) return true;
      }
    }
    return true;
  }

  // ---------------- 플레이어 ----------------
  class Player {
    constructor(game, pos, mode) {
      this.game = game;
      this.pos = pos.slice();
      this.spawn = pos.slice();
      this.body = makeBody(0.3, 1.8);
      this.yaw = 0; this.pitch = 0;
      this.mode = mode || 'survival';
      this.hp = 20; this.hunger = 20; this.stamina = 100; this.oxygen = 100;
      this.dead = false;
      this.slots = Array(INV_SIZE).fill(null);   // 0~8 = 핫바
      this.sel = 0;
      this.target = null; this.targetPrev = null;
      this.breakProgress = 0; this.breakingKey = null;
      this.attackCd = 0; this.eatTimer = 0;
      this.hungerTimer = 0; this.regenTimer = 0; this.dmgTick = 0;
      // 입력 상태 (main.js/ui.js 가 갱신)
      this.input = { mx: 0, mz: 0, jump: false, sprint: false, sneak: false,
                     breaking: false, down: false };
    }

    eyePos() { return [this.pos[0], this.pos[1] + EYE, this.pos[2]]; }
    forward() {
      const cy = this.yaw * Math.PI / 180, cp = this.pitch * Math.PI / 180;
      return [Math.sin(cy) * Math.cos(cp), -Math.sin(cp),
              Math.cos(cy) * Math.cos(cp)];
    }
    selected() { return this.slots[this.sel]; }
    selectedItem() {
      const s = this.selected();
      return s ? BLK.ITEMS[s.id] : null;
    }

    update(dt) {
      if (this.dead) return;
      const world = this.game.world, inp = this.input;

      // 이동
      const cy = this.yaw * Math.PI / 180;
      const fx = Math.sin(cy), fz = Math.cos(cy);
      const rx = Math.cos(cy), rz = -Math.sin(cy);
      let dx = fx * inp.mz + rx * inp.mx, dz = fz * inp.mz + rz * inp.mx;
      const d = Math.hypot(dx, dz);
      if (d > 1) { dx /= d; dz /= d; }

      const sprinting = inp.sprint && this.stamina > 1 && this.hunger > 6;
      if (this.mode === 'creative') {
        const spd = 10;
        this.body.vel[0] = dx * spd;
        this.body.vel[2] = dz * spd;
        this.body.vel[1] = inp.jump ? spd : inp.down ? -spd : 0;
      } else {
        let spd = sprinting ? 6.2 : inp.sneak ? 1.8 : 4.3;
        if (this.body.inWater) spd *= 0.55;
        this.body.vel[0] = dx * spd;
        this.body.vel[2] = dz * spd;
        if (inp.jump) {
          if (this.body.inWater) this.body.vel[1] = 3.2;
          else if (this.body.grounded) this.body.vel[1] = 8.2;
        }
        applyGravity(this.body, dt);
        if (sprinting && d > 0) this.stamina = Math.max(0, this.stamina - 12 * dt);
        else this.stamina = Math.min(100, this.stamina + 8 * dt);
      }

      const prevVy = this.body.vel[1];
      this.pos = moveBody(world, this.body, this.pos, dt);

      // 낙하 피해 / 탄성 블록
      if (this.body.grounded && prevVy < -12) {
        const gb = BLK.B[this.body.groundBlock];
        if (gb && gb.bounce > 0) this.body.vel[1] = -prevVy * gb.bounce;
        else if (this.mode === 'survival' && !this.body.inWater) {
          const dmg = Math.floor((-prevVy - 12) * 0.7);
          if (dmg > 0) this.damage(dmg);
        }
      }
      if (this.pos[1] < -10) {
        this.pos[1] = WorldMod.CHH;
        this.body.vel[1] = 0;
        if (this.mode === 'survival') this.damage(4);
      }

      this.updateSurvival(dt);
      this.updateTarget();
      this.updateBreaking(dt);
    }

    updateSurvival(dt) {
      if (this.mode !== 'survival' || this.dead) return;
      this.hungerTimer += dt;
      if (this.hungerTimer >= 30) {
        this.hungerTimer = 0;
        this.hunger = Math.max(0, this.hunger - 1);
      }
      this.dmgTick += dt;
      if (this.hunger >= 16 && this.hp < 20) {
        this.regenTimer += dt;
        if (this.regenTimer >= 3) { this.regenTimer = 0; this.hp = Math.min(20, this.hp + 1); }
      } else if (this.hunger <= 0 && this.dmgTick >= 3) {
        this.dmgTick = 0; this.damage(1);
      }
      if (this.body.headInWater) {
        this.oxygen = Math.max(0, this.oxygen - 8 * dt);
        if (this.oxygen <= 0 && this.dmgTick >= 1.5) {
          this.dmgTick = 0; this.damage(2);
        }
      } else {
        this.oxygen = Math.min(100, this.oxygen + 25 * dt);
      }
      // 접촉 피해 블록 (선인장)
      const world = this.game.world;
      for (const [ox, oy] of [[0.5, 0], [-0.5, 0], [0, 0.5], [0, -0.5]]) {
        const b = BLK.B[world.getBlock(this.pos[0] + ox, this.pos[1] + 0.5,
                                       this.pos[2] + oy)];
        if (b && b.damage > 0 && this.dmgTick >= 0.8) {
          this.dmgTick = 0; this.damage(b.damage);
          break;
        }
      }
    }

    damage(n) {
      if (this.mode === 'creative' || this.dead) return;
      this.hp -= n;
      if (this.hp <= 0) { this.hp = 0; this.die(); }
    }
    die() {
      this.dead = true;
      // 일부 아이템 드롭
      for (let i = 0; i < this.slots.length; i++) {
        if (this.slots[i] && Math.random() < 0.4) {
          this.game.drops.spawnStack(this.slots[i],
            [this.pos[0], this.pos[1] + 1, this.pos[2]]);
          this.slots[i] = null;
        }
      }
      this.game.onPlayerDeath();
    }
    respawn() {
      this.pos = this.spawn.slice();
      this.body.vel = [0, 0, 0];
      this.hp = 20; this.hunger = 20; this.stamina = 100; this.oxygen = 100;
      this.dead = false;
    }

    updateTarget() {
      const world = this.game.world;
      const [ex, ey, ez] = this.eyePos();
      const [fx, fy, fz] = this.forward();
      const res = U.raycast(ex, ey, ez, fx, fy, fz, 5, (x, y, z) => {
        const b = BLK.B[world.getBlock(x, y, z)];
        return b.id !== 0 && !b.liquid;
      });
      this.target = res ? res.hit : null;
      this.targetPrev = res ? res.prev : null;
    }

    breakTimeFor(def) {
      const it = this.selectedItem();
      let speed = 1, lvl = 0;
      if (it && it.tool) {
        lvl = it.toolLvl;
        if (it.tool === def.tool) speed = it.speed;
      }
      const canDrop = lvl >= def.toolLvl;
      let t = Math.max(0.05, def.hard * 1.2) / speed;
      if (!canDrop) t *= 3;
      return { t, canDrop };
    }

    updateBreaking(dt) {
      this.attackCd = Math.max(0, this.attackCd - dt);
      if (!this.input.breaking) {
        this.breakProgress = 0; this.breakingKey = null;
        return;
      }
      // 시선의 몹 우선 공격
      const mob = this.game.mobs.rayPick(this.eyePos(), this.forward(), 3.5);
      if (mob) {
        if (this.attackCd <= 0) {
          this.attackCd = 0.5;
          const it = this.selectedItem();
          mob.hurt(it ? it.dmg : 1, this.game, this.pos);
          this.damageTool();
        }
        this.breakProgress = 0;
        return;
      }
      if (!this.target) { this.breakProgress = 0; return; }
      const [x, y, z] = this.target;
      const world = this.game.world;
      const id = world.getBlock(x, y, z);
      if (id === 0) return;
      const def = BLK.B[id];
      if (def.hard < 0 && this.mode !== 'creative') return;

      const key = x + ',' + y + ',' + z;
      if (this.breakingKey !== key) { this.breakingKey = key; this.breakProgress = 0; }

      if (this.mode === 'creative') { this.finishBreak(x, y, z, def, false); return; }
      const { t, canDrop } = this.breakTimeFor(def);
      this.breakProgress += dt / t;
      if (this.breakProgress >= 1) this.finishBreak(x, y, z, def, canDrop);
    }

    finishBreak(x, y, z, def, drops) {
      const world = this.game.world, ID = BLK.ID;
      world.setBlock(x, y, z, 0);
      this.breakProgress = 0; this.breakingKey = null;

      if (def.id === ID.CHEST) {
        const key = x + ',' + y + ',' + z;
        const cont = world.containers[key];
        if (cont) {
          for (const s of cont.slots) {
            if (s) this.game.drops.spawnStack(s, [x + .5, y + .5, z + .5]);
          }
          world.removeContainer(x, y, z);
        }
      } else if (def.id === ID.FURNACE) {
        world.removeContainer(x, y, z);
      }
      if (def.id === ID.BOOM) {
        this.game.explode([x + .5, y + .5, z + .5], 3.2, 14);
        return;
      }
      if (drops && this.mode === 'survival') {
        for (const [iid, cnt, prob] of def.drops) {
          if (Math.random() < prob) {
            this.game.drops.spawn(iid, cnt, [x + .5, y + .4, z + .5]);
          }
        }
        this.damageTool();
      }
    }

    damageTool() {
      const s = this.selected();
      if (s && s.dur !== undefined) {
        s.dur -= 1;
        if (s.dur <= 0) this.slots[this.sel] = null;
      }
    }

    /** 우클릭/✋: 상호작용 > 음식 > 블록 설치. 반환: 처리 결과 문자열 */
    use() {
      const world = this.game.world, ID = BLK.ID;
      if (this.target) {
        const [x, y, z] = this.target;
        const id = world.getBlock(x, y, z);
        if (id === ID.WORKBENCH) return 'workbench';
        if (id === ID.FURNACE) return 'furnace:' + x + ',' + y + ',' + z;
        if (id === ID.CHEST) return 'chest:' + x + ',' + y + ',' + z;
      }
      const it = this.selectedItem();
      if (it && it.food > 0) {
        if (this.hunger >= 20) return null;
        this.hunger = Math.min(20, this.hunger + it.food);
        if (it.heal) this.hp = Math.min(20, this.hp + it.heal);
        if ((it.id === 'raw_meat' || it.id === 'raw_chicken') &&
            Math.random() < 0.3) {
          this.hunger = Math.max(0, this.hunger - 3);
        }
        if (this.mode === 'survival') this.consumeSelected();
        return 'eat';
      }
      return this.placeBlock() ? 'place' : null;
    }

    placeBlock() {
      if (!this.target || !this.targetPrev) return false;
      const it = this.selectedItem();
      if (!it || it.place === null) return false;
      const def = BLK.B[it.place];
      const [x, y, z] = this.targetPrev;
      const world = this.game.world;
      if (world.getBlock(x, y, z) !== 0) return false;
      // 플레이어 AABB 와 겹침 방지
      if (def.solid) {
        const [px, py, pz] = this.pos;
        if (Math.abs(x + .5 - px) < .5 + this.body.hw &&
            Math.abs(z + .5 - pz) < .5 + this.body.hw &&
            y + 1 > py && y < py + this.body.h) return false;
      }
      world.setBlock(x, y, z, def.id);
      if (this.mode === 'survival') this.consumeSelected();
      return true;
    }

    consumeSelected() {
      const s = this.selected();
      if (!s) return;
      s.cnt -= 1;
      if (s.cnt <= 0) this.slots[this.sel] = null;
    }

    dropOne() {
      const s = this.selected();
      if (!s) return;
      const one = { id: s.id, cnt: 1 };
      if (s.dur !== undefined) one.dur = s.dur;
      s.cnt -= 1;
      if (s.cnt <= 0) this.slots[this.sel] = null;
      const [fx, fy, fz] = this.forward();
      const [ex, ey, ez] = this.eyePos();
      this.game.drops.spawnStack(one, [ex + fx, ey - .3, ez + fz],
                                 [fx * 5, 2, fz * 5]);
    }
  }

  window.PlayerMod = { Player, makeBody, moveBody, applyGravity, collides,
                       makeStack, addItem, removeItem, countItem };
})();
