// The existing biological layout wrapped onto a sphere. This is not geographic space.
// Canvas keeps the globe light enough for phones; the original flat map remains available.
import { useEffect, useRef, useState } from "react";
import type { MapProps, RouteStop } from "./StarMap";
import { useReducedMotion } from "../lib/useReducedMotion";

type V = { x: number; y: number; z: number };
type Pin = RouteStop & { x: number; y: number };
const clamp = (n: number, a: number, b: number) => Math.max(a, Math.min(b, n));

export function GlobeMap(props: MapProps) {
  const reduceMotion = useReducedMotion();
  const motion = useRef(reduceMotion);
  motion.current = reduceMotion;
  const canvas = useRef<HTMLCanvasElement>(null);
  const current = useRef(props);
  current.current = props;
  const redraw = useRef<() => void>(() => {});
  const fly = useRef<() => void>(() => {});
  const zoom = useRef<(factor: number) => void>(() => {});
  const [pins, setPins] = useState<Pin[]>([]);
  const [hover, setHover] = useState("");

  useEffect(() => {
    const el = canvas.current!;
    const ctx = el.getContext("2d")!;
    const { data } = current.current;
    const xs = data.nodes.map(n => n.x), ys = data.nodes.map(n => n.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const angles = (x: number, y: number) => ({ lon: ((x - minX) / (maxX - minX) - 0.5) * Math.PI * 1.85, lat: (0.5 - (y - minY) / (maxY - minY)) * Math.PI * 0.78 });
    const vector = (x: number, y: number): V => { const { lon, lat } = angles(x, y); return { x: Math.cos(lat) * Math.sin(lon), y: Math.sin(lat), z: Math.cos(lat) * Math.cos(lon) }; };
    const nodes = data.nodes.map(n => ({ ...n, v: vector(n.x, n.y), ...angles(n.x, n.y) }));
    const byId = new Map(nodes.map(n => [n.id, n]));
    const camera = { yaw: 0, pitch: 0.08, zoom: 1 };
    let width = 1, height = 1, radius = 1, cx = 0, cy = 0, frame = 0;
    let target: typeof camera | null = null;
    let disposed = false;
    let hitNodes: { id: string; x: number; y: number; name: string }[] = [];
    const rotate = (v: V) => {
      const x = Math.cos(camera.yaw) * v.x - Math.sin(camera.yaw) * v.z;
      const z = Math.sin(camera.yaw) * v.x + Math.cos(camera.yaw) * v.z;
      return { x, y: Math.cos(camera.pitch) * v.y - Math.sin(camera.pitch) * z, z: Math.sin(camera.pitch) * v.y + Math.cos(camera.pitch) * z };
    };
    const screen = (v: V) => { const r = rotate(v); return { x: cx + r.x * radius, y: cy - r.y * radius, z: r.z }; };
    const glow = document.createElement("canvas");
    glow.width = glow.height = 48;
    const g = glow.getContext("2d")!;
    const gradient = g.createRadialGradient(24, 24, 0, 24, 24, 24);
    gradient.addColorStop(0, "rgba(255,236,189,.85)"); gradient.addColorStop(.15, "rgba(248,195,109,.35)"); gradient.addColorStop(1, "rgba(222,152,57,0)");
    g.fillStyle = gradient; g.fillRect(0, 0, 48, 48);

    const arc = (a: V, b: V, bright: boolean) => {
      // A spherical interpolation keeps paths attached to the globe as it turns.
      const omega = Math.acos(clamp(a.x*b.x + a.y*b.y + a.z*b.z, -1, 1));
      if (omega < 0.0001 || Math.abs(Math.sin(omega)) < 0.0001) return;
      const steps = bright ? 40 : 14;
      ctx.beginPath(); let visible = false;
      for (let i = 0; i <= steps; i++) {
        const t = i / steps, sa = Math.sin((1-t)*omega)/Math.sin(omega), sb = Math.sin(t*omega)/Math.sin(omega);
        const lift = 1 + Math.sin(t*Math.PI)*(bright ? .025 : .007);
        const p = screen({ x: (a.x*sa+b.x*sb)*lift, y: (a.y*sa+b.y*sb)*lift, z: (a.z*sa+b.z*sb)*lift });
        if (p.z < .02) { visible = false; continue; }
        if (!visible) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        visible = true;
      }
      ctx.stroke();
    };

    const draw = () => {
      if (disposed) return;
      frame = 0;
      if (target) {
        const diff = ((target.yaw - camera.yaw + Math.PI * 3) % (Math.PI*2)) - Math.PI;
        const t = motion.current ? 1 : .13;
        camera.yaw += diff*t; camera.pitch += (target.pitch-camera.pitch)*t; camera.zoom += (target.zoom-camera.zoom)*t;
        if (Math.abs(diff)+Math.abs(target.pitch-camera.pitch)+Math.abs(target.zoom-camera.zoom)<.004) target = null;
      }
      cx = width/2; cy = height/2 + (width < 600 ? 18 : 0); radius = Math.min(width*.44,height*.43)*camera.zoom;
      ctx.clearRect(0,0,width,height);
      // A restrained blue atmosphere defines the silhouette; the lights carry the detail.
      const atmosphere = ctx.createRadialGradient(cx,cy,radius*.92,cx,cy,radius*1.06);
      atmosphere.addColorStop(0,"rgba(35,60,94,.05)"); atmosphere.addColorStop(.58,"rgba(70,104,149,.15)"); atmosphere.addColorStop(1,"rgba(15,28,50,0)");
      ctx.fillStyle=atmosphere; ctx.beginPath(); ctx.arc(cx,cy,radius*1.06,0,Math.PI*2); ctx.fill();
      const sphere = ctx.createRadialGradient(cx-radius*.35,cy-radius*.35,0,cx,cy,radius);
      sphere.addColorStop(0,"#101d2b"); sphere.addColorStop(.7,"#091320"); sphere.addColorStop(1,"#040a13");
      ctx.fillStyle=sphere; ctx.beginPath(); ctx.arc(cx,cy,radius,0,Math.PI*2); ctx.fill();
      const { focus, related, highlight, emphasized, route, activeStep } = current.current;
      const rel = new Set(related.map(n=>n.id));
      ctx.lineWidth=.65; ctx.strokeStyle=focus ? "rgba(153,182,217,.035)" : "rgba(177,190,205,.10)";
      for (let i=0; i<data.edges.length; i+=Math.max(1,Math.floor(data.edges.length/650))) {
        const [a,b]=data.edges[i]; if (nodes[a] && nodes[b]) arc(nodes[a].v,nodes[b].v,false);
      }
      hitNodes=[];
      for (const n of nodes) {
        const p=screen(n.v); if (p.z<=0 || p.x < -20 || p.x>width+20 || p.y< -20 || p.y>height+20) continue;
        const selected=n.id===focus, relative=rel.has(n.id), lit=highlight?.has(n.id);
        const size=selected ? 4 : relative || lit ? 2.1 : clamp(.65+Math.sqrt(camera.zoom)*.26+n.connections/100,.7,2);
        ctx.globalAlpha=(focus || highlight) && !selected && !relative && !lit ? .25 : .3+.7*Math.sqrt(p.z);
        const halo=(selected ? 40 : relative || lit ? 22 : 8+Math.sqrt(camera.zoom)*4);
        ctx.drawImage(glow,p.x-halo/2,p.y-halo/2,halo,halo);
        ctx.fillStyle=selected ? "#fffef4" : relative || lit ? "#ffe1a1" : "#e5c797";
        ctx.beginPath(); ctx.arc(p.x,p.y,size,0,Math.PI*2); ctx.fill();
        hitNodes.push({id:n.id,x:p.x,y:p.y,name:n.name});
      }
      ctx.globalAlpha=1;
      const origin=focus ? byId.get(focus) : null;
      if (origin) {
        for (const r of related) { const n=byId.get(r.id); if (!n) continue; ctx.strokeStyle=r.id===emphasized ? "rgba(255,247,215,.95)" : "rgba(228,195,133,.45)";ctx.lineWidth=r.id===emphasized?2:1;arc(origin.v,n.v,true); }
        ctx.strokeStyle="rgba(255,218,142,.9)";ctx.lineWidth=1.6;ctx.setLineDash([5,4]);
        for (let i=1;i<route.length;i++) { const a=byId.get(route[i-1].id), b=byId.get(route[i].id); if(a&&b)arc(a.v,b.v,true); }
        ctx.setLineDash([]);
      }
      // Labels share one collision budget so names stay legible in dense cities.
      const boxes: {x:number;y:number;w:number;h:number}[]=[];
      const label=(text:string,v:V,selected=false) => {
        const p=screen(v); if(p.z < .2)return;
        const size=selected?12:10;ctx.font=`${selected?600:500} ${size}px Inter, system-ui, sans-serif`;
        const short=text.length>43?text.slice(0,41)+"…":text,w=ctx.measureText(short).width+12;
        const box={x:p.x-w/2,y:p.y+12,w,h:20};
        if(box.x<8||box.x+w>width-8||box.y<70||box.y+20>height-58)return;
        if(boxes.some(b=>box.x<b.x+b.w&&box.x+w>b.x&&box.y<b.y+b.h&&box.y+box.h>b.y))return;
        boxes.push(box);ctx.textAlign="center";ctx.fillStyle=selected?"#ffedc9":"rgba(197,211,226,.68)";
        ctx.shadowColor="#03070e";ctx.shadowBlur=6;ctx.fillText(short,p.x,p.y+26);ctx.shadowBlur=0;
      };
      if(origin)label(origin.name,origin.v,true);
      for(const r of [...related].sort((a,b)=>a.id===emphasized?-1:b.id===emphasized?1:0)){ const n=byId.get(r.id);if(n)label(n.name,n.v,true); }
      const areas=camera.zoom<1.7?data.regions:data.constellations;
      for(const a of [...areas].sort((a,b)=>b.size-a.size))label(a.name,vector(a.x,a.y));
      const chosen=route.filter(p=>p.step===activeStep||!route.some(q=>q.id===p.id&&q.step===activeStep)&&route.find(q=>q.id===p.id)?.step===p.step);
      const nextPins: Pin[]=[];
      for(const pin of [...chosen].sort((a,b)=>a.step===activeStep?-1:b.step===activeStep?1:0)) {
        const n=byId.get(pin.id);if(!n)continue;const pos=screen(n.v);
        if(pos.z<=.1||pos.x<16||pos.x>width-16||pos.y<60||pos.y>height-40)continue;
        let y=pos.y;
        while(nextPins.some(p=>Math.hypot(p.x-pos.x,p.y-y)<34))y-=34;
        if(y!==pos.y){ctx.strokeStyle="rgba(255,218,142,.7)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(pos.x,pos.y);ctx.lineTo(pos.x,y);ctx.stroke();}
        nextPins.push({...pin,x:pos.x,y});
      }
      setPins(nextPins);
      if(target)frame=requestAnimationFrame(draw);
    };
    const schedule=()=>{if(!frame)frame=requestAnimationFrame(draw);};
    redraw.current=schedule;
    fly.current=()=>{
      const { focus, highlight }=current.current;
      const n=focus ? byId.get(focus) : highlight?.size ? byId.get([...highlight][0]) : null;
      target=n ? {yaw:n.lon,pitch:n.lat,zoom:focus?2.5:1.2} : {yaw:0,pitch:.08,zoom:1};
      schedule();
    };
    zoom.current=factor=>{target=null;camera.zoom=clamp(camera.zoom*factor,.7,18);schedule();};
    const resize=()=>{const rect=el.getBoundingClientRect();width=rect.width;height=rect.height;const dpr=Math.min(window.devicePixelRatio||1,2);el.width=Math.round(width*dpr);el.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);schedule();};
    const observer=new ResizeObserver(resize);observer.observe(el);
    const pointers=new Map<number,{x:number;y:number}>();
    let down={x:0,y:0},moved=false,pinch=0;
    const distance=()=>{const p=[...pointers.values()];return p.length===2?Math.hypot(p[1].x-p[0].x,p[1].y-p[0].y):0;};
    const nearest=(x:number,y:number)=>hitNodes.reduce<{id:string;x:number;y:number;name:string}|null>((best,n)=>Math.hypot(n.x-x,n.y-y)<12&&(!best||Math.hypot(n.x-x,n.y-y)<Math.hypot(best.x-x,best.y-y))?n:best,null);
    const pointerDown=(e:PointerEvent)=>{target=null;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});down={x:e.clientX,y:e.clientY};moved=false;pinch=distance();el.setPointerCapture(e.pointerId);};
    const pointerMove=(e:PointerEvent)=>{
      const prev=pointers.get(e.pointerId);
      if(prev){pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(Math.hypot(e.clientX-down.x,e.clientY-down.y)>4)moved=true;
        if(pointers.size===2){const next=distance();if(pinch)camera.zoom=clamp(camera.zoom*next/pinch,.7,18);pinch=next;moved=true;}
        else{camera.yaw-=(e.clientX-prev.x)/radius;camera.pitch=clamp(camera.pitch+(e.clientY-prev.y)/radius,-Math.PI/2,Math.PI/2);}schedule();
      }else{const r=el.getBoundingClientRect();const n=nearest(e.clientX-r.left,e.clientY-r.top);setHover(n?.name||"");el.style.cursor=n?"pointer":"grab";}
    };
    const pointerUp=(e:PointerEvent)=>{if(!moved&&pointers.size===1){const r=el.getBoundingClientRect(),n=nearest(e.clientX-r.left,e.clientY-r.top);if(n)current.current.onSelect(n.id);}pointers.delete(e.pointerId);pinch=0;};
    const cancel=(e:PointerEvent)=>{pointers.delete(e.pointerId);pinch=0;moved=true;};
    const wheel=(e:WheelEvent)=>{e.preventDefault();zoom.current(Math.exp(-e.deltaY*.001));};
    const key=(e:KeyboardEvent)=>{if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","+","=","-"].includes(e.key)){e.preventDefault();target=null;if(e.key==="ArrowLeft")camera.yaw-=.12;if(e.key==="ArrowRight")camera.yaw+=.12;if(e.key==="ArrowUp")camera.pitch=clamp(camera.pitch+.12,-1.5,1.5);if(e.key==="ArrowDown")camera.pitch=clamp(camera.pitch-.12,-1.5,1.5);if(e.key==="+"||e.key==="=")zoom.current(1.3);if(e.key==="-")zoom.current(1/1.3);schedule();}};
    el.addEventListener("pointerdown",pointerDown);el.addEventListener("pointermove",pointerMove);el.addEventListener("pointerup",pointerUp);el.addEventListener("pointercancel",cancel);el.addEventListener("wheel",wheel,{passive:false});el.addEventListener("keydown",key);
    fly.current();
    return()=>{disposed=true;cancelAnimationFrame(frame);observer.disconnect();el.removeEventListener("pointerdown",pointerDown);el.removeEventListener("pointermove",pointerMove);el.removeEventListener("pointerup",pointerUp);el.removeEventListener("pointercancel",cancel);el.removeEventListener("wheel",wheel);el.removeEventListener("keydown",key);};
  },[props.data]);
  useEffect(()=>{fly.current();},[props.focus,props.highlight]);
  useEffect(()=>{redraw.current();},[props.related,props.emphasized,props.route,props.activeStep]);
  useEffect(()=>{redraw.current();},[reduceMotion]);
  return <div className="absolute inset-x-0 top-0 bottom-[58dvh] overflow-hidden bg-[#03070e] sm:bottom-0 sm:left-[432px]">
    <canvas ref={canvas} tabIndex={0} role="img" aria-label="Interactive globe of rare genetic conditions. Drag or use arrow keys to turn. Scroll or use plus and minus to zoom. Use search or Directions to choose a condition." className="absolute inset-0 h-full w-full touch-none outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-amber-200" />
    {pins.map(p=><button key={p.step} onClick={()=>props.onStop(p.step)} aria-label={`Directions stop ${p.step+1}: ${p.label}`} style={{left:p.x,top:p.y}} className={`absolute z-10 grid h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border text-xs font-bold shadow-lg ${p.step===props.activeStep?"border-white bg-amber-100 text-slate-900":"border-amber-200/70 bg-slate-900 text-amber-100"}`}>{p.step+1}</button>)}
    <div className="pointer-events-none absolute bottom-3 left-4 right-16 text-[10px] leading-relaxed text-slate-400">{hover || (props.focus ? "Numbered stops follow your Directions. Shared biology, not geography." : `${props.data.nodes.length.toLocaleString()} conditions · drag to turn · scroll to explore`)}</div>
    <div className="absolute bottom-4 right-4 flex flex-col overflow-hidden rounded-xl bg-slate-900/90 text-white ring-1 ring-white/15"><button className="px-3 py-2 hover:bg-white/10" aria-label="Zoom in" onClick={()=>zoom.current(1.5)}>+</button><button className="border-t border-white/10 px-3 py-2 hover:bg-white/10" aria-label="Zoom out" onClick={()=>zoom.current(1/1.5)}>−</button><button className="border-t border-white/10 px-3 py-2 text-xs hover:bg-white/10" aria-label="Reset globe view" onClick={()=>fly.current()}>↺</button></div>
  </div>;
}
