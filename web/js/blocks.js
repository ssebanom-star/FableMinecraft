/* blocks.js - 블록/아이템/레시피 데이터 (전역 BLK) */
(function () {
  'use strict';

  // ---------------------------------------------------------------
  // 블록 (id 순서 고정 - 저장 호환)
  // ---------------------------------------------------------------
  const B = [];
  let _id = 0;
  function reg(name, disp, col, opt) {
    opt = opt || {};
    B.push({
      id: _id, name, disp, col,
      top: opt.top || col, bottom: opt.bottom || col,
      hard: opt.hard !== undefined ? opt.hard : 1,     // -1 = 파괴불가
      solid: opt.solid !== undefined ? opt.solid : true,
      transp: !!opt.transp, liquid: !!opt.liquid, cross: !!opt.cross,
      light: opt.light || 0, damage: opt.damage || 0,
      tool: opt.tool || null, toolLvl: opt.toolLvl || 0,
      drops: opt.drops !== undefined ? opt.drops : [[name, 1, 1]],
      place: opt.place !== undefined ? opt.place : true,
      bounce: opt.bounce || 0,
    });
    return _id++;
  }

  const AIR = reg('air', '공기', [0, 0, 0],
    { hard: 0, solid: false, transp: true, drops: [], place: false });
  const GRASS = reg('grass', '잔디 흙', [.42, .32, .20],
    { top: [.36, .62, .26], hard: .6, tool: 'shovel',
      drops: [['dirt', 1, 1]] });
  const DIRT = reg('dirt', '흙', [.42, .30, .19], { hard: .5, tool: 'shovel' });
  const STONE = reg('stone', '돌', [.52, .52, .54],
    { hard: 1.5, tool: 'pickaxe', drops: [['cobble', 1, 1]] });
  const SAND = reg('sand', '모래', [.86, .80, .58], { hard: .5, tool: 'shovel' });
  const GRAVEL = reg('gravel', '자갈', [.55, .52, .50],
    { hard: .6, tool: 'shovel' });
  const SNOW = reg('snow', '눈', [.94, .95, .97], { hard: .3, tool: 'shovel' });
  const ICE = reg('ice', '얼음', [.62, .78, .95],
    { hard: .5, transp: true, tool: 'pickaxe', drops: [] });
  const WATER = reg('water', '물', [.18, .38, .75],
    { hard: -1, solid: false, transp: true, liquid: true, drops: [],
      place: false });
  const OAK_LOG = reg('oak_log', '참나무 원목', [.42, .31, .17],
    { top: [.62, .50, .31], hard: 2, tool: 'axe' });
  const OAK_LEAVES = reg('oak_leaves', '참나무 잎', [.22, .48, .16],
    { hard: .2, transp: true,
      drops: [['apple', 1, .08], ['stick', 1, .12]] });
  const BIRCH_LOG = reg('birch_log', '자작나무 원목', [.82, .80, .72],
    { top: [.75, .70, .55], hard: 2, tool: 'axe' });
  const BIRCH_LEAVES = reg('birch_leaves', '자작나무 잎', [.42, .62, .28],
    { hard: .2, transp: true, drops: [['stick', 1, .12]] });
  const SPRUCE_LOG = reg('spruce_log', '가문비 원목', [.30, .22, .12],
    { hard: 2, tool: 'axe' });
  const SPRUCE_LEAVES = reg('spruce_leaves', '가문비 잎', [.16, .36, .20],
    { hard: .2, transp: true, drops: [['stick', 1, .12]] });
  const CACTUS = reg('cactus', '선인장', [.20, .52, .22],
    { hard: .4, damage: 1 });
  const TALLGRASS = reg('tallgrass', '풀', [.32, .60, .22],
    { hard: 0, solid: false, transp: true, cross: true,
      drops: [['seeds', 1, .3]] });
  const FLOWER_R = reg('flower_r', '붉은 꽃', [.85, .20, .22],
    { hard: 0, solid: false, transp: true, cross: true });
  const FLOWER_Y = reg('flower_y', '노란 꽃', [.92, .83, .20],
    { hard: 0, solid: false, transp: true, cross: true });
  const MUSHROOM = reg('mushroom', '버섯', [.72, .45, .35],
    { hard: 0, solid: false, transp: true, cross: true });
  const COAL_ORE = reg('coal_ore', '석탄 광석', [.34, .34, .35],
    { hard: 3, tool: 'pickaxe', toolLvl: 1, drops: [['coal', 1, 1]] });
  const IRON_ORE = reg('iron_ore', '철 광석', [.58, .50, .45],
    { hard: 3.5, tool: 'pickaxe', toolLvl: 1, drops: [['raw_iron', 1, 1]] });
  const GOLD_ORE = reg('gold_ore', '금 광석', [.62, .56, .32],
    { hard: 3.5, tool: 'pickaxe', toolLvl: 2, drops: [['raw_gold', 1, 1]] });
  const CRYSTAL_ORE = reg('crystal_ore', '수정 광석', [.48, .40, .62],
    { hard: 4, tool: 'pickaxe', toolLvl: 2, light: 5,
      drops: [['crystal', 1, 1]] });
  const PLANKS = reg('planks', '나무 판자', [.66, .53, .33],
    { hard: 1.5, tool: 'axe' });
  const COBBLE = reg('cobble', '조약돌', [.44, .44, .46],
    { hard: 2, tool: 'pickaxe' });
  const STONE_BRICKS = reg('stone_bricks', '돌벽돌', [.48, .48, .51],
    { hard: 2, tool: 'pickaxe' });
  const GLASS = reg('glass', '유리', [.75, .85, .90],
    { hard: .3, transp: true, drops: [] });
  const TORCH = reg('torch', '횃불', [.95, .75, .30],
    { hard: 0, solid: false, transp: true, cross: true, light: 14 });
  const WORKBENCH = reg('workbench', '작업대', [.55, .40, .22],
    { top: [.68, .55, .34], hard: 1.5, tool: 'axe' });
  const FURNACE = reg('furnace', '화로', [.40, .40, .42],
    { top: [.35, .35, .37], hard: 2.5, tool: 'pickaxe' });
  const CHEST = reg('chest', '상자', [.60, .45, .22],
    { top: [.70, .55, .30], hard: 1.5, tool: 'axe' });
  const GLOWSTONE = reg('glowstone', '발광 블록', [.95, .85, .45],
    { hard: .5, light: 15 });
  const BOOM = reg('boom', '폭발 블록', [.75, .25, .20],
    { top: [.85, .70, .30], hard: .2 });
  const SLIME = reg('slime', '탄성 블록', [.45, .78, .40],
    { hard: .3, transp: true, bounce: .8 });
  const SANDSTONE = reg('sandstone', '사암', [.80, .74, .52],
    { hard: 1.8, tool: 'pickaxe' });
  const MUD = reg('mud', '진흙', [.30, .24, .18], { hard: .5, tool: 'shovel' });
  const BEDROCK = reg('bedrock', '기반암', [.20, .20, .22],
    { hard: -1, drops: [], place: false });
  const DEADBUSH = reg('deadbush', '마른 덤불', [.55, .42, .25],
    { hard: 0, solid: false, transp: true, cross: true,
      drops: [['stick', 2, .7]] });

  const ID = { AIR, GRASS, DIRT, STONE, SAND, GRAVEL, SNOW, ICE, WATER,
    OAK_LOG, OAK_LEAVES, BIRCH_LOG, BIRCH_LEAVES, SPRUCE_LOG, SPRUCE_LEAVES,
    CACTUS, TALLGRASS, FLOWER_R, FLOWER_Y, MUSHROOM, COAL_ORE, IRON_ORE,
    GOLD_ORE, CRYSTAL_ORE, PLANKS, COBBLE, STONE_BRICKS, GLASS, TORCH,
    WORKBENCH, FURNACE, CHEST, GLOWSTONE, BOOM, SLIME, SANDSTONE, MUD,
    BEDROCK, DEADBUSH };

  // 불투명(면 컬링 기준): solid && !transp && !cross
  const OPAQUE = B.map(b => b.solid && !b.transp && !b.cross);
  // 반투명 메시로 렌더링
  const ALPHA = B.map(b => b.liquid || b.name === 'glass' || b.name === 'ice');

  // ---------------------------------------------------------------
  // 아이템
  // ---------------------------------------------------------------
  const ITEMS = {};
  function item(id, disp, opt) {
    opt = opt || {};
    ITEMS[id] = {
      id, disp, col: opt.col || [.8, .8, .8],
      stack: opt.stack || 64, place: opt.place !== undefined ? opt.place : null,
      tool: opt.tool || null, toolLvl: opt.toolLvl || 0,
      speed: opt.speed || 1, dmg: opt.dmg || 1, dur: opt.dur || 0,
      food: opt.food || 0, heal: opt.heal || 0,
      fuel: opt.fuel || 0, smelt: opt.smelt || null,
      desc: opt.desc || '',
    };
  }

  // 블록 아이템 자동 등록
  for (const b of B) {
    if (b.name === 'air' || !b.place) continue;
    item(b.name, b.disp, { col: b.top, place: b.id });
  }
  ITEMS.oak_log.fuel = 3; ITEMS.birch_log.fuel = 3;
  ITEMS.spruce_log.fuel = 3; ITEMS.planks.fuel = 1.5;
  ITEMS.sand.smelt = 'glass'; ITEMS.cobble.smelt = 'stone';

  // 자원
  item('stick', '막대기', { col: [.55, .42, .24], fuel: .5 });
  item('coal', '석탄', { col: [.15, .15, .15], fuel: 8 });
  item('raw_iron', '철 원석', { col: [.78, .68, .60], smelt: 'iron_ingot' });
  item('raw_gold', '금 원석', { col: [.88, .75, .35], smelt: 'gold_ingot' });
  item('iron_ingot', '철괴', { col: [.85, .85, .88] });
  item('gold_ingot', '금괴', { col: [.95, .82, .30] });
  item('crystal', '수정', { col: [.70, .58, .92] });
  item('seeds', '씨앗', { col: [.50, .70, .30] });
  item('leather', '가죽', { col: [.60, .40, .22] });
  item('string', '실', { col: [.90, .90, .90] });
  item('bone', '뼈', { col: [.92, .90, .82] });
  item('gunpowder', '화약', { col: [.45, .45, .45] });
  item('feather', '깃털', { col: [.95, .95, .95] });

  // 도구/무기: [등급, 속도, 내구, 공격]
  const TIERS = { wood: [1, 2, 60, 0, [.62, .48, .28]],
                  stone: [2, 4, 132, 1, [.55, .55, .57]],
                  iron: [3, 6, 250, 2, [.85, .85, .88]],
                  crystal: [4, 9, 1024, 3, [.70, .58, .92]] };
  const TIER_KO = { wood: '나무', stone: '돌', iron: '철', crystal: '수정' };
  const KINDS = { pickaxe: ['곡괭이', 2], axe: ['도끼', 4], shovel: ['삽', 1] };
  for (const t in TIERS) {
    const [lvl, spd, dur, bonus, col] = TIERS[t];
    for (const k in KINDS) {
      if (t === 'crystal' && k !== 'pickaxe') continue;
      item(t + '_' + k, TIER_KO[t] + ' ' + KINDS[k][0],
        { col, stack: 1, tool: k, toolLvl: lvl, speed: spd,
          dmg: KINDS[k][1] + bonus, dur });
    }
    item(t + '_sword', TIER_KO[t] + ' 검',
      { col, stack: 1, dmg: 4 + lvl, dur });
  }

  // 음식
  item('apple', '사과', { col: [.85, .2, .2], food: 4 });
  item('raw_meat', '생고기', { col: [.8, .35, .35], food: 3,
    smelt: 'cooked_meat' });
  item('cooked_meat', '익힌 고기', { col: [.6, .35, .2], food: 8, heal: 2 });
  item('raw_chicken', '생 닭고기', { col: [.9, .75, .7], food: 2,
    smelt: 'cooked_chicken' });
  item('cooked_chicken', '익힌 닭고기', { col: [.75, .55, .35], food: 6,
    heal: 1 });

  // ---------------------------------------------------------------
  // 제작 레시피 (목록형 UI - 재료 dict 기반)
  // ---------------------------------------------------------------
  const RECIPES = [
    { id: 'planks', need: { oak_log: 1 }, out: 'planks', n: 4 },
    { id: 'planks_b', need: { birch_log: 1 }, out: 'planks', n: 4 },
    { id: 'planks_s', need: { spruce_log: 1 }, out: 'planks', n: 4 },
    { id: 'stick', need: { planks: 2 }, out: 'stick', n: 4 },
    { id: 'workbench', need: { planks: 4 }, out: 'workbench', n: 1 },
    { id: 'torch', need: { coal: 1, stick: 1 }, out: 'torch', n: 4 },
    { id: 'furnace', need: { cobble: 8 }, out: 'furnace', n: 1, wb: true },
    { id: 'chest', need: { planks: 8 }, out: 'chest', n: 1, wb: true },
    { id: 'stone_bricks', need: { stone: 4 }, out: 'stone_bricks', n: 4 },
    { id: 'sandstone', need: { sand: 4 }, out: 'sandstone', n: 1 },
    { id: 'glowstone', need: { crystal: 1, coal: 2 }, out: 'glowstone',
      n: 1, wb: true },
    { id: 'boom', need: { gunpowder: 4, sand: 1 }, out: 'boom', n: 1,
      wb: true },
    { id: 'wood_pickaxe', need: { planks: 3, stick: 2 },
      out: 'wood_pickaxe', n: 1, wb: true },
    { id: 'wood_axe', need: { planks: 3, stick: 2 }, out: 'wood_axe',
      n: 1, wb: true },
    { id: 'wood_shovel', need: { planks: 1, stick: 2 }, out: 'wood_shovel',
      n: 1, wb: true },
    { id: 'wood_sword', need: { planks: 2, stick: 1 }, out: 'wood_sword',
      n: 1, wb: true },
    { id: 'stone_pickaxe', need: { cobble: 3, stick: 2 },
      out: 'stone_pickaxe', n: 1, wb: true },
    { id: 'stone_axe', need: { cobble: 3, stick: 2 }, out: 'stone_axe',
      n: 1, wb: true },
    { id: 'stone_shovel', need: { cobble: 1, stick: 2 },
      out: 'stone_shovel', n: 1, wb: true },
    { id: 'stone_sword', need: { cobble: 2, stick: 1 }, out: 'stone_sword',
      n: 1, wb: true },
    { id: 'iron_pickaxe', need: { iron_ingot: 3, stick: 2 },
      out: 'iron_pickaxe', n: 1, wb: true },
    { id: 'iron_axe', need: { iron_ingot: 3, stick: 2 }, out: 'iron_axe',
      n: 1, wb: true },
    { id: 'iron_shovel', need: { iron_ingot: 1, stick: 2 },
      out: 'iron_shovel', n: 1, wb: true },
    { id: 'iron_sword', need: { iron_ingot: 2, stick: 1 },
      out: 'iron_sword', n: 1, wb: true },
    { id: 'crystal_pickaxe', need: { crystal: 3, stick: 2 },
      out: 'crystal_pickaxe', n: 1, wb: true },
    { id: 'crystal_sword', need: { crystal: 2, stick: 1 },
      out: 'crystal_sword', n: 1, wb: true },
  ];

  window.BLK = { B, ID, OPAQUE, ALPHA, ITEMS, RECIPES };
})();
