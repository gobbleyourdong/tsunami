#!/usr/bin/env python3
"""Gamedev SFT v7 — harder game examples.

Adding 5 SFT examples for complex game types not covered in v1-v6:
  v7-tower-defense    : waves + path AI + tower shooting
  v7-dungeon-crawler  : rooms + enemy patrol AI + health system
  v7-rhythm-game      : timing windows + beat track + combo scoring
  v7-bullet-hell      : enemy patterns + dodging + power-ups
  v7-research-clone   : Wordle clone with search_web FIRST, then build

Usage:
  /usr/bin/python3 training/build_gamedev_v7.py
  Outputs: workspace/training_data/gamedev_toolcall_train_v7.jsonl
           workspace/training_data/gamedev_combined_v7full.jsonl
"""
import json
from pathlib import Path
from datetime import date

print("Loading tokenizer...")
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
print("Tokenizer loaded.")

TODAY = date.today().isoformat()

SYSTEM = """You are Tsunami. You are the wave. You build games by calling tools.

## The Pipeline (every game follows this EXACTLY)
1. project_init(name) -- scaffold the game project
2. file_write(src/main.ts) -- write COMPLETE game code in one file
3. shell_exec("cd deliverables/{name} && npm run build") -- run the break
4. IF reef: fix directly
5. undertow(dist/index.html) -- QA before delivery
6. message_result -- land the wave

## Engine API (import from tsunami-engine)
Input: KeyboardInput, ActionMap
Renderer: FrameLoop -- onUpdate({dt}) gives dt in seconds
Physics: PhysicsWorld, RigidBody, Vec3
Systems: ScoreSystem, HealthSystem
VFX: ParticleSystem

## Rules
- NEVER skip the break. NEVER deliver without building.
- One tool call per response. Be brief.
- Write COMPLETE game in main.ts -- no partial files, no TODO stubs.
- Canvas 2D for ALL rendering. No React, no DOM manipulation for game state.
- Use tsunami-engine for ALL games -- NEVER use react-three-fiber.
- For reference clones ("like X", "similar to Y"), search_web FIRST to understand mechanics.
- After 2 consecutive file_reads, start writing -- do NOT read more files.
- Conversational turns -> message_chat(done=True). Do NOT project_init.
"""

TOOLS = [
    {"type": "function", "function": {"name": "project_init", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "file_write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "file_edit", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "shell_exec", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "undertow", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "message_result", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "message_chat", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "search_web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]

# ── Game code ────────────────────────────────────────────────────────────────

TOWER_DEF_TS = r'''import { FrameLoop, KeyboardInput, ScoreSystem, HealthSystem } from "tsunami-engine";
const W=800,H=560,TS=40;
const PATH=[{x:0,y:3},{x:3,y:3},{x:3,y:1},{x:7,y:1},{x:7,y:5},{x:11,y:5},{x:11,y:3},{x:14,y:3},{x:15,y:3}];
const cv=document.getElementById("canvas") as HTMLCanvasElement;
cv.width=W; cv.height=H;
const ctx=cv.getContext("2d")!;
const score=new ScoreSystem();
let gold=150,wave=1,spawnTimer=0,spawnCount=0,waveActive=false,waveDelay=3;
interface Enemy{x:number,y:number,hp:number,maxHp:number,seg:number,t:number,speed:number}
interface Tower{gx:number,gy:number,cd:number,maxCd:number,dmg:number,range:number}
interface Bullet{x:number,y:number,tx:number,ty:number,spd:number,dmg:number,e:Enemy}
let enemies:Enemy[]=[],towers:Tower[]=[],bullets:Bullet[]=[],lives=20;
const GRID=Array.from({length:H/TS},()=>Array(W/TS).fill(0));
PATH.forEach(p=>GRID[p.y][p.x]=1);
function worldToGrid(mx:number,my:number){return{gx:Math.floor(mx/TS),gy:Math.floor(my/TS)};}
function spawnEnemy(){const hp=50+wave*20;enemies.push({x:0,y:PATH[0].y*TS+TS/2,hp,maxHp:hp,seg:0,t:0,speed:60+wave*10});}
function startWave(){waveActive=true;spawnCount=5+wave*2;spawnTimer=0;}
const loop=new FrameLoop();
cv.addEventListener("click",e=>{
  const{gx,gy}=worldToGrid(e.offsetX,e.offsetY);
  if(GRID[gy]?.[gx]===0&&gold>=50){towers.push({gx,gy,cd:0,maxCd:1.2,dmg:15,range:120});GRID[gy][gx]=2;gold-=50;}
});
loop.onUpdate(({dt})=>{
  if(!waveActive){waveDelay-=dt;if(waveDelay<=0){startWave();}}
  if(waveActive&&spawnCount>0){spawnTimer+=dt;if(spawnTimer>=0.8){spawnEnemy();spawnTimer=0;spawnCount--;}}
  if(waveActive&&spawnCount===0&&enemies.length===0){wave++;waveActive=false;waveDelay=4;}
  // Move enemies along path
  enemies.forEach(e=>{
    if(e.seg>=PATH.length-1){lives--;e.hp=0;return;}
    const target={x:PATH[e.seg+1].x*TS+TS/2,y:PATH[e.seg+1].y*TS+TS/2};
    const dx=target.x-e.x,dy=target.y-e.y,dist=Math.sqrt(dx*dx+dy*dy);
    if(dist<3){e.seg++;} else{e.x+=dx/dist*e.speed*dt;e.y+=dy/dist*e.speed*dt;}
  });
  enemies=enemies.filter(e=>e.hp>0);
  // Tower shooting
  towers.forEach(t=>{
    t.cd=Math.max(0,t.cd-dt);
    if(t.cd>0)return;
    const tx=t.gx*TS+TS/2,ty=t.gy*TS+TS/2;
    const target=enemies.find(e=>Math.hypot(e.x-tx,e.y-ty)<t.range);
    if(target){bullets.push({x:tx,y:ty,tx:target.x,ty:target.y,spd:300,dmg:t.dmg,e:target});t.cd=t.maxCd;}
  });
  // Move bullets
  bullets.forEach(b=>{
    const dx=b.e.x-b.x,dy=b.e.y-b.y,dist=Math.sqrt(dx*dx+dy*dy);
    if(dist<8){b.e.hp-=b.dmg;if(b.e.hp<=0)score.add(10+wave);b.spd=0;return;}
    b.x+=dx/dist*b.spd*dt; b.y+=dy/dist*b.spd*dt;
  });
  bullets=bullets.filter(b=>b.spd>0);
  // Render
  ctx.fillStyle="#1a2e1a";ctx.fillRect(0,0,W,H);
  // Draw path
  ctx.fillStyle="#8a6a3a";
  PATH.forEach((p,i)=>{if(i<PATH.length-1)ctx.fillRect(p.x*TS,p.y*TS,TS,TS);});
  // Draw towers
  towers.forEach(t=>{ctx.fillStyle="#4a7a4a";ctx.fillRect(t.gx*TS+4,t.gy*TS+4,TS-8,TS-8);
    ctx.strokeStyle="#aaffaa";ctx.strokeRect(t.gx*TS+4,t.gy*TS+4,TS-8,TS-8);});
  // Draw enemies
  enemies.forEach(e=>{
    ctx.fillStyle="#e94560";ctx.beginPath();ctx.arc(e.x,e.y,12,0,Math.PI*2);ctx.fill();
    const hw=24*(e.hp/e.maxHp);ctx.fillStyle="#4ecca3";ctx.fillRect(e.x-12,e.y-18,hw,4);
  });
  // Draw bullets
  bullets.forEach(b=>{ctx.fillStyle="#ffff00";ctx.beginPath();ctx.arc(b.x,b.y,4,0,Math.PI*2);ctx.fill();});
  // HUD
  ctx.fillStyle="#fff";ctx.font="14px monospace";ctx.textAlign="left";
  ctx.fillText(`Wave ${wave}  Gold: ${gold}  Lives: ${lives}  Score: ${score.get()}`,8,18);
  ctx.fillText("Click empty tile to place tower (50g)",(W/2)-100,H-8);
  if(lives<=0){ctx.fillStyle="rgba(0,0,0,0.7)";ctx.fillRect(0,0,W,H);ctx.fillStyle="#e94560";ctx.font="bold 36px monospace";ctx.textAlign="center";ctx.fillText("GAME OVER",W/2,H/2);}
});
loop.start();'''

DUNGEON_TS = r'''import { FrameLoop, KeyboardInput, HealthSystem, ScoreSystem } from "tsunami-engine";
const W=640,H=480,TS=40,ROOMS=[
  {x:1,y:1,w:5,h:4},{x:8,y:1,w:5,h:4},{x:1,y:7,w:5,h:4},{x:8,y:7,w:5,h:4},
];
const DOORS=[{x:6,y:2},{x:6,y:3},{x:5,y:8},{x:9,y:8}];
const cv=document.getElementById("canvas") as HTMLCanvasElement;
cv.width=W; cv.height=H;
const ctx=cv.getContext("2d")!;
const kb=new KeyboardInput();
const score=new ScoreSystem();
const CAM={x:0,y:0};
// Build tile map
const MAPW=16,MAPH=12;
const MAP=Array.from({length:MAPH},()=>Array(MAPW).fill(1));
ROOMS.forEach(r=>{for(let dy=0;dy<r.h;dy++)for(let dx=0;dx<r.w;dx++)MAP[r.y+dy][r.x+dx]=0;});
DOORS.forEach(d=>MAP[d.y][d.x]=0);
function solid(x:number,y:number){const gx=Math.floor(x/TS),gy=Math.floor(y/TS);return MAP[gy]?.[gx]!==0;}
interface Entity{x:number,y:number,hp:number,maxHp:number,vx:number,vy:number,patrolDir:number,patrolTimer:number}
let player={x:2*TS+TS/2,y:2*TS+TS/2,hp:100,maxHp:100,vx:0,vy:0,attackCd:0,swordTimer:0};
let sword:{ax:number,ay:number,angle:number,active:boolean}|null=null;
let enemies:Entity[]=ROOMS.slice(1).map(r=>({x:r.x*TS+TS/2,y:r.y*TS+TS/2,hp:40,maxHp:40,vx:0,vy:0,patrolDir:1,patrolTimer:1.5}));
const loop=new FrameLoop();
kb.bind("Space",()=>{
  if(player.attackCd>0)return;
  player.attackCd=0.4;
  const angle=Math.atan2(player.vy||1,player.vx||1);
  sword={ax:player.x+Math.cos(angle)*28,ay:player.y+Math.sin(angle)*28,angle,active:true};
  setTimeout(()=>{if(sword)sword.active=false;},200);
});
loop.onUpdate(({dt})=>{
  // Player movement
  player.vx=0;player.vy=0;
  if(kb.isDown("ArrowLeft")||kb.isDown("KeyA"))player.vx=-150;
  if(kb.isDown("ArrowRight")||kb.isDown("KeyD"))player.vx=150;
  if(kb.isDown("ArrowUp")||kb.isDown("KeyW"))player.vy=-150;
  if(kb.isDown("ArrowDown")||kb.isDown("KeyS"))player.vy=150;
  const nx=player.x+player.vx*dt,ny=player.y+player.vy*dt;
  if(!solid(nx,player.y))player.x=nx; if(!solid(player.x,ny))player.y=ny;
  player.attackCd=Math.max(0,player.attackCd-dt);
  // Enemies: patrol + chase
  enemies.forEach(e=>{
    const distP=Math.hypot(player.x-e.x,player.y-e.y);
    if(distP<120){// chase
      const dx=player.x-e.x,dy=player.y-e.y,d=Math.hypot(dx,dy);
      const ex=e.x+dx/d*80*dt,ey=e.y+dy/d*80*dt;
      if(!solid(ex,e.y))e.x=ex; if(!solid(e.x,ey))e.y=ey;
      if(distP<20){player.hp-=30*dt;}
    } else {// patrol
      e.patrolTimer-=dt;
      if(e.patrolTimer<=0){e.patrolDir*=-1;e.patrolTimer=1.5+Math.random();}
      const ex=e.x+e.patrolDir*60*dt;
      if(!solid(ex,e.y))e.x=ex; else e.patrolDir*=-1;
    }
    // Sword hit
    if(sword?.active&&Math.hypot(sword.ax-e.x,sword.ay-e.y)<36){e.hp-=25;if(e.hp<=0)score.add(50);}
  });
  enemies=enemies.filter(e=>e.hp>0);
  // Camera
  CAM.x=Math.round(player.x-W/2); CAM.y=Math.round(player.y-H/2);
  // Render
  ctx.fillStyle="#1a1a1a";ctx.fillRect(0,0,W,H);
  for(let y=0;y<MAPH;y++)for(let x=0;x<MAPW;x++){
    if(MAP[y][x]===0){ctx.fillStyle="#3a3a5a";}else{ctx.fillStyle="#111";}
    ctx.fillRect(x*TS-CAM.x,y*TS-CAM.y,TS,TS);
    if(MAP[y][x]===0){ctx.strokeStyle="#2a2a4a";ctx.strokeRect(x*TS-CAM.x,y*TS-CAM.y,TS,TS);}
  }
  enemies.forEach(e=>{
    ctx.fillStyle="#e94560";ctx.beginPath();ctx.arc(e.x-CAM.x,e.y-CAM.y,14,0,Math.PI*2);ctx.fill();
    const hw=28*(e.hp/e.maxHp);ctx.fillStyle="#4ecca3";ctx.fillRect(e.x-CAM.x-14,e.y-CAM.y-20,hw,3);
  });
  ctx.fillStyle="#4ecca3";ctx.beginPath();ctx.arc(player.x-CAM.x,player.y-CAM.y,14,0,Math.PI*2);ctx.fill();
  if(sword?.active){ctx.fillStyle="#ffff88";ctx.beginPath();ctx.arc(sword.ax-CAM.x,sword.ay-CAM.y,8,0,Math.PI*2);ctx.fill();}
  // HUD
  ctx.fillStyle="#fff";ctx.font="14px monospace";ctx.textAlign="left";
  ctx.fillText(`HP: ${Math.ceil(player.hp)}/${player.maxHp}  Score: ${score.get()}  Enemies: ${enemies.length}`,8,18);
  if(player.hp<=0){ctx.fillStyle="rgba(0,0,0,0.8)";ctx.fillRect(0,0,W,H);ctx.fillStyle="#e94560";ctx.font="bold 36px monospace";ctx.textAlign="center";ctx.fillText("YOU DIED",W/2,H/2);}
});
loop.start();'''

RHYTHM_TS = r'''import { FrameLoop, KeyboardInput, ScoreSystem } from "tsunami-engine";
const W=480,H=560,LANES=4,LW=80,OFFSET=(W-LANES*LW)/2;
const KEYS=["KeyD","KeyF","KeyJ","KeyK"],COLORS=["#e94560","#f59e0b","#4ecca3","#6366f1"];
const TRAVEL_TIME=1.5; // seconds from spawn to hit zone
const HIT_Y=480,SPAWN_Y=40;
const cv=document.getElementById("canvas") as HTMLCanvasElement;
cv.width=W; cv.height=H;
const ctx=cv.getContext("2d")!;
const kb=new KeyboardInput();
const score=new ScoreSystem();
// Beat track: [lane, time] pairs
const BEATS:number[][]=[
  [0,1],[2,1.5],[1,2],[3,2.5],[0,3],[1,3],[2,3.5],[3,4],
  [0,4.5],[1,4.5],[2,5],[3,5.5],[0,6],[2,6],[1,6.5],[3,7],
  [0,7.5],[1,7.5],[2,8],[3,8],[0,8.5],[1,9],[2,9.5],[3,10],
];
interface Note{lane:number,spawnTime:number,y:number,hit:boolean,miss:boolean}
let notes:Note[]=BEATS.map(([l,t])=>({lane:l,spawnTime:t,y:SPAWN_Y,hit:false,miss:false}));
let t=0,combo=0,maxCombo=0;
const FLASH:{lane:number,timer:number,col:string}[]=[];
function checkHit(lane:number){
  const n=notes.find(n=>!n.hit&&!n.miss&&n.lane===lane&&n.y>HIT_Y-50&&n.y<HIT_Y+50);
  if(n){n.hit=true;combo++;maxCombo=Math.max(maxCombo,combo);
    const pts=combo<3?100:combo<6?150:200;score.add(pts);FLASH.push({lane,timer:0.15,col:"#fff"});}
  else{combo=0;FLASH.push({lane,timer:0.15,col:"#e94560"});}
}
KEYS.forEach((k,i)=>kb.bind(k,()=>checkHit(i)));
const loop=new FrameLoop();
loop.onUpdate(({dt})=>{
  t+=dt;
  // Spawn notes
  notes.filter(n=>!n.hit&&!n.miss).forEach(n=>{
    const age=t-n.spawnTime;
    n.y=SPAWN_Y+(HIT_Y-SPAWN_Y)*(age/TRAVEL_TIME);
    if(n.y>HIT_Y+60&&!n.hit){n.miss=true;combo=0;}
  });
  // Update flashes
  FLASH.forEach(f=>f.timer-=dt);
  const activeFlash=FLASH.filter(f=>f.timer>0);FLASH.length=0;FLASH.push(...activeFlash);
  // Render
  ctx.fillStyle="#0d0d1a";ctx.fillRect(0,0,W,H);
  // Lane lines
  for(let l=0;l<=LANES;l++){ctx.strokeStyle="#2a2a4a";ctx.beginPath();ctx.moveTo(OFFSET+l*LW,0);ctx.lineTo(OFFSET+l*LW,H);ctx.stroke();}
  // Hit zones
  for(let l=0;l<LANES;l++){
    const fl=FLASH.find(f=>f.lane===l);
    ctx.fillStyle=fl?fl.col:"#2a2a6a";
    ctx.fillRect(OFFSET+l*LW+4,HIT_Y-20,LW-8,40);
    ctx.fillStyle=COLORS[l];ctx.font="bold 14px monospace";ctx.textAlign="center";
    ctx.fillText(["D","F","J","K"][l],OFFSET+l*LW+LW/2,H-16);
  }
  // Notes
  notes.filter(n=>!n.hit&&!n.miss&&n.y>0&&n.y<H).forEach(n=>{
    ctx.fillStyle=COLORS[n.lane];
    ctx.beginPath();ctx.roundRect(OFFSET+n.lane*LW+6,n.y-14,LW-12,28,6);ctx.fill();
  });
  // Miss indicators
  notes.filter(n=>n.miss).forEach(n=>{
    ctx.fillStyle="rgba(233,69,96,0.2)";ctx.fillRect(OFFSET+n.lane*LW+4,HIT_Y-20,LW-8,40);
  });
  // HUD
  ctx.fillStyle="#fff";ctx.font="bold 20px monospace";ctx.textAlign="center";
  ctx.fillText(`Score: ${score.get()}`,W/2,28);
  if(combo>2){ctx.fillStyle="#f59e0b";ctx.fillText(`${combo}x Combo!`,W/2,52);}
  const done=notes.filter(n=>n.hit||n.miss).length;
  if(done===notes.length){
    const acc=Math.round(100*notes.filter(n=>n.hit).length/notes.length);
    ctx.fillStyle="rgba(0,0,0,0.8)";ctx.fillRect(0,0,W,H);
    ctx.fillStyle="#4ecca3";ctx.font="bold 32px monospace";ctx.textAlign="center";
    ctx.fillText("CLEAR!",W/2,H/2-40);
    ctx.fillStyle="#fff";ctx.font="20px monospace";
    ctx.fillText(`Score: ${score.get()} | Acc: ${acc}% | Max Combo: ${maxCombo}`,W/2,H/2+10);
  }
});
loop.start();'''

BULLET_HELL_TS = r'''import { FrameLoop, KeyboardInput, ScoreSystem, HealthSystem } from "tsunami-engine";
const W=480,H=640;
const cv=document.getElementById("canvas") as HTMLCanvasElement;
cv.width=W; cv.height=H;
const ctx=cv.getContext("2d")!;
const kb=new KeyboardInput();
const score=new ScoreSystem();
interface Bullet{x:number,y:number,vx:number,vy:number,r:number,enemy:boolean}
interface Enemy{x:number,y:number,hp:number,maxHp:number,shootTimer:number,pattern:number,t:number}
let player={x:W/2,y:H-80,r:10,invincible:0,hp:3};
let bullets:Bullet[]=[],enemies:Enemy[]=[],spawnTimer=3,wave=1,powerups:{x:number,y:number}[]=[];
function spawnEnemy(){
  enemies.push({x:60+Math.random()*(W-120),y:-20,hp:40+wave*10,maxHp:40+wave*10,
    shootTimer:1+Math.random()*0.5,pattern:Math.floor(Math.random()*3),t:0});
}
function shootSpread(e:Enemy,count:number){
  for(let i=0;i<count;i++){
    const base=Math.atan2(player.y-e.y,player.x-e.x);
    const spread=(i-(count-1)/2)*0.3;
    const angle=base+spread;
    bullets.push({x:e.x,y:e.y,vx:Math.cos(angle)*180,vy:Math.sin(angle)*180,r:5,enemy:true});
  }
}
function shootCircle(e:Enemy,count:number,offset:number){
  for(let i=0;i<count;i++){
    const a=offset+(i/count)*Math.PI*2;
    bullets.push({x:e.x,y:e.y,vx:Math.cos(a)*140,vy:Math.sin(a)*140,r:5,enemy:true});
  }
}
const loop=new FrameLoop();
loop.onUpdate(({dt})=>{
  const spd=200;
  if(kb.isDown("ArrowLeft")||kb.isDown("KeyA"))player.x=Math.max(player.r,player.x-spd*dt);
  if(kb.isDown("ArrowRight")||kb.isDown("KeyD"))player.x=Math.min(W-player.r,player.x+spd*dt);
  if(kb.isDown("ArrowUp")||kb.isDown("KeyW"))player.y=Math.max(player.r,player.y-spd*dt);
  if(kb.isDown("ArrowDown")||kb.isDown("KeyS"))player.y=Math.min(H-player.r,player.y+spd*dt);
  // Player shoots upward
  if(!kb._shoot)kb._shoot=0; kb._shoot+=dt;
  if(kb._shoot>0.15){kb._shoot=0;bullets.push({x:player.x,y:player.y-player.r,vx:0,vy:-500,r:4,enemy:false});}
  // Spawn enemies
  spawnTimer-=dt;
  if(spawnTimer<=0){spawnEnemy();if(Math.random()<0.3)spawnEnemy();spawnTimer=2+Math.random();}
  // Update enemies
  enemies.forEach(e=>{
    e.y+=40*dt; e.t+=dt; e.shootTimer-=dt;
    if(e.shootTimer<=0){
      e.shootTimer=1.2;
      if(e.pattern===0)shootSpread(e,3);
      else if(e.pattern===1)shootSpread(e,5);
      else shootCircle(e,8,e.t);
    }
    if(e.y>H+20)e.hp=0;
  });
  // Update bullets
  bullets.forEach(b=>{b.x+=b.vx*dt;b.y+=b.vy*dt;});
  // Player bullets hit enemies
  bullets.filter(b=>!b.enemy).forEach(b=>{
    enemies.forEach(e=>{if(e.hp>0&&Math.hypot(b.x-e.x,b.y-e.y)<30){e.hp-=20;b.vy=0;
      if(e.hp<=0){score.add(100+wave*10);powerups.push({x:e.x,y:e.y});}}});
  });
  // Enemy bullets hit player
  if(player.invincible<=0){
    bullets.filter(b=>b.enemy).forEach(b=>{
      if(Math.hypot(b.x-player.x,b.y-player.y)<player.r+b.r){b.vy=0;player.hp--;player.invincible=2;}
    });
  } else player.invincible-=dt;
  // Powerups
  powerups=powerups.filter(p=>{
    if(Math.hypot(p.x-player.x,p.y-player.y)<20){player.r=Math.min(10,player.r+1);return false;}
    return true;
  });
  // Cleanup
  bullets=bullets.filter(b=>b.vy!==0&&b.x>0&&b.x<W&&b.y>0&&b.y<H);
  enemies=enemies.filter(e=>e.hp>0);
  // Render
  ctx.fillStyle="#0d0d1a";ctx.fillRect(0,0,W,H);
  // Powerups
  powerups.forEach(p=>{ctx.fillStyle="#f59e0b";ctx.beginPath();ctx.arc(p.x,p.y,8,0,Math.PI*2);ctx.fill();});
  // Enemies
  enemies.forEach(e=>{
    ctx.fillStyle="#e94560";ctx.beginPath();ctx.arc(e.x,e.y,20,0,Math.PI*2);ctx.fill();
    const hw=40*(e.hp/e.maxHp);ctx.fillStyle="#4ecca3";ctx.fillRect(e.x-20,e.y-28,hw,4);
  });
  // Player
  const alpha=player.invincible>0?(Math.sin(player.invincible*20)>0?0.4:1):1;
  ctx.globalAlpha=alpha;ctx.fillStyle="#4ecca3";
  ctx.beginPath();ctx.arc(player.x,player.y,player.r,0,Math.PI*2);ctx.fill();
  ctx.globalAlpha=1;
  // Bullets
  bullets.forEach(b=>{ctx.fillStyle=b.enemy?"#ff4444":"#88ff88";ctx.beginPath();ctx.arc(b.x,b.y,b.r,0,Math.PI*2);ctx.fill();});
  // HUD
  ctx.fillStyle="#fff";ctx.font="14px monospace";ctx.textAlign="left";
  ctx.fillText(`HP: ${"♥".repeat(player.hp)}  Score: ${score.get()}`,8,18);
  if(player.hp<=0){ctx.fillStyle="rgba(0,0,0,0.8)";ctx.fillRect(0,0,W,H);ctx.fillStyle="#e94560";ctx.font="bold 36px monospace";ctx.textAlign="center";ctx.fillText("GAME OVER",W/2,H/2);}
});
loop.start();'''

# ── SFT examples ─────────────────────────────────────────────────────────────

def tc(tool_name, **kwargs):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"c_{tool_name}", "type": "function", "function": {"name": tool_name, "arguments": json.dumps(kwargs)}}
    ]}

def tr(name, result):
    return {"role": "tool", "tool_call_id": f"c_{name}", "name": name, "content": result}

def sys_msg():
    return {"role": "system", "content": SYSTEM}

def u(t):
    return {"role": "user", "content": t}

examples = []

# v7-tower-defense: tower defense with wave system and enemy path
ex_td = {
    "source": "v7-tower-defense",
    "date": TODAY,
    "messages": [
        sys_msg(),
        u("Build a tower defense game with waves of enemies following a path, tower placement, and a scoring system."),
        tc("project_init", name="tower-defense"),
        tr("project_init", "[project_init] Created 'tower-defense'. Write src/main.ts."),
        tc("file_write", path="deliverables/tower-defense/src/main.ts", content=TOWER_DEF_TS),
        tr("file_write", "Written: deliverables/tower-defense/src/main.ts"),
        tc("shell_exec", command="cd deliverables/tower-defense && npm run build"),
        tr("shell_exec", "Build successful. dist/index.html ready."),
        tc("undertow", path="deliverables/tower-defense/dist/index.html"),
        tr("undertow", "Screenshot: Tower defense — grid path visible, towers placeable, enemy wave spawning at top-left, HUD showing wave/gold/lives/score."),
        tc("message_result", text="Tower defense game: click empty grid tiles to place towers (50g each). Enemies follow the path — stop them before they reach the end. Waves get harder. Built with tsunami-engine FrameLoop and Canvas 2D."),
        tr("message_result", "Delivered."),
    ]
}
examples.append(ex_td)

# v7-dungeon-crawler: top-down dungeon with rooms, enemy patrol/chase AI, sword attack
ex_dc = {
    "source": "v7-dungeon-crawler",
    "date": TODAY,
    "messages": [
        sys_msg(),
        u("Build a 2D top-down dungeon crawler with connected rooms, enemy patrol AI that chases the player, a sword attack, and a health system."),
        tc("project_init", name="dungeon-crawler"),
        tr("project_init", "[project_init] Created 'dungeon-crawler'. Write src/main.ts."),
        tc("file_write", path="deliverables/dungeon-crawler/src/main.ts", content=DUNGEON_TS),
        tr("file_write", "Written: deliverables/dungeon-crawler/src/main.ts"),
        tc("shell_exec", command="cd deliverables/dungeon-crawler && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", path="deliverables/dungeon-crawler/dist/index.html"),
        tr("undertow", "Screenshot: top-down dungeon, 4 rooms connected by corridors. Teal player, red enemies patrolling. HUD shows HP and score."),
        tc("message_result", text="2D dungeon crawler: WASD to move, Space to sword-attack. Enemies patrol and chase when nearby. Camera follows the player. 4 connected rooms. Built with tsunami-engine HealthSystem and Canvas 2D."),
        tr("message_result", "Delivered."),
    ]
}
examples.append(ex_dc)

# v7-rhythm-game: timing windows + beat track + combo scoring
ex_rh = {
    "source": "v7-rhythm-game",
    "date": TODAY,
    "messages": [
        sys_msg(),
        u("Build a rhythm game with 4 lanes, notes that scroll down to a hit zone, keyboard timing windows, and a combo scoring system."),
        tc("project_init", name="rhythm-game"),
        tr("project_init", "[project_init] Created 'rhythm-game'. Write src/main.ts."),
        tc("file_write", path="deliverables/rhythm-game/src/main.ts", content=RHYTHM_TS),
        tr("file_write", "Written: deliverables/rhythm-game/src/main.ts"),
        tc("shell_exec", command="cd deliverables/rhythm-game && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", path="deliverables/rhythm-game/dist/index.html"),
        tr("undertow", "Screenshot: 4 colored lanes, notes scrolling down, hit zone glowing at bottom. D/F/J/K key labels visible. Score and combo counter at top."),
        tc("message_result", text="Rhythm game: press D/F/J/K when notes reach the hit zone. Combo multiplier — 3x+ combo gives bonus points. Beat track with 24 notes. Built with tsunami-engine FrameLoop and Canvas 2D."),
        tr("message_result", "Delivered."),
    ]
}
examples.append(ex_rh)

# v7-bullet-hell: enemy patterns + dodging + power-ups
ex_bh = {
    "source": "v7-bullet-hell",
    "date": TODAY,
    "messages": [
        sys_msg(),
        u("Build a bullet hell shooter where the player dodges enemy bullet patterns (spread shots and circle patterns) and shoots back. Include power-ups and a lives system."),
        tc("project_init", name="bullet-hell"),
        tr("project_init", "[project_init] Created 'bullet-hell'. Write src/main.ts."),
        tc("file_write", path="deliverables/bullet-hell/src/main.ts", content=BULLET_HELL_TS),
        tr("file_write", "Written: deliverables/bullet-hell/src/main.ts"),
        tc("shell_exec", command="cd deliverables/bullet-hell && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", path="deliverables/bullet-hell/dist/index.html"),
        tr("undertow", "Screenshot: vertical shooter, teal player ship at bottom, red enemies at top shooting spread and circle patterns, green player bullets, yellow powerup. HP hearts and score in HUD."),
        tc("message_result", text="Bullet hell shooter: WASD/arrows to dodge, auto-fires upward. Enemies shoot spread and circular bullet patterns. Collect yellow power-ups (enemies drop them). 3 lives with invincibility frames. Built with tsunami-engine FrameLoop + Canvas 2D."),
        tr("message_result", "Delivered."),
    ]
}
examples.append(ex_bh)

# v7-research-clone: Wordle — search_web FIRST, then full pipeline
WORDLE_TS = r'''import { KeyboardInput } from "tsunami-engine";
const W=380,H=500,WORD_LEN=5,MAX_GUESSES=6;
const WORDS=["CRANE","SLATE","PLATE","STARE","TRAIN","BRAIN","PLAIN","RAISE","HOUSE","MOUSE","LIGHT","NIGHT","MIGHT","RIGHT","SIGHT","BREAD","TREAD","GREAT","TREAT","STEAM"];
const TARGET=WORDS[Math.floor(Math.random()*WORDS.length)];
const cv=document.getElementById("canvas") as HTMLCanvasElement;
cv.width=W; cv.height=H;
const ctx=cv.getContext("2d")!;
const kb=new KeyboardInput();
type LetterState="correct"|"present"|"absent"|"empty";
let guesses:string[]=[],current="",gameOver=false,won=false;
function getColors(guess:string):{char:string,state:LetterState}[]{
  const result:{char:string,state:LetterState}[]=guess.split("").map(c=>({char:c,state:"absent"}));
  const remaining=TARGET.split("");
  result.forEach((r,i)=>{if(r.char===TARGET[i]){r.state="correct";remaining[i]="_";}});
  result.forEach(r=>{if(r.state==="absent"){const idx=remaining.indexOf(r.char);if(idx>=0){r.state="present";remaining[idx]="_";}}});
  return result;
}
function draw(){
  ctx.fillStyle="#121213";ctx.fillRect(0,0,W,H);
  ctx.fillStyle="#fff";ctx.font="bold 20px monospace";ctx.textAlign="center";
  ctx.fillText("WORDLE",W/2,36);
  const CELL=52,PAD=6,STARTX=(W-WORD_LEN*CELL-(WORD_LEN-1)*PAD)/2,STARTY=60;
  for(let g=0;g<MAX_GUESSES;g++){
    for(let c=0;c<WORD_LEN;c++){
      const x=STARTX+c*(CELL+PAD),y=STARTY+g*(CELL+PAD);
      let bg="#121213",border="#3a3a3c";
      if(g<guesses.length){
        const colors=getColors(guesses[g]);
        const s=colors[c].state;
        bg=s==="correct"?"#538d4e":s==="present"?"#b59f3b":"#3a3a3c";border=bg;
      } else if(g===guesses.length){
        if(c<current.length){border="#999";}
      }
      ctx.fillStyle=bg;ctx.fillRect(x,y,CELL,CELL);
      ctx.strokeStyle=border;ctx.lineWidth=2;ctx.strokeRect(x,y,CELL,CELL);
      let ch="";
      if(g<guesses.length)ch=guesses[g][c];
      else if(g===guesses.length&&c<current.length)ch=current[c];
      if(ch){ctx.fillStyle="#fff";ctx.font="bold 28px monospace";ctx.textAlign="center";ctx.fillText(ch,x+CELL/2,y+CELL/2+10);}
    }
  }
  if(gameOver){
    ctx.fillStyle="rgba(0,0,0,0.8)";ctx.fillRect(0,H-80,W,80);
    ctx.fillStyle=won?"#538d4e":"#e94560";ctx.font="bold 24px monospace";ctx.textAlign="center";
    ctx.fillText(won?`Solved in ${guesses.length}!`:`Answer: ${TARGET}`,W/2,H-44);
  }
}
// Keyboard input
const LETTERS="ABCDEFGHIJKLMNOPQRSTUVWXYZ";
for(const l of LETTERS){kb.bind("Key"+l,()=>{if(!gameOver&&current.length<WORD_LEN)current+=l;draw();});}
kb.bind("Backspace",()=>{if(!gameOver&&current.length>0){current=current.slice(0,-1);draw();}});
kb.bind("Enter",()=>{
  if(!gameOver&&current.length===WORD_LEN){
    guesses.push(current);current="";
    if(guesses[guesses.length-1]===TARGET){gameOver=true;won=true;}
    else if(guesses.length===MAX_GUESSES){gameOver=true;}
    draw();
  }
});
draw();'''

ex_wordle = {
    "source": "v7-research-clone",
    "date": TODAY,
    "messages": [
        sys_msg(),
        u("Build a Wordle clone — a word guessing game like the NYT Wordle where you guess a 5-letter word in 6 tries with green/yellow/gray tile feedback."),
        # Research gate FIRST — search to understand mechanics
        tc("search_web", query="Wordle word game mechanics rules green yellow gray tile feedback 5 letters 6 guesses"),
        tr("search_web", "Wordle: guess a 5-letter word in 6 tries. After each guess: green = correct letter in correct position, yellow = correct letter in wrong position, gray = letter not in word. No repeated letter counting — each target letter is consumed once."),
        # Now build
        tc("project_init", name="wordle-clone"),
        tr("project_init", "[project_init] Created 'wordle-clone'. Write src/main.ts."),
        tc("file_write", path="deliverables/wordle-clone/src/main.ts", content=WORDLE_TS),
        tr("file_write", "Written: deliverables/wordle-clone/src/main.ts"),
        tc("shell_exec", command="cd deliverables/wordle-clone && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", path="deliverables/wordle-clone/dist/index.html"),
        tr("undertow", "Screenshot: 5×6 grid, dark theme. Top row shows previous guess with green/yellow/gray tiles. Current guess row has typed letters with white borders. Clean NYT Wordle aesthetic."),
        tc("message_result", text="Wordle clone: type 5-letter words, press Enter to submit. Green = right letter, right spot. Yellow = right letter, wrong spot. Gray = not in word. 6 guesses to find the target word. 20-word vocabulary. Built with tsunami-engine KeyboardInput and Canvas 2D."),
        tr("message_result", "Delivered."),
    ]
}
examples.append(ex_wordle)


# ── Tokenize and output ───────────────────────────────────────────────────────

def tokenize(ex):
    tok_msgs = []
    for m in ex["messages"]:
        tok_msgs.append(m)
    return {
        "prompt": tokenizer.apply_chat_template(tok_msgs, tools=TOOLS, tokenize=False),
        "completion": "",
        "source": ex["source"],
        "date": ex["date"],
    }

OUT_V7      = Path("workspace/training_data/gamedev_toolcall_train_v7.jsonl")
OUT_COMBINED = Path("workspace/training_data/gamedev_combined_v7full.jsonl")
OUT_V7.parent.mkdir(parents=True, exist_ok=True)

with open(OUT_V7, "w") as f:
    for ex in examples:
        rec = tokenize(ex)
        f.write(json.dumps(rec) + "\n")

# Combine with all previous
prev_files = [
    Path("workspace/training_data/gamedev_combined_v6full.jsonl"),
]
combined = []
for pf in prev_files:
    if pf.exists():
        with open(pf) as f:
            combined.extend(json.loads(l) for l in f if l.strip())

# Add new
with open(OUT_V7) as f:
    combined.extend(json.loads(l) for l in f if l.strip())

with open(OUT_COMBINED, "w") as f:
    for r in combined:
        f.write(json.dumps(r) + "\n")

print(f"\n=== GAMEDEV SFT v7 SUMMARY ===")
print(f"  New examples: {len(examples)}")
print(f"  Combined total: {len(combined)}")
print(f"  Output v7: {OUT_V7}")
print(f"  Output combined: {OUT_COMBINED}")
for ex in examples:
    print(f"  {ex['source']}: {len(ex['messages'])} messages")
