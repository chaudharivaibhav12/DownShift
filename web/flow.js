/* Downshift · Flow: a live 3D view of the same data the console shows.
   Every particle is a real answer from /api/answers; every crystal is a real skill; the cost meter adds real costs
   as particles land. Timing is stylized (sped up / slowed down), numbers are not. */
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const oid = (x) => (x && typeof x === "object" ? x.$oid : x);
const usd = (n) => (n == null ? "—" : "$" + (n === 0 ? "0.00" : n < 0.01 ? n.toFixed(4) : n < 1 ? n.toFixed(3) : n.toFixed(2)));
const secs = (ms) => (ms >= 1000 ? (ms / 1000).toFixed(1) + " s" : Math.round(ms) + " ms");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const COL = {
  frontier: 0x4c6ef5, mid: 0xf2b01e, cheap: 0x00ed64, bad: 0xff5c5c, atlas: 0x00ed64, dim: 0x1b2330, white: 0xe8eaed,
};
const PATHCOL = { cheap: COL.cheap, mid: COL.mid, learn: COL.frontier, frontier: COL.frontier };

// ------------------------------------------------------------------ renderer / scene
const stage = $("stage");
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
} catch (e) {
  $("nogl").hidden = false;
  throw e;
}
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
stage.appendChild(renderer.domElement);

const labels = new CSS2DRenderer();
labels.setSize(innerWidth, innerHeight);
Object.assign(labels.domElement.style, { position: "absolute", inset: "0", pointerEvents: "none" });
stage.appendChild(labels.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x07090c);
scene.fog = new THREE.FogExp2(0x07090c, 0.022);

const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.1, 200);
const TARGET = new THREE.Vector3(-1, 2.6, 0);
const CAM_R = 27, CAM_Y = 7.5;
camera.position.set(-2, CAM_Y, CAM_R);
camera.lookAt(TARGET);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.copy(TARGET);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 8;
controls.maxDistance = 45;
controls.enabled = false;

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), REDUCED ? 0.55 : 0.85, 0.5, 0.2);
composer.addPass(bloom);
composer.addPass(new OutputPass());

scene.add(new THREE.AmbientLight(0xffffff, 0.35));
const key = new THREE.DirectionalLight(0xffffff, 1.2);
key.position.set(5, 12, 8);
scene.add(key);

const grid = new THREE.GridHelper(80, 80, 0x16202b, 0x0e141b);
grid.position.y = -0.6;
scene.add(grid);

function label(html, cls = "lbl3d") {
  const el = document.createElement("div");
  el.className = cls;
  el.innerHTML = html;
  return new CSS2DObject(el);
}
const glow = (color, opacity = 1) => new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity });

// ------------------------------------------------------------------ static set pieces
const INLET = new THREE.Vector3(-14.5, 6.2, 0);
const ROUTER = new THREE.Vector3(-9.5, 2.4, 0);
const ATLAS = new THREE.Vector3(11.5, -0.2, 0);
const ATLAS_IN = new THREE.Vector3(9.3, 1.9, 0);
const LANE_Z = { frontier: -5, mid: 0, cheap: 5 };
const LANE_Y = { frontier: 5.0, mid: 2.4, cheap: -0.1 };
const NODE_X = 0;

// inlet: a ring questions fall out of
const inlet = new THREE.Mesh(new THREE.TorusGeometry(0.9, 0.04, 8, 48), glow(0x6b7582));
inlet.position.copy(INLET);
inlet.rotation.y = Math.PI / 2;
scene.add(inlet);
const inletLbl = label("QUESTIONS");
inletLbl.position.set(0, 1.5, 0);
inlet.add(inletLbl);

// router: skill search
const router = new THREE.Group();
router.position.copy(ROUTER);
const routerRing = new THREE.Mesh(new THREE.TorusGeometry(1.1, 0.06, 12, 64), glow(0x9aa1ab));
routerRing.rotation.x = Math.PI / 2;
const routerRing2 = new THREE.Mesh(new THREE.TorusGeometry(0.75, 0.03, 8, 48), glow(0x5f6670));
routerRing2.rotation.x = Math.PI / 2;
router.add(routerRing, routerRing2);
const routerLbl = label("SKILL SEARCH<small>which skill fits?</small>");
routerLbl.position.set(0, -1.1, 0);
router.add(routerLbl);
scene.add(router);

// lanes + model nodes
const lanes = {};
const nodes = {};
const NODE_DEF = {
  frontier: { geo: new THREE.IcosahedronGeometry(1.35, 0), text: "FRONTIER MODEL<small>writes + generalizes · $$$</small>" },
  mid: { geo: new THREE.DodecahedronGeometry(0.8, 0), text: "MID MODEL<small>fallback · $$</small>" },
  cheap: { geo: new THREE.OctahedronGeometry(0.5, 0), text: "CHEAP MODEL<small>fills skill params · $</small>" },
};
for (const tier of ["frontier", "mid", "cheap"]) {
  const z = LANE_Z[tier];
  const curve = new THREE.CatmullRomCurve3([
    ROUTER.clone(), new THREE.Vector3(-5.5, LANE_Y[tier] * 0.8 + 0.4, z * 0.9), new THREE.Vector3(NODE_X, LANE_Y[tier], z),
    new THREE.Vector3(5.5, LANE_Y[tier] * 0.8 + 0.4, z * 0.9), ATLAS_IN.clone(),
  ], false, "centripetal");
  lanes[tier] = curve;
  const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 160, 0.035, 6, false), glow(COL[tier], 0.28));
  scene.add(tube);

  const g = new THREE.Group();
  g.position.copy(curve.getPointAt(0.5));
  const solid = new THREE.Mesh(NODE_DEF[tier].geo, new THREE.MeshStandardMaterial({ color: 0x0c1016, emissive: COL[tier], emissiveIntensity: 0.25, roughness: 0.4, metalness: 0.3 }));
  const wire = new THREE.LineSegments(new THREE.EdgesGeometry(NODE_DEF[tier].geo), new THREE.LineBasicMaterial({ color: COL[tier] }));
  wire.scale.setScalar(1.02);
  g.add(solid, wire);
  const l = label(NODE_DEF[tier].text);
  l.position.set(0, tier === "frontier" ? 2.1 : 1.45, 0);
  g.add(l);
  scene.add(g);
  nodes[tier] = { group: g, solid, wire, pulse: 0, spin: 0.15 + (tier === "cheap" ? 0.2 : 0) };
}

// atlas: a glowing database stack
const atlas = new THREE.Group();
atlas.position.copy(ATLAS);
const discs = [];
for (let i = 0; i < 3; i++) {
  const geo = new THREE.CylinderGeometry(2, 2, 0.55, 64);
  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x0b1510, emissive: COL.atlas, emissiveIntensity: 0.07, roughness: 0.5, metalness: 0.4 }));
  m.position.y = 0.4 + i * 0.85;
  const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 30), new THREE.LineBasicMaterial({ color: COL.atlas, transparent: true, opacity: 0.75 }));
  edge.position.copy(m.position);
  atlas.add(m, edge);
  discs.push(m);
}
const atlasLbl = label("MONGODB ATLAS<small>sample_supplies.sales</small>");
atlasLbl.position.set(0, 3.6, 0);
atlas.add(atlasLbl);
const atlasRing = new THREE.Mesh(new THREE.RingGeometry(2.3, 2.45, 96), glow(COL.atlas, 0.5));
atlasRing.rotation.x = -Math.PI / 2;
atlasRing.position.y = -0.55;
atlas.add(atlasRing);
scene.add(atlas);
let atlasPulse = 0;

// skill shelf label
const SHELF_Y = 9.2, SHELF_Z = -3;
const shelfLbl = label("SKILL LIBRARY<small>tested pipeline templates</small>");
shelfLbl.position.set(0, SHELF_Y + 2, SHELF_Z);
scene.add(shelfLbl);

// ambient flow: dim dots drifting along each lane
const drift = [];
for (const tier of Object.keys(lanes)) {
  for (let i = 0; i < 7; i++) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8), glow(COL[tier], 0.55));
    scene.add(m);
    drift.push({ m, tier, u: i / 7 });
  }
}

// ------------------------------------------------------------------ skills (crystals)
const crystals = new Map(); // skillId -> crystal
const CRYSTAL_GEO = new THREE.OctahedronGeometry(0.5, 0);

function shelfSlot(i, n) {
  const gap = 4.3;
  return new THREE.Vector3((i - (n - 1) / 2) * gap, SHELF_Y, SHELF_Z);
}
function layoutShelf() {
  const list = [...crystals.values()];
  list.forEach((c, i) => { c.home.copy(shelfSlot(i, list.length)); c.lbl.position.y = i % 2 ? 1.0 : -1.0; });
}
function makeCrystal(skillId, version, from) {
  const mat = new THREE.MeshStandardMaterial({ color: 0x08130d, emissive: COL.cheap, emissiveIntensity: 0.9, roughness: 0.3, metalness: 0.2 });
  const mesh = new THREE.Mesh(CRYSTAL_GEO, mat);
  const wire = new THREE.LineSegments(new THREE.EdgesGeometry(CRYSTAL_GEO), new THREE.LineBasicMaterial({ color: COL.cheap }));
  wire.scale.setScalar(1.08);
  const g = new THREE.Group();
  g.add(mesh, wire);
  const lbl = label("", "lbl3d skill");
  lbl.position.set(0, -1.0, 0);
  g.add(lbl);
  g.position.copy(from || new THREE.Vector3(0, SHELF_Y, SHELF_Z));
  scene.add(g);
  const c = { skillId, version, g, mesh, wire, lbl, home: g.position.clone(), state: "ok", flash: 0, fly: null, jitter: 0 };
  crystals.set(skillId, c);
  setCrystal(c, "ok", version);
  layoutShelf();
  return c;
}
function setCrystal(c, state, version) {
  c.state = state;
  if (version) c.version = version;
  const col = state === "bad" ? COL.bad : state === "fix" ? COL.frontier : COL.cheap;
  c.mesh.material.emissive.setHex(col);
  c.wire.material.color.setHex(col);
  c.lbl.element.className = "lbl3d skill" + (state === "bad" ? " bad" : state === "fix" ? " fix" : "");
  c.lbl.element.innerHTML = `${esc(c.skillId)} v${c.version}${state === "bad" ? " · broken" : state === "fix" ? " · repairing" : ""}`;
}

// ------------------------------------------------------------------ effects
const actors = new Set();
function addActor(a) { actors.add(a); return a; }

function beam(from, to, color, dur = 0.7) {
  const geo = new THREE.BufferGeometry().setFromPoints([from.clone(), to.clone()]);
  const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 1 }));
  scene.add(line);
  let t = 0;
  addActor({ update(dt) { t += dt; line.material.opacity = Math.max(0, 1 - t / dur); if (t >= dur) { scene.remove(line); geo.dispose(); return false; } return true; } });
}
function burst(pos, color, size = 1.2, dur = 0.6) {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.2, 0.28, 48), glow(color, 1));
  m.position.copy(pos);
  m.lookAt(camera.position);
  m.material.side = THREE.DoubleSide;
  scene.add(m);
  let t = 0;
  addActor({ update(dt) { t += dt; const k = t / dur; m.scale.setScalar(1 + k * size * 5); m.material.opacity = Math.max(0, 1 - k); if (k >= 1) { scene.remove(m); return false; } return true; } });
}
function shockwave(color) {
  const m = new THREE.Mesh(new THREE.RingGeometry(2.3, 2.6, 96), glow(color, 0.9));
  m.rotation.x = -Math.PI / 2;
  m.position.set(ATLAS.x, -0.5, ATLAS.z);
  m.material.side = THREE.DoubleSide;
  scene.add(m);
  let t = 0;
  addActor({ update(dt) { t += dt; const k = t / 1.6; m.scale.setScalar(1 + k * 7); m.material.opacity = Math.max(0, 0.9 * (1 - k)); if (k >= 1) { scene.remove(m); return false; } return true; } });
}

// ------------------------------------------------------------------ particles (one per real answer)
const PARTICLE_GEO = new THREE.SphereGeometry(0.17, 16, 16);
const TRAIL = 26;

function segCurve(curve, u0, u1) { return { at: (p) => curve.getPointAt(u0 + (u1 - u0) * p) }; }
function arc(a, b, lift) {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  mid.y += lift;
  const c = new THREE.QuadraticBezierCurve3(a.clone(), mid, b.clone());
  return { at: (p) => c.getPoint(p) };
}

function launch(a, speed) {
  const path = a.path;
  const color = PATHCOL[path] ?? COL.bad;
  const mesh = new THREE.Mesh(PARTICLE_GEO, glow(0xffffff));
  mesh.position.copy(INLET);
  scene.add(mesh);
  const trailGeo = new THREE.BufferGeometry();
  const trailPos = new Float32Array(TRAIL * 3);
  for (let i = 0; i < TRAIL; i++) trailPos.set([INLET.x, INLET.y, INLET.z], i * 3);
  trailGeo.setAttribute("position", new THREE.BufferAttribute(trailPos, 3));
  const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.75 }));
  scene.add(trail);
  const q = label(esc(a.question.length > 46 ? a.question.slice(0, 44) + "…" : a.question), "lbl3d");
  q.element.style.cssText = "font:500 12px var(--sans);letter-spacing:0;color:#cfd3d8;opacity:.95;transition:opacity .5s";
  q.position.set(0, 0.55, 0);
  mesh.add(q);

  const skill = a.skill ? a.skill.split(" ")[0].split("@")[0] : null;
  const crystal = skill ? crystals.get(skill) : null;
  const setColor = (c) => { mesh.material.color.setHex(c); trail.material.color.setHex(c); };
  const s = (d) => d / speed;
  const segs = [];
  segs.push({ c: arc(INLET, ROUTER, 1.2), d: s(0.8), end: () => {
    q.element.style.opacity = "0";
    routerRing.material.color.setHex(0xffffff);
    setTimeout(() => routerRing.material.color.setHex(0x9aa1ab), 180);
    if (crystal && path !== "learn" && path !== "frontier") { beam(ROUTER, crystal.g.position, COL.cheap); crystal.flash = 1; }
  } });
  const toNode = (tier) => ({ c: segCurve(lanes[tier], 0, 0.5), d: s(tier === "frontier" ? 1.3 : 0.9), start: () => setColor(COL[tier]), end: () => { nodes[tier].pulse = 1; } });
  const fromNode = (tier) => ({ c: segCurve(lanes[tier], 0.5, 1), d: s(tier === "frontier" ? 1.1 : 0.8) });
  if (path === "cheap") segs.push(toNode("cheap"), fromNode("cheap"));
  else if (path === "mid") {
    segs.push({ ...toNode("cheap"), end: () => { nodes.cheap.pulse = 1; setColor(COL.bad); burst(lanes.cheap.getPointAt(0.5), COL.bad, 0.6); } });
    segs.push({ c: arc(lanes.cheap.getPointAt(0.5), lanes.mid.getPointAt(0.5), 1.6), d: s(0.6), start: () => setColor(COL.mid), end: () => { nodes.mid.pulse = 1; } });
    segs.push(fromNode("mid"));
  } else if (path === "learn" || path === "frontier") {
    segs.push(toNode("frontier"), { c: { at: () => lanes.frontier.getPointAt(0.5) }, d: s(path === "learn" ? 0.9 : 0.4), start: () => { nodes.frontier.spin = 3; }, end: () => { nodes.frontier.spin = 0.15; } }, fromNode("frontier"));
  } else {
    segs.push({ c: { at: () => ROUTER }, d: s(0.4), start: () => setColor(COL.bad) });
  }

  let i = 0, t = 0, started = false;
  const done = () => {
    scene.remove(mesh, trail);
    trailGeo.dispose();
    if (PATHCOL[path] != null) {
      atlasPulse = 1;
      burst(ATLAS_IN, color, 0.5, 0.5);
      if (path === "learn" && a.skill && a.skill.includes("promoted") && !crystals.has(skill)) forge(skill, Number((a.skill.split("@v")[1] || "1").split(" ")[0]));
    }
    land(a);
  };
  return addActor({
    update(dt) {
      if (i >= segs.length) {
        // let the trail catch up, then finish
        t += dt;
        trail.material.opacity = Math.max(0, 0.55 - t * 1.5);
        if (t > 0.35) { done(); return false; }
        return true;
      }
      const sg = segs[i];
      if (!started) { sg.start?.(); started = true; }
      t += dt;
      const p = Math.min(1, t / sg.d);
      mesh.position.copy(sg.c.at(p));
      if (p >= 1) { sg.end?.(); i++; t = 0; started = false; }
      trailPos.copyWithin(3, 0, (TRAIL - 1) * 3);
      trailPos.set([mesh.position.x, mesh.position.y, mesh.position.z], 0);
      trailGeo.attributes.position.needsUpdate = true;
      return true;
    },
  });
}

function forge(skillId, version) {
  const from = lanes.frontier.getPointAt(0.5).clone();
  const c = makeCrystal(skillId, version, from);
  beam(from, c.home, COL.frontier, 1.0);
  burst(from, COL.frontier, 1.2, 0.8);
  c.fly = { from, t: 0 };
  ticker(`<b style="color:#AFC0FF">New skill</b> ${esc(skillId)} v${version} added to the library<span class="m">cheap model can use it now</span>`);
}

// ------------------------------------------------------------------ HUD
const hud = { costD: 0, costF: 0, n: 0, paths: { cheap: 0, mid: 0, learn: 0, frontier: 0 } };
let FPA = 0.02;

function renderMeter() {
  const max = Math.max(hud.costF, hud.costD, 1e-9);
  $("barF").style.width = (hud.costF / max) * 100 + "%";
  $("barD").style.width = (hud.costD / max) * 100 + "%";
  $("costF").textContent = usd(hud.costF);
  $("costD").textContent = usd(hud.costD);
  const save = $("save");
  if (!hud.n) { save.className = "save small"; save.textContent = "ask a question to start"; }
  else if (hud.costD < hud.costF) { save.className = "save"; save.innerHTML = `${Math.round((1 - hud.costD / hud.costF) * 100)}% cheaper <span style="font:12px var(--mono);color:#8A9099;letter-spacing:0">over ${hud.n} answers</span>`; }
  else { save.className = "save small"; save.textContent = `learning: ${hud.n} answer${hud.n === 1 ? "" : "s"}, skills pay off from the next one`; }
  const P = [["cheap", "#00ED64"], ["mid", "#F2B01E"], ["learn", "#4C6EF5"], ["frontier", "#9AA1AB"]];
  $("paths").innerHTML = P.filter(([p]) => hud.paths[p] || p !== "frontier").map(([p, c]) => `<span><i style="--c:${c}"></i>${p} ${hud.paths[p]}</span>`).join("");
}

function land(a) {
  hud.n += 1;
  hud.costD += a.cost || 0;
  hud.costF += FPA;
  if (hud.paths[a.path] != null) hud.paths[a.path] += 1;
  renderMeter();
  const skill = a.skill ? a.skill.split(" ")[0] : "";
  const m = `<span class="m">${usd(a.cost)} · ${secs(a.ms)}</span>`;
  if (a.path === "cheap") ticker(`<b style="color:#7CE0A7">Cheap</b> reused ${esc(skill)}${m}`);
  else if (a.path === "mid") ticker(`<b style="color:#F2B01E">Escalated</b> cheap model slipped, mid model filled ${esc(skill)}${m}`);
  else if (a.path === "learn") ticker(`<b style="color:#AFC0FF">Learned</b> new kind of question, frontier answered once${m}`);
  else if (a.path === "frontier") ticker(`<b>Frontier</b> answered while its skill is being repaired${m}`);
  else ticker(`<b style="color:#FF9C9C">No answer</b> ${esc(a.question)}`);
}

function ticker(html) {
  const el = document.createElement("div");
  el.className = "tick";
  el.innerHTML = html;
  const box = $("ticker");
  box.prepend(el);
  while (box.children.length > 4) box.lastChild.remove();
}

// ------------------------------------------------------------------ data sync
let S = null;
let booted = false;
const seen = new Set();
const queue = [];
const skillState = new Map(); // "skillId@vN" -> status
let repairId = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

function latestBySkill(skills) {
  const m = new Map();
  for (const s of skills) if (!m.has(s.skillId) || s.version > m.get(s.skillId).version) m.set(s.skillId, s);
  return m;
}

function syncSkills(first) {
  const latest = latestBySkill(S.skills);
  for (const s of S.skills) {
    const k = `${s.skillId}@v${s.version}`;
    const prev = skillState.get(k);
    skillState.set(k, s.status);
    if (first || prev === s.status) continue;
    const c = crystals.get(s.skillId);
    if (s.status === "flagged" && c) {
      setCrystal(c, "bad");
      c.jitter = 1;
      burst(c.g.position, COL.bad, 0.8);
      ticker(`<b style="color:#FF9C9C">Broken</b> ${esc(s.skillId)} reads a renamed field<span class="m">off the cheap path</span>`);
    }
    if (s.status === "promoted" && s.repairedFrom && c) {
      setCrystal(c, "fix", s.version);
      beam(lanes.frontier.getPointAt(0.5), c.g.position, COL.frontier, 1.2);
      setTimeout(() => { setCrystal(c, "ok", s.version); c.jitter = 0; burst(c.g.position, COL.cheap, 1); }, 900);
      const res = (S.repair?.results || []).find((r) => r.skill === s.skillId && r.to === s.version);
      const eq = res?.equivalence || [];
      ticker(`<b style="color:#7CE0A7">Repaired</b> ${esc(s.skillId)} → v${s.version}<span class="m">${eq.filter((e) => e.same).length}/${eq.length} answers identical · gate ${esc(res?.gate || "")}</span>`);
    }
    if (s.status === "rejected") ticker(`<b style="color:#FF9C9C">Rejected</b> ${esc(s.skillId)} v${s.version} failed the gate<span class="m">frontier reflecting on the failing traces</span>`);
    if (s.status === "promoted" && s.reflectedFrom) ticker(`<b style="color:#7CE0A7">Reflected</b> ${esc(s.skillId)} v${s.reflectedFrom} → v${s.version}<span class="m">${esc(s.reflectionNote || "")}</span>`);
  }
  if (first) {
    for (const [id, s] of latest) {
      if (!["promoted", "flagged"].includes(s.status)) continue;
      const c = makeCrystal(id, s.version);
      if (s.status === "flagged") { setCrystal(c, "bad"); c.jitter = 1; }
    }
  }
}

function syncRepair(first) {
  const r = S.repair;
  const id = r ? oid(r._id) : null;
  if (id && id !== repairId && !first) {
    shockwave(COL.mid);
    atlasPulse = 1.5;
    ticker(`<b style="color:#F2B01E">Schema changed</b> ${esc((r.changed || []).join(" ↔ "))}<span class="m">change stream noticed · checking skills</span>`);
  }
  repairId = id;
}

function syncAnswers(first) {
  const fresh = S.answers.filter((a) => !seen.has(oid(a._id))).sort((x, y) => new Date(x.ts.$date || x.ts) - new Date(y.ts.$date || y.ts));
  for (const a of fresh) seen.add(oid(a._id));
  if (first) {
    // start the meter from the full history, don't animate it
    FPA = S.stats.frontierPerAnswer;
    hud.n = S.stats.answers;
    hud.costD = S.stats.spent;
    hud.costF = S.stats.answers * FPA;
    Object.assign(hud.paths, S.stats.paths);
    renderMeter();
    return;
  }
  FPA = S.stats.frontierPerAnswer;
  queue.push(...fresh);
}

function syncHeader() {
  const busy = !!S.job.name;
  $("replayBtn").disabled = busy;
  $("replayBtn").textContent = S.job.name === "replay" ? `Replaying ${S.job.done}/${S.job.total}…` : "Replay 30 questions";
  $("schemaBtn").disabled = busy;
  $("schemaBtn").textContent = S.job.name === "schema-change" ? "Repairing…" : "Simulate schema change";
  $("demoTag").hidden = !S.demo;
  $("resetBtn").hidden = !S.demo;
}

async function refresh() {
  try {
    S = await api("/api/state");
    $("live").classList.remove("off");
  } catch {
    $("live").classList.add("off");
    return;
  }
  const first = !booted;
  booted = true;
  syncHeader();
  syncRepair(first);
  syncSkills(first);
  syncAnswers(first);
}
let rt = null;
const refreshSoon = () => { clearTimeout(rt); rt = setTimeout(refresh, 100); };
const es = new EventSource("/api/stream");
es.onmessage = refreshSoon;
es.onerror = () => $("live").classList.add("off");
setInterval(refresh, 8000);
refresh();

// ------------------------------------------------------------------ controls
$("replayBtn").onclick = () => api("/api/replay", { method: "POST" }).then(refreshSoon).catch((e) => ticker(esc(e.message)));
$("schemaBtn").onclick = () => api("/api/schema-change", { method: "POST", body: "{}" }).then(refreshSoon).catch((e) => ticker(esc(e.message)));
let armed = false;
$("resetBtn").onclick = async () => {
  if (!armed) { armed = true; $("resetBtn").textContent = "Click again"; setTimeout(() => { armed = false; $("resetBtn").textContent = "Reset"; }, 3000); return; }
  armed = false; $("resetBtn").textContent = "Reset";
  await api("/api/reset", { method: "POST" }).catch(() => {});
  for (const c of crystals.values()) scene.remove(c.g);
  crystals.clear(); seen.clear(); skillState.clear(); queue.length = 0; booted = false; repairId = null;
  Object.assign(hud, { costD: 0, costF: 0, n: 0, paths: { cheap: 0, mid: 0, learn: 0, frontier: 0 } });
  $("ticker").innerHTML = "";
  refresh();
};
$("askForm").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("askInput").value.trim();
  if (!q) return;
  $("askBtn").disabled = true;
  try { await api("/api/ask", { method: "POST", body: JSON.stringify({ question: q }) }); $("askInput").value = ""; }
  catch (err) { ticker(`<b style="color:#FF9C9C">Error</b> ${esc(err.message)}`); }
  finally { $("askBtn").disabled = false; refreshSoon(); }
};
let orbit = !REDUCED;
const setOrbit = (on) => { orbit = on; controls.enabled = !on; $("orbitBtn").setAttribute("aria-pressed", String(on)); };
setOrbit(orbit);
$("orbitBtn").onclick = () => setOrbit(!orbit);
renderer.domElement.addEventListener("pointerdown", () => orbit && setOrbit(false));
const toggleFull = () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()).catch(() => {});
$("fullBtn").onclick = toggleFull;
addEventListener("keydown", (e) => { if (e.key === "f" && document.activeElement.tagName !== "INPUT") toggleFull(); });
document.addEventListener("fullscreenchange", () => document.body.classList.toggle("booth", !!document.fullscreenElement));

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
  labels.setSize(innerWidth, innerHeight);
});

// ------------------------------------------------------------------ loop
const clock = new THREE.Clock();
let sinceLaunch = 99;
let elapsed = 0;
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  elapsed += dt;

  // launch queued answers; speed up when a replay floods the queue
  const speed = (REDUCED ? 2 : 1) * Math.min(2.6, 1 + queue.length * 0.12);
  sinceLaunch += dt;
  if (queue.length && sinceLaunch > 0.55 / speed) { launch(queue.shift(), speed); sinceLaunch = 0; }

  for (const a of [...actors]) if (!a.update(dt)) actors.delete(a);

  // set pieces
  routerRing.rotation.z += dt * 0.6;
  routerRing2.rotation.z -= dt * 1.1;
  inlet.rotation.x += dt * 0.4;
  for (const [tier, n] of Object.entries(nodes)) {
    n.group.rotation.y += dt * n.spin;
    n.group.rotation.x += dt * n.spin * 0.4;
    n.pulse = Math.max(0, n.pulse - dt * 1.8);
    n.solid.material.emissiveIntensity = 0.25 + n.pulse * 1.6;
    n.group.scale.setScalar(1 + n.pulse * 0.18);
  }
  atlasPulse = Math.max(0, atlasPulse - dt * 1.5);
  discs.forEach((d, i) => { d.material.emissiveIntensity = 0.07 + atlasPulse * (0.35 - i * 0.07) + Math.sin(elapsed * 1.5 + i) * 0.015; });
  atlasRing.material.opacity = 0.3 + atlasPulse * 0.4;
  for (const d of drift) {
    d.u = (d.u + dt * 0.05) % 1;
    d.m.position.copy(lanes[d.tier].getPointAt(d.u));
  }
  for (const c of crystals.values()) {
    if (c.fly) {
      c.fly.t += dt / 1.1;
      const k = Math.min(1, c.fly.t);
      const e = 1 - Math.pow(1 - k, 3);
      c.g.position.lerpVectors(c.fly.from, c.home, e);
      c.g.scale.setScalar(0.3 + 0.7 * e);
      if (k >= 1) c.fly = null;
    } else {
      c.g.position.lerp(c.home, Math.min(1, dt * 3));
      c.g.position.y = c.home.y + Math.sin(elapsed * 1.2 + c.home.x) * 0.12;
      if (c.jitter) { c.g.position.x += (Math.random() - 0.5) * 0.06; c.g.position.z += (Math.random() - 0.5) * 0.06; }
    }
    c.g.rotation.y += dt * (c.state === "bad" ? 0.2 : 0.8);
    c.flash = Math.max(0, c.flash - dt * 2);
    c.mesh.material.emissiveIntensity = (c.state === "bad" ? 0.5 + Math.abs(Math.sin(elapsed * 6)) * 0.6 : 0.8) + c.flash * 1.5;
  }

  // camera: slow sway, or free orbit
  if (orbit) {
    const az = Math.sin(elapsed * 0.07) * 0.42;
    camera.position.set(TARGET.x + Math.sin(az) * CAM_R, CAM_Y + Math.sin(elapsed * 0.05) * 0.8, TARGET.z + Math.cos(az) * CAM_R);
    camera.lookAt(TARGET);
    controls.target.copy(TARGET);
  } else controls.update();

  composer.render();
  labels.render(scene, camera);
  requestAnimationFrame(frame);
}
renderMeter();
frame();
