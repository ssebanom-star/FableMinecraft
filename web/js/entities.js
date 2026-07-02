/* entities.js - 드롭 아이템 / 몹 / 투사체 (전역 EntMod) */
(function () {
  'use strict';
  const { makeBody, moveBody, applyGravity, addItem } = PlayerMod;
  const { distSq } = U;

  // ---------------- 드롭 아이템 ----------------
  class Drops {
    constructor(world) {
      this.world = world;
      this.list = [];
      this.max = 80;
      this.lifetime = 120;
    }
    spawn(id, cnt, pos, vel) {
      if (!BLK.ITEMS[id]) return;
      this.spawnStack({ id, cnt }, pos, vel);
    }
    spawnStack(stack, pos, vel) {
      if (!stack || stack.cnt <= 0) return;
      if (this.list.length >= this.max) this.list.shift();
      const a = Math.random() * Math.PI * 2;
      this.list.push({
        stack, pos: pos.slice(),
        body: makeBody(0.12, 0.25),
        vel: vel ? vel.slice() : [Math.cos(a) * 1.5, 3, Math.sin(a) * 1.5],
        age: 0, delay: 0.6, rot: Math.random() * 360,
      });
    }
    update(dt, player) {
      for (const d of this.list) {
        d.age += dt;
        if (d.delay > 0) d.delay -= dt;
        d.body.vel = d.vel;
        applyGravity(d.body, dt);
        d.vel[0] *= 0.92; d.vel[2] *= 0.92;
        d.pos = moveBody(this.world, d.body, d.pos, dt);
        d.rot += dt * 90;
      }
      // 획득
      for (let i = this.list.length - 1; i >= 0; i--) {
        const d = this.list[i];
        if (d.age >= this.lifetime) { this.list.splice(i, 1); continue; }
        if (d.delay > 0) continue;
        if (distSq(d.pos, player.pos) < 1.6 * 1.6) {
          const left = d.stack.dur !== undefined
            ? this._addTool(player.slots, d.stack)
            : addItem(player.slots, d.stack.id, d.stack.cnt);
          if (left === 0) this.list.splice(i, 1);
          else d.stack.cnt = left;
        }
      }
      // 병합
      for (let i = 0; i < this.list.length; i++) {
        const a = this.list[i];
        if (a.stack.dur !== undefined) continue;
        for (let j = this.list.length - 1; j > i; j--) {
          const b = this.list[j];
          if (b.stack.id !== a.stack.id || b.stack.dur !== undefined) continue;
          if (distSq(a.pos, b.pos) < 1) {
            a.stack.cnt += b.stack.cnt;
            this.list.splice(j, 1);
          }
        }
      }
    }
    _addTool(slots, stack) {
      for (let i = 0; i < slots.length; i++) {
        if (!slots[i]) { slots[i] = Object.assign({}, stack); return 0; }
      }
      return stack.cnt;
    }
    draw(r) {
      for (const d of this.list) {
        const it = BLK.ITEMS[d.stack.id];
        const c = it ? it.col : [1, 0, 1];
        r.drawCube(d.pos[0], d.pos[1] + 0.15, d.pos[2],
                   0.28, 0.28, 0.28, d.rot, c[0], c[1], c[2], 1);
      }
    }
  }

  // ---------------- 몹 ----------------
  const MOB_TYPES = {
    pig: { disp: '돼지', hp: 10, speed: 2.2, dmg: 0, range: 0, detect: 0,
           ai: 'passive', col: [.92, .65, .65], size: [.9, .8, 1.0],
           drops: [['raw_meat', 1, 2, 1]], biomes: null, time: 'day' },
    cow: { disp: '소', hp: 12, speed: 2, dmg: 0, range: 0, detect: 0,
           ai: 'passive', col: [.45, .32, .25], size: [.95, 1, 1.2],
           drops: [['raw_meat', 1, 3, 1], ['leather', 0, 2, .8]],
           biomes: null, time: 'day' },
    chicken: { disp: '닭', hp: 4, speed: 2.4, dmg: 0, range: 0, detect: 0,
               ai: 'passive', col: [.95, .93, .85], size: [.5, .6, .55],
               drops: [['raw_chicken', 1, 1, 1], ['feather', 0, 2, .9]],
               biomes: null, time: 'day' },
    shambler: { disp: '괴인', hp: 20, speed: 2.6, dmg: 4, range: 1.6,
                detect: 16, ai: 'hostile', col: [.35, .55, .35],
                size: [.7, 1.7, .5],
                drops: [['string', 0, 2, .6], ['bone', 0, 1, .4]],
                biomes: null, time: 'night' },
    boneshot: { disp: '해골 사수', hp: 16, speed: 2.4, dmg: 4, range: 13,
                detect: 17, ai: 'ranged', col: [.85, .85, .8],
                size: [.6, 1.7, .4],
                drops: [['bone', 1, 3, 1]], biomes: null, time: 'night' },
    boomer: { disp: '폭발 덩굴', hp: 16, speed: 2.6, dmg: 0, range: 2.4,
              detect: 15, ai: 'exploder', col: [.3, .65, .3],
              size: [.6, 1.5, .6],
              drops: [['gunpowder', 1, 2, 1]], biomes: null, time: 'night' },
  };

  class Mob {
    constructor(type, pos) {
      this.type = type;
      this.t = MOB_TYPES[type];
      this.pos = pos.slice();
      const [w, h, d] = this.t.size;
      this.body = makeBody(Math.max(w, d) / 2, h);
      this.hp = this.t.hp;
      this.yaw = 0;
      this.wander = 0; this.wdir = null; this.flee = 0;
      this.atkCd = 0; this.fuse = 0; this.hurtT = 0;
      this.dead = false;
    }
    hurt(n, game, srcPos) {
      if (this.dead) return;
      this.hp -= n;
      this.hurtT = 0.25;
      this.flee = 5;
      if (srcPos) {
        const dx = this.pos[0] - srcPos[0], dz = this.pos[2] - srcPos[2];
        const d = Math.hypot(dx, dz) || 1;
        this.body.vel[0] += dx / d * 6;
        this.body.vel[1] += 3.5;
        this.body.vel[2] += dz / d * 6;
      }
      if (this.hp <= 0) this.die(game);
    }
    die(game, silent) {
      if (this.dead) return;
      this.dead = true;
      if (!silent) {
        for (const [id, lo, hi, prob] of this.t.drops) {
          if (Math.random() < prob) {
            const n = lo + Math.floor(Math.random() * (hi - lo + 1));
            if (n > 0) game.drops.spawn(id, n,
              [this.pos[0], this.pos[1] + .5, this.pos[2]]);
          }
        }
      }
    }
    steer(dx, dz, mult) {
      const d = Math.hypot(dx, dz);
      if (d < 1e-5) return;
      const spd = this.t.speed * (mult || 1);
      this.body.vel[0] = dx / d * spd;
      this.body.vel[2] = dz / d * spd;
      this.yaw = Math.atan2(dx, dz) * 180 / Math.PI;
      if (this.body.hitWall && this.body.grounded) this.body.vel[1] = 8;
      if (this.body.inWater) this.body.vel[1] = Math.max(this.body.vel[1], 2);
    }
    stop() { this.body.vel[0] *= .6; this.body.vel[2] *= .6; }

    tick(game, dt) {
      const p = game.player;
      const dx = p.pos[0] - this.pos[0], dz = p.pos[2] - this.pos[2];
      const d2 = distSq(this.pos, p.pos);

      switch (this.t.ai) {
        case 'passive':
          if (this.flee > 0 || d2 < 6) {
            this.flee = Math.max(0, this.flee - dt);
            this.steer(-dx, -dz, 1.4);
          } else {
            this.wander -= dt;
            if (this.wander <= 0) {
              this.wander = 2 + Math.random() * 4;
              this.wdir = Math.random() < .55
                ? [Math.cos(Math.random() * 6.28),
                   Math.sin(Math.random() * 6.28)] : null;
            }
            if (this.wdir) this.steer(this.wdir[0], this.wdir[1], .5);
            else this.stop();
          }
          break;
        case 'hostile':
          if (p.dead || d2 > this.t.detect ** 2) { this.stop(); break; }
          if (d2 <= this.t.range ** 2) {
            this.stop();
            this.atkCd -= dt;
            if (this.atkCd <= 0) {
              this.atkCd = 1.2;
              game.damagePlayer(this.t.dmg, this.pos);
            }
          } else this.steer(dx, dz);
          break;
        case 'ranged': {
          if (p.dead || d2 > this.t.detect ** 2) { this.stop(); break; }
          const dist = Math.sqrt(d2);
          if (dist < 6) this.steer(-dx, -dz);
          else if (dist > 12) this.steer(dx, dz);
          else this.stop();
          this.atkCd -= dt;
          if (this.atkCd <= 0 && dist < 15) {
            this.atkCd = 2.5;
            const oy = this.pos[1] + this.body.h * .7;
            const speed = 16;
            // 중력 낙차 보정 (비행시간 동안 떨어지는 만큼 위로 조준)
            const flight = dist / speed;
            const drop = 0.5 * 14 * flight * flight;
            game.projectiles.spawn(
              [this.pos[0], oy, this.pos[2]],
              [dx, p.pos[1] + 1.2 - oy + drop, dz], speed,
              this.t.dmg, 'mob');
          }
          break;
        }
        case 'exploder':
          if (this.fuse > 0) {
            this.stop();
            this.fuse -= dt;
            if (this.fuse <= 0) {
              this.die(game, true);
              game.explode([this.pos[0], this.pos[1] + .5, this.pos[2]],
                           3, 15);
            }
            break;
          }
          if (p.dead || d2 > this.t.detect ** 2) { this.stop(); break; }
          if (d2 < 2.4 ** 2) { this.fuse = 1.4; this.stop(); }
          else this.steer(dx, dz);
          break;
      }

      applyGravity(this.body, dt);
      this.pos = moveBody(game.world, this.body, this.pos, dt);
      if (this.hurtT > 0) this.hurtT -= dt;
      if (this.pos[1] < -8) this.die(game, true);
    }
  }

  class Mobs {
    constructor(world) {
      this.world = world;
      this.list = [];
      this.max = 14;
      this.spawnTimer = 0;
    }
    spawn(type, pos) {
      const m = new Mob(type, pos);
      this.list.push(m);
      return m;
    }
    trySpawn(game) {
      if (this.list.length >= this.max) return;
      const p = game.player;
      const a = Math.random() * Math.PI * 2;
      const dist = 14 + Math.random() * 16;
      const x = p.pos[0] + Math.cos(a) * dist;
      const z = p.pos[2] + Math.sin(a) * dist;
      const y = this.world.surfaceHeight(x, z) + 1;
      if (!this.world.isSolid(x, y - 1, z)) return;
      if (this.world.getBlock(x, y, z) !== 0) return;
      const isDay = game.isDay();
      const light = this.world.lightAt(x, y, z);
      const pool = [];
      for (const t in MOB_TYPES) {
        const mt = MOB_TYPES[t];
        if (mt.time === 'day' && (!isDay || light < 8)) continue;
        if (mt.time === 'night' && isDay && light >= 8) continue;
        pool.push(t);
      }
      if (!pool.length) return;
      this.spawn(pool[Math.floor(Math.random() * pool.length)], [x, y, z]);
    }
    update(game, dt) {
      this.spawnTimer -= dt;
      if (this.spawnTimer <= 0) {
        this.spawnTimer = 2.5;
        this.trySpawn(game);
      }
      const p = game.player;
      for (let i = this.list.length - 1; i >= 0; i--) {
        const m = this.list[i];
        const d2 = distSq(m.pos, p.pos);
        if (d2 > 70 * 70) { this.list.splice(i, 1); continue; }
        if (d2 < 45 * 45) m.tick(game, dt);   // AI 거리 제한
        if (m.dead) this.list.splice(i, 1);
      }
    }
    rayPick(origin, dir, maxDist) {
      let best = null, bestT = maxDist;
      for (const m of this.list) {
        const cx = m.pos[0] - origin[0];
        const cy = m.pos[1] + m.body.h * .5 - origin[1];
        const cz = m.pos[2] - origin[2];
        const t = cx * dir[0] + cy * dir[1] + cz * dir[2];
        if (t < 0 || t > bestT) continue;
        const p2 = (cx - dir[0] * t) ** 2 + (cy - dir[1] * t) ** 2 +
                   (cz - dir[2] * t) ** 2;
        if (p2 < (m.body.hw + .55) ** 2) { best = m; bestT = t; }
      }
      return best;
    }
    draw(r, game) {
      for (const m of this.list) {
        const [w, h, d] = m.t.size;
        let c = m.t.col;
        if (m.hurtT > 0) c = [1, .3, .3];
        else if (m.fuse > 0 && ((m.fuse * 8) | 0) % 2 === 0) c = [1, 1, 1];
        r.drawCube(m.pos[0], m.pos[1] + h * .42, m.pos[2],
                   w, h * .65, d, m.yaw, c[0], c[1], c[2], 1);
        r.drawCube(m.pos[0], m.pos[1] + h * .9, m.pos[2],
                   w * .6, h * .32, w * .6, m.yaw,
                   Math.min(1, c[0] * 1.15), Math.min(1, c[1] * 1.15),
                   Math.min(1, c[2] * 1.15), 1);
      }
    }
  }

  // ---------------- 투사체 ----------------
  class Projectiles {
    constructor() { this.list = []; }
    spawn(pos, dir, speed, dmg, owner) {
      const d = Math.hypot(dir[0], dir[1], dir[2]) || 1;
      this.list.push({
        pos: pos.slice(),
        vel: [dir[0] / d * speed, dir[1] / d * speed, dir[2] / d * speed],
        dmg, owner, age: 0,
      });
    }
    update(game, dt) {
      for (let i = this.list.length - 1; i >= 0; i--) {
        const p = this.list[i];
        p.age += dt;
        if (p.age > 8) { this.list.splice(i, 1); continue; }
        p.vel[1] -= 14 * dt;
        p.pos[0] += p.vel[0] * dt;
        p.pos[1] += p.vel[1] * dt;
        p.pos[2] += p.vel[2] * dt;
        if (game.world.isSolid(p.pos[0], p.pos[1], p.pos[2])) {
          this.list.splice(i, 1); continue;
        }
        if (p.owner === 'player') {
          let hit = false;
          for (const m of game.mobs.list) {
            if (distSq(p.pos, [m.pos[0], m.pos[1] + m.body.h * .5,
                               m.pos[2]]) < .8) {
              m.hurt(p.dmg, game, p.pos);
              hit = true; break;
            }
          }
          if (hit) { this.list.splice(i, 1); continue; }
        } else {
          const pl = game.player;
          if (distSq(p.pos, [pl.pos[0], pl.pos[1] + .9, pl.pos[2]]) < .8) {
            game.damagePlayer(p.dmg, p.pos);
            this.list.splice(i, 1); continue;
          }
        }
      }
    }
    draw(r) {
      for (const p of this.list) {
        r.drawCube(p.pos[0], p.pos[1], p.pos[2], .12, .12, .3, 0,
                   .8, .78, .72, 1);
      }
    }
  }

  window.EntMod = { Drops, Mobs, Projectiles, MOB_TYPES };
})();
