/* ui.js - HUD / 터치 컨트롤 / 패널 (전역 UIManager) */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const { addItem, removeItem, countItem } = PlayerMod;

  const IS_TOUCH = ('ontouchstart' in window) ||
    (window.matchMedia && matchMedia('(pointer: coarse)').matches);

  const SMELT_TIME = 3.0;

  class UIManager {
    constructor(game) {
      this.game = game;
      this.overlayOpen = null;      // 열린 패널 id
      this.invSel = -1;             // 인벤토리 탭-선택 슬롯
      this.furnaceState = null;
      this.chestState = null;
      this.toastTimer = 0;
      this.debugOn = false;

      this._buildHotbar();
      this._bindButtons();
      if (IS_TOUCH) this._setupTouch();
    }

    // =============== 핫바 ===============
    _buildHotbar() {
      const bar = $('hotbar');
      bar.innerHTML = '';
      this.hslots = [];
      for (let i = 0; i < 9; i++) {
        const el = document.createElement('div');
        el.className = 'hslot';
        el.innerHTML = '<div class="swatch"></div><div class="cnt"></div>';
        el.addEventListener('pointerdown', (e) => {
          e.stopPropagation();
          this.game.player.sel = i;
        });
        bar.appendChild(el);
        this.hslots.push(el);
      }
    }

    refreshHotbar() {
      const p = this.game.player;
      for (let i = 0; i < 9; i++) {
        const el = this.hslots[i], s = p.slots[i];
        el.classList.toggle('sel', i === p.sel);
        const sw = el.firstChild, cnt = el.lastChild;
        if (s) {
          const it = BLK.ITEMS[s.id];
          sw.style.background = it ? cssCol(it.col) : '#f0f';
          cnt.textContent = s.cnt > 1 ? s.cnt : '';
        } else {
          sw.style.background = 'transparent';
          cnt.textContent = '';
        }
      }
      const s = p.slots[p.sel];
      $('selname').textContent = s ? BLK.ITEMS[s.id].disp : '';
    }

    // =============== HUD ===============
    updateHUD(dt, fps) {
      const g = this.game, p = g.player;
      this.refreshHotbar();
      $('hp').firstElementChild.style.width = (p.hp / 20 * 100) + '%';
      $('hg').firstElementChild.style.width = (p.hunger / 20 * 100) + '%';
      $('st').firstElementChild.style.width = p.stamina + '%';
      $('ox').firstElementChild.style.width = p.oxygen + '%';

      const biome = WorldMod.BIOMES[g.world.biomeAt(p.pos[0], p.pos[2])];
      $('info').textContent =
        g.clockString() + '  ·  ' + (biome ? biome.disp : '') + '  ·  ' +
        (p.mode === 'creative' ? '크리에이티브' : '서바이벌');

      // 바라보는 블록
      if (p.target) {
        const id = g.world.getBlock(p.target[0], p.target[1], p.target[2]);
        $('targetname').textContent = id ? BLK.B[id].disp : '';
      } else $('targetname').textContent = '';

      // 파괴 진행
      const bb = $('breakbar');
      if (p.breakProgress > 0.02) {
        bb.style.display = 'block';
        $('breakfill').style.width =
          Math.min(100, p.breakProgress * 100) + '%';
      } else bb.style.display = 'none';

      // 토스트
      if (this.toastTimer > 0) {
        this.toastTimer -= dt;
        if (this.toastTimer <= 0) $('toast').style.opacity = 0;
      }

      // 디버그
      const dbg = $('debug');
      dbg.style.display = this.debugOn ? 'block' : 'none';
      if (this.debugOn) {
        dbg.textContent =
          'FPS: ' + fps +
          '\nXYZ: ' + p.pos.map(v => v.toFixed(1)).join(' / ') +
          '\n청크: ' + Math.floor(p.pos[0] / 16) + ',' +
          Math.floor(p.pos[2] / 16) + ' (로드 ' + g.world.chunks.size + ')' +
          '\n시간: ' + g.time.toFixed(3) +
          '\n몹: ' + g.mobs.list.length + '  드롭: ' + g.drops.list.length +
          '\n시드: ' + g.world.seed;
      }

      // 열린 화로 패널 실시간 갱신
      if (this.overlayOpen === 'furnaceoverlay' && this.furnaceState) {
        this._renderFurnace();
      }
    }

    toast(msg) {
      const t = $('toast');
      t.textContent = msg;
      t.style.opacity = 1;
      this.toastTimer = 1.8;
    }

    // =============== 오버레이 공통 ===============
    open(id) {
      this.closeAll();
      this.overlayOpen = id;
      $(id).style.display = 'flex';
      if (document.pointerLockElement) document.exitPointerLock();
    }
    closeAll() {
      for (const id of ['invoverlay', 'furnaceoverlay', 'chestoverlay',
                        'pause', 'deathoverlay']) {
        $(id).style.display = 'none';
      }
      this.overlayOpen = null;
      this.invSel = -1;
    }
    isOpen() { return this.overlayOpen !== null; }

    // =============== 버튼 바인딩 ===============
    _bindButtons() {
      const g = this.game;
      $('btn-inv').addEventListener('pointerdown', (e) => {
        e.stopPropagation();
        if (this.overlayOpen === 'invoverlay') this.closeAll();
        else this.openInventory();
      });
      $('btn-pause').addEventListener('pointerdown', (e) => {
        e.stopPropagation();
        this.openPause();
      });
      $('btn-resume').addEventListener('click', () => this.closeAll());
      $('btn-save').addEventListener('click', () => {
        g.save(); this.closeAll(); this.toast('저장되었습니다');
      });
      $('btn-rd').addEventListener('click', () => {
        const w = g.world;
        w.renderDistance = w.renderDistance >= 4 ? 1 : w.renderDistance + 1;
        $('btn-rd').textContent = '렌더 거리: ' + w.renderDistance;
      });
      $('btn-tomenu').addEventListener('click', () => {
        g.save();
        location.reload();
      });
      $('btn-respawn').addEventListener('click', () => {
        g.player.respawn();
        this.closeAll();
      });

      // 인벤토리 탭
      $('tab-inv').addEventListener('click', () => this._tab('inv'));
      $('tab-craft').addEventListener('click', () => this._tab('craft'));
      $('btn-close-inv').addEventListener('click', () => this.closeAll());
      $('btn-close-craft').addEventListener('click', () => this.closeAll());
      $('btn-drop1').addEventListener('click', () => {
        if (this.invSel >= 0) {
          const p = g.player, s = p.slots[this.invSel];
          if (s) {
            const one = { id: s.id, cnt: 1 };
            if (s.dur !== undefined) one.dur = s.dur;
            s.cnt -= 1;
            if (s.cnt <= 0) { p.slots[this.invSel] = null; this.invSel = -1; }
            const f = p.forward();
            g.drops.spawnStack(one,
              [p.pos[0] + f[0], p.pos[1] + 1.2, p.pos[2] + f[2]],
              [f[0] * 5, 2, f[2] * 5]);
          }
          this._renderInvGrid();
        } else this.toast('버릴 칸을 먼저 선택하세요');
      });
      $('btn-close-furnace').addEventListener('click', () => this.closeAll());
      $('btn-close-chest').addEventListener('click', () => this.closeAll());
    }

    _tab(which) {
      $('tab-inv').classList.toggle('on', which === 'inv');
      $('tab-craft').classList.toggle('on', which === 'craft');
      $('invpane').style.display = which === 'inv' ? 'block' : 'none';
      $('craftpane').style.display = which === 'craft' ? 'block' : 'none';
      if (which === 'craft') this._renderCraft();
      else this._renderInvGrid();
    }

    // =============== 인벤토리 ===============
    openInventory() {
      this.open('invoverlay');
      this._tab('inv');
    }

    _slotEl(stack, selected) {
      const el = document.createElement('div');
      el.className = 'gslot' + (selected ? ' sel' : '');
      if (stack) {
        const it = BLK.ITEMS[stack.id];
        el.innerHTML =
          '<div class="swatch" style="background:' +
          cssCol(it ? it.col : [1, 0, 1]) + '"></div>' +
          '<div class="cnt">' + (stack.cnt > 1 ? stack.cnt : '') + '</div>';
        el.title = it ? it.disp : stack.id;
      }
      return el;
    }

    _renderInvGrid() {
      const grid = $('invgrid');
      grid.innerHTML = '';
      const p = this.game.player;
      // 메인(9~35) 먼저, 핫바(0~8) 마지막 줄
      const order = [];
      for (let i = 9; i < 36; i++) order.push(i);
      for (let i = 0; i < 9; i++) order.push(i);
      for (const idx of order) {
        const el = this._slotEl(p.slots[idx], idx === this.invSel);
        if (idx < 9) el.style.borderColor = '#5a6377';
        el.addEventListener('click', () => this._invTap(idx));
        grid.appendChild(el);
      }
    }

    _invTap(idx) {
      const p = this.game.player;
      if (this.invSel < 0) {
        if (p.slots[idx]) this.invSel = idx;
      } else if (this.invSel === idx) {
        this.invSel = -1;
      } else {
        const a = p.slots[this.invSel], b = p.slots[idx];
        if (b && a && b.id === a.id &&
            a.dur === undefined && b.dur === undefined) {
          const max = BLK.ITEMS[a.id].stack;
          const take = Math.min(max - b.cnt, a.cnt);
          b.cnt += take; a.cnt -= take;
          if (a.cnt <= 0) p.slots[this.invSel] = null;
        } else {
          p.slots[idx] = a;
          p.slots[this.invSel] = b;
        }
        this.invSel = -1;
      }
      this._renderInvGrid();
    }

    // =============== 제작 ===============
    _renderCraft() {
      const list = $('craftlist');
      list.innerHTML = '';
      const p = this.game.player;
      const nearWb = this.game.nearBlock(BLK.ID.WORKBENCH, 4);
      for (const r of BLK.RECIPES) {
        const it = BLK.ITEMS[r.out];
        const have = Object.entries(r.need).every(
          ([id, n]) => countItem(p.slots, id) >= n);
        const wbOk = !r.wb || nearWb || p.mode === 'creative';
        const ok = (have || p.mode === 'creative') && wbOk;

        const div = document.createElement('div');
        div.className = 'recipe' + (ok ? '' : ' no');
        const needTxt = Object.entries(r.need).map(([id, n]) => {
          const own = countItem(p.slots, id);
          return BLK.ITEMS[id].disp + ' ' + own + '/' + n;
        }).join(' · ');
        div.innerHTML =
          '<div class="ricon" style="background:' + cssCol(it.col) +
          '"></div><div class="rtxt"><b>' + it.disp +
          (r.n > 1 ? ' ×' + r.n : '') + '</b>' +
          (r.wb ? ' <span style="opacity:.6">(작업대 필요)</span>' : '') +
          '<br>' + needTxt + '</div>';
        const btn = document.createElement('button');
        btn.className = 'rbtn';
        btn.textContent = '제작';
        btn.disabled = !ok;
        btn.addEventListener('click', () => {
          if (p.mode !== 'creative') {
            for (const [id, n] of Object.entries(r.need)) {
              removeItem(p.slots, id, n);
            }
          }
          const left = addItem(p.slots, r.out, r.n);
          if (left > 0) {
            this.game.drops.spawn(r.out, left,
              [p.pos[0], p.pos[1] + 1, p.pos[2]]);
          }
          this.toast(it.disp + ' 제작 완료');
          this._renderCraft();
        });
        div.appendChild(btn);
        list.appendChild(div);
      }
    }

    // =============== 화로 ===============
    openFurnace(state) {
      this.furnaceState = state;
      this.open('furnaceoverlay');
      this._renderFurnace(true);
    }

    _renderFurnace(rebuild) {
      const st = this.furnaceState, p = this.game.player;
      const status = $('furnacestatus');
      let txt = '연료: ' + st.burn.toFixed(0) + '초  ·  대기 재료: ' +
                st.queue.length + '개';
      if (st.queue.length && st.burn > 0) {
        txt += '  ·  진행 ' +
               Math.round(st.progress / SMELT_TIME * 100) + '%';
      } else if (st.queue.length) {
        txt += '  ·  연료 필요!';
      }
      status.textContent = txt;

      if (!rebuild && this._furnaceListBuilt) return;
      this._furnaceListBuilt = true;
      const list = $('smeltlist');
      list.innerHTML = '';

      // 결과물 회수
      for (const id in st.out) {
        if (st.out[id] <= 0) continue;
        const it = BLK.ITEMS[id];
        const div = document.createElement('div');
        div.className = 'recipe';
        div.innerHTML = '<div class="ricon" style="background:' +
          cssCol(it.col) + '"></div><div class="rtxt"><b>' + it.disp +
          ' ×' + st.out[id] + '</b><br>제련 완료</div>';
        const btn = document.createElement('button');
        btn.className = 'rbtn';
        btn.textContent = '가져가기';
        btn.addEventListener('click', () => {
          const left = addItem(p.slots, id, st.out[id]);
          st.out[id] = left;
          if (left > 0) this.toast('인벤토리가 가득 찼습니다');
          this._renderFurnace(true);
        });
        div.appendChild(btn);
        list.appendChild(div);
      }

      // 재료 넣기 (제련 가능한 소지 아이템)
      for (let i = 0; i < 36; i++) {
        const s = p.slots[i];
        if (!s) continue;
        const it = BLK.ITEMS[s.id];
        if (!it || !it.smelt || this._listed(list, 'in-' + s.id)) continue;
        const out = BLK.ITEMS[it.smelt];
        const div = document.createElement('div');
        div.className = 'recipe';
        div.dataset.key = 'in-' + s.id;
        div.innerHTML = '<div class="ricon" style="background:' +
          cssCol(it.col) + '"></div><div class="rtxt"><b>' + it.disp +
          ' → ' + out.disp + '</b><br>보유 ' +
          countItem(p.slots, s.id) + '개</div>';
        const btn = document.createElement('button');
        btn.className = 'rbtn';
        btn.textContent = '넣기';
        btn.addEventListener('click', () => {
          if (removeItem(p.slots, s.id, 1)) {
            st.queue.push(it.smelt);
            this._renderFurnace(true);
          }
        });
        div.appendChild(btn);
        list.appendChild(div);
      }

      // 연료 넣기
      for (let i = 0; i < 36; i++) {
        const s = p.slots[i];
        if (!s) continue;
        const it = BLK.ITEMS[s.id];
        if (!it || !it.fuel || this._listed(list, 'fu-' + s.id)) continue;
        const div = document.createElement('div');
        div.className = 'recipe';
        div.dataset.key = 'fu-' + s.id;
        div.innerHTML = '<div class="ricon" style="background:' +
          cssCol(it.col) + '"></div><div class="rtxt"><b>연료: ' + it.disp +
          '</b><br>+' + (it.fuel * SMELT_TIME).toFixed(0) + '초 · 보유 ' +
          countItem(p.slots, s.id) + '개</div>';
        const btn = document.createElement('button');
        btn.className = 'rbtn';
        btn.textContent = '넣기';
        btn.addEventListener('click', () => {
          if (removeItem(p.slots, s.id, 1)) {
            st.burn += it.fuel * SMELT_TIME;
            this._renderFurnace(true);
          }
        });
        div.appendChild(btn);
        list.appendChild(div);
      }
      if (!list.children.length) {
        list.innerHTML = '<div class="hint">제련할 재료나 연료가 없습니다.' +
          ' (모래→유리, 철 원석→철괴, 생고기→익힌 고기 ...)</div>';
      }
    }
    _listed(list, key) {
      for (const c of list.children) if (c.dataset.key === key) return true;
      return false;
    }

    // =============== 상자 ===============
    openChest(state) {
      this.chestState = state;
      this.open('chestoverlay');
      this._renderChest();
    }
    _renderChest() {
      const st = this.chestState, p = this.game.player;
      const cg = $('chestgrid');
      cg.innerHTML = '';
      for (let i = 0; i < 27; i++) {
        const el = this._slotEl(st.slots[i], false);
        el.addEventListener('click', () => {
          const s = st.slots[i];
          if (!s) return;
          const left = s.dur !== undefined
            ? (p.slots.includes(null)
               ? (p.slots[p.slots.indexOf(null)] = s, 0) : s.cnt)
            : addItem(p.slots, s.id, s.cnt);
          if (left === 0) st.slots[i] = null;
          else s.cnt = left;
          this._renderChest();
        });
        cg.appendChild(el);
      }
      const ig = $('chestinvgrid');
      ig.innerHTML = '';
      for (let i = 0; i < 36; i++) {
        const el = this._slotEl(p.slots[i], false);
        el.addEventListener('click', () => {
          const s = p.slots[i];
          if (!s) return;
          for (let j = 0; j < 27; j++) {
            const c = st.slots[j];
            if (c && c.id === s.id && s.dur === undefined &&
                c.dur === undefined) {
              const max = BLK.ITEMS[s.id].stack;
              const take = Math.min(max - c.cnt, s.cnt);
              c.cnt += take; s.cnt -= take;
              if (s.cnt <= 0) { p.slots[i] = null; break; }
            }
          }
          if (p.slots[i]) {
            for (let j = 0; j < 27; j++) {
              if (!st.slots[j]) { st.slots[j] = p.slots[i]; p.slots[i] = null; break; }
            }
          }
          this._renderChest();
        });
        ig.appendChild(el);
      }
    }

    openPause() { this.open('pause'); }
    showDeath() { this.open('deathoverlay'); }

    // =============== 터치 컨트롤 ===============
    _setupTouch() {
      $('joystick').style.display = 'block';
      $('tbtns').style.display = 'flex';
      const p = this.game.player;

      // 조이스틱
      const joy = $('joystick'), knob = $('knob');
      let joyId = null;
      const joyCenter = () => {
        const r = joy.getBoundingClientRect();
        return [r.left + r.width / 2, r.top + r.height / 2];
      };
      joy.addEventListener('pointerdown', (e) => {
        joyId = e.pointerId;
        try { joy.setPointerCapture(e.pointerId); } catch (err) {}
        e.preventDefault();
      });
      joy.addEventListener('pointermove', (e) => {
        if (e.pointerId !== joyId) return;
        const [cx, cy] = joyCenter();
        let dx = e.clientX - cx, dy = e.clientY - cy;
        const d = Math.hypot(dx, dy), max = 45;
        if (d > max) { dx = dx / d * max; dy = dy / d * max; }
        knob.style.transform =
          `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
        p.input.mx = dx / max;
        p.input.mz = -dy / max;
        p.input.sprint = d > max * 0.92;   // 끝까지 밀면 달리기
      });
      const joyEnd = (e) => {
        if (e.pointerId !== joyId) return;
        joyId = null;
        knob.style.transform = 'translate(-50%,-50%)';
        p.input.mx = 0; p.input.mz = 0; p.input.sprint = false;
      };
      joy.addEventListener('pointerup', joyEnd);
      joy.addEventListener('pointercancel', joyEnd);

      // 시점 드래그 (캔버스)
      const canvas = $('glcanvas');
      let lookId = null, lastX = 0, lastY = 0;
      canvas.addEventListener('pointerdown', (e) => {
        if (e.pointerType === 'mouse') return;
        if (lookId !== null) return;
        lookId = e.pointerId;
        lastX = e.clientX; lastY = e.clientY;
      });
      canvas.addEventListener('pointermove', (e) => {
        if (e.pointerId !== lookId || this.isOpen()) return;
        p.yaw += (e.clientX - lastX) * 0.35;
        p.pitch = U.clamp(p.pitch + (e.clientY - lastY) * 0.35, -89, 89);
        lastX = e.clientX; lastY = e.clientY;
      });
      const lookEnd = (e) => { if (e.pointerId === lookId) lookId = null; };
      canvas.addEventListener('pointerup', lookEnd);
      canvas.addEventListener('pointercancel', lookEnd);

      // 동작 버튼
      const hold = (id, on, off) => {
        const el = $(id);
        el.addEventListener('pointerdown', (e) => {
          e.preventDefault(); e.stopPropagation();
          try { el.setPointerCapture(e.pointerId); } catch (err) {}
          el.classList.add('on'); on();
        });
        const end = () => { el.classList.remove('on'); if (off) off(); };
        el.addEventListener('pointerup', end);
        el.addEventListener('pointercancel', end);
      };
      hold('btn-break', () => { p.input.breaking = true; },
           () => { p.input.breaking = false; });
      hold('btn-jump', () => { p.input.jump = true; },
           () => { p.input.jump = false; });
      hold('btn-down', () => { p.input.down = true; },
           () => { p.input.down = false; });
      $('btn-use').addEventListener('pointerdown', (e) => {
        e.preventDefault(); e.stopPropagation();
        this.game.useAction();
      });
    }

    setCreativeButtons(creative) {
      $('btn-down').style.display = creative && IS_TOUCH ? 'flex' : 'none';
    }
  }

  function cssCol(c) {
    return 'rgb(' + Math.round(c[0] * 255) + ',' + Math.round(c[1] * 255) +
           ',' + Math.round(c[2] * 255) + ')';
  }

  window.UIManager = UIManager;
  window.IS_TOUCH = IS_TOUCH;
  window.SMELT_TIME = SMELT_TIME;
})();
