import { useEffect, useRef, useState } from "react";

const VERT = `attribute vec2 a_pos; void main(){ gl_Position = vec4(a_pos, 0.0, 1.0); }`;

const FRAG = `#extension GL_OES_standard_derivatives : enable
precision highp float;
uniform float u_time; uniform vec2 u_resolution; uniform vec2 u_mouse;
void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution.xy;
  vec2 p = uv * 2.0 - 1.0; p.x *= u_resolution.x / u_resolution.y;
  vec2 mouse = u_mouse / u_resolution.xy; if (length(u_mouse) < 1.0) { mouse = vec2(0.5, 0.6); }
  vec2 m = mouse * 2.0 - 1.0; m.x *= u_resolution.x / u_resolution.y;
  float t = u_time * 0.45;
  float mDist = length(p - m);
  float mWave = sin(mDist * 14.0 - t * 3.5) * exp(-mDist * 2.5) * 0.22;
  float mGlow = exp(-mDist * 2.8);
  float w1 = sin(p.x * 2.2 + t * 0.8 + sin(p.y * 1.8 + t * 0.6)) * 0.25;
  float w2 = cos(p.y * 2.5 - t * 0.7 + cos(p.x * 2.0 + t * 0.5)) * 0.22;
  float w3 = sin((p.x + p.y) * 3.0 + t * 1.2 + mWave * 4.0) * 0.14;
  float wave = w1 + w2 + w3 + mWave;
  vec3 colDeepSky = vec3(0.01, 0.48, 0.76); vec3 colLightSky = vec3(0.12, 0.62, 0.92);
  vec3 colBase = mix(colDeepSky, colLightSky, clamp(uv.y * 0.8 + wave * 0.15, 0.0, 1.0));
  float contour = sin(wave * 28.0 + t * 0.5);
  colBase = mix(colBase, vec3(0.40, 0.82, 0.98), smoothstep(0.96, 0.99, abs(contour)) * 0.25);
  vec2 aspectVec = vec2(u_resolution.x / u_resolution.y, 1.0);
  vec2 gridUV = (uv * 38.0 * aspectVec) + vec2(wave * 2.2);
  vec2 majorGrid = abs(fract(gridUV * 0.1 - 0.5) - 0.5) / fwidth(gridUV * 0.1);
  float majorLine = 1.0 - min(min(majorGrid.x, majorGrid.y), 1.0);
  vec2 minorGrid = abs(fract(gridUV - 0.5) - 0.5) / fwidth(gridUV);
  float minorLine = 1.0 - min(min(minorGrid.x, minorGrid.y), 1.0);
  float dotCircle = smoothstep(0.18, 0.08, length(fract(gridUV) - 0.5));
  colBase += vec3(0.20, 0.55, 0.85) * mGlow * 0.35;
  vec3 chalkWhite = vec3(0.95, 0.98, 1.0);
  colBase = mix(colBase, chalkWhite, minorLine * 0.08);
  colBase = mix(colBase, chalkWhite, majorLine * 0.16);
  colBase = mix(colBase, chalkWhite, dotCircle * 0.40);
  float grain = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453);
  colBase += (grain - 0.5) * 0.025;
  gl_FragColor = vec4(colBase, 1.0);
}`;

/** Fixed full-page WebGL blueprint grid. CSS grid fallback when WebGL is unavailable. */
export function BlueprintBackground(): JSX.Element {
  const ref = useRef<HTMLCanvasElement>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const gl = (canvas.getContext("webgl") ?? canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) { setFallback(true); return; }
    gl.getExtension("OES_standard_derivatives");
    const compile = (type: number, src: string): WebGLShader | null => {
      const s = gl.createShader(type);
      if (!s) return null;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
    };
    const vs = compile(gl.VERTEX_SHADER, VERT);
    const fs = compile(gl.FRAGMENT_SHADER, FRAG);
    const prog = gl.createProgram();
    if (!vs || !fs || !prog) { setFallback(true); return; }
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { setFallback(true); return; }
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const uTime = gl.getUniformLocation(prog, "u_time");
    const uRes = gl.getUniformLocation(prog, "u_resolution");
    const uMouse = gl.getUniformLocation(prog, "u_mouse");

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let mouse = [0, 0];
    let raf = 0;
    const t0 = performance.now();

    const draw = (): void => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const w = Math.max(1, Math.floor(window.innerWidth * dpr));
      const h = Math.max(1, Math.floor(window.innerHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      gl.viewport(0, 0, w, h);
      gl.uniform1f(uTime, reduced.matches ? 0 : (performance.now() - t0) / 1000);
      gl.uniform2f(uRes, w, h);
      gl.uniform2f(uMouse, mouse[0] * dpr, mouse[1] * dpr);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    const loop = (): void => { draw(); raf = requestAnimationFrame(loop); };
    const start = (): void => {
      cancelAnimationFrame(raf);
      const visible = document.visibilityState === "visible";
      if (reduced.matches || !visible) { if (visible) draw(); return; }
      raf = requestAnimationFrame(loop);
    };
    const onMove = (e: PointerEvent): void => { mouse = [e.clientX, window.innerHeight - e.clientY]; };
    const onResize = (): void => { if (reduced.matches) draw(); };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", start);
    reduced.addEventListener("change", start);
    start();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", start);
      reduced.removeEventListener("change", start);
    };
  }, []);

  return (
    <div aria-hidden="true" className={`fixed inset-0 -z-10 pointer-events-none ${fallback ? "blueprint-grid-subtle" : ""}`} style={{ backgroundColor: "#0284c7" }}>
      {!fallback && <canvas ref={ref} className="w-full h-full block" />}
    </div>
  );
}
