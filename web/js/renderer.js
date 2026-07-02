/* renderer.js - WebGL 렌더러 (전역 Renderer) */
(function () {
  'use strict';

  const VS = `
attribute vec3 aPos;
attribute vec4 aCol;
attribute vec2 aUV;
uniform mat4 uProj;
uniform mat4 uView;
uniform mat4 uModel;
varying vec4 vCol;
varying vec2 vUV;
varying float vDist;
void main() {
  vec4 world = uModel * vec4(aPos, 1.0);
  vec4 viewPos = uView * world;
  vDist = length(viewPos.xyz);
  vCol = aCol;
  vUV = aUV;
  gl_Position = uProj * viewPos;
}`;

  const FS = `
precision mediump float;
varying vec4 vCol;
varying vec2 vUV;
varying float vDist;
uniform sampler2D uTex;
uniform float uAmbient;
uniform vec4 uTint;
uniform vec3 uFogColor;
uniform float uFogDensity;
void main() {
  vec4 t = texture2D(uTex, vUV);
  if (t.a < 0.1) discard;          // 잎/식물 알파 컷아웃
  vec3 c = t.rgb * vCol.rgb * uTint.rgb * uAmbient;
  float fog = clamp(exp(-vDist * uFogDensity), 0.0, 1.0);
  c = mix(uFogColor, c, fog);
  gl_FragColor = vec4(c, t.a * vCol.a * uTint.a);
}`;

  class Renderer {
    constructor(canvas) {
      this.canvas = canvas;
      const gl = canvas.getContext('webgl', { antialias: false,
        powerPreference: 'high-performance' });
      if (!gl) throw new Error('WebGL 미지원 브라우저입니다.');
      this.gl = gl;

      const compile = (type, src) => {
        const sh = gl.createShader(type);
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
          throw new Error(gl.getShaderInfoLog(sh));
        }
        return sh;
      };
      const prog = gl.createProgram();
      gl.attachShader(prog, compile(gl.VERTEX_SHADER, VS));
      gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(prog));
      }
      gl.useProgram(prog);
      this.prog = prog;
      this.aPos = gl.getAttribLocation(prog, 'aPos');
      this.aCol = gl.getAttribLocation(prog, 'aCol');
      this.aUV = gl.getAttribLocation(prog, 'aUV');
      this.uTex = gl.getUniformLocation(prog, 'uTex');
      this.uProj = gl.getUniformLocation(prog, 'uProj');
      this.uView = gl.getUniformLocation(prog, 'uView');
      this.uModel = gl.getUniformLocation(prog, 'uModel');
      this.uAmbient = gl.getUniformLocation(prog, 'uAmbient');
      this.uTint = gl.getUniformLocation(prog, 'uTint');
      this.uFogColor = gl.getUniformLocation(prog, 'uFogColor');
      this.uFogDensity = gl.getUniformLocation(prog, 'uFogDensity');

      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      // 뒤집힌 면도 그린다 (winding 안전)
      gl.disable(gl.CULL_FACE);

      this.identity = U.mat4Identity();
      this._initCube();
      this.resize();
    }

    /** 절차적 아틀라스 캔버스를 GL 텍스처로 업로드 (최근접 필터) */
    setAtlas(canvas) {
      const gl = this.gl;
      const tex = gl.createTexture();
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA,
                    gl.UNSIGNED_BYTE, canvas);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.uniform1i(this.uTex, 0);
      this.atlasTex = tex;
    }

    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.floor(this.canvas.clientWidth * dpr);
      const h = Math.floor(this.canvas.clientHeight * dpr);
      if (this.canvas.width !== w || this.canvas.height !== h) {
        this.canvas.width = w;
        this.canvas.height = h;
        this.gl.viewport(0, 0, w, h);
      }
      this.aspect = w / Math.max(1, h);
    }

    // ---------- 청크 버퍼 ----------
    uploadChunk(chunk, mesh) {
      this.deleteChunk(chunk);
      const gl = this.gl;
      const make = (data) => {
        if (!data) return null;
        const vp = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, vp);
        gl.bufferData(gl.ARRAY_BUFFER, data.pos, gl.STATIC_DRAW);
        const vc = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, vc);
        gl.bufferData(gl.ARRAY_BUFFER, data.col, gl.STATIC_DRAW);
        const vt = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, vt);
        gl.bufferData(gl.ARRAY_BUFFER, data.uv, gl.STATIC_DRAW);
        return { vp, vc, vt, count: data.pos.length / 3 };
      };
      chunk.gpu = { solid: make(mesh.solid), alpha: make(mesh.alpha) };
    }
    deleteChunk(chunk) {
      if (!chunk.gpu) return;
      const gl = this.gl;
      for (const part of ['solid', 'alpha']) {
        const b = chunk.gpu[part];
        if (b) {
          gl.deleteBuffer(b.vp); gl.deleteBuffer(b.vc);
          gl.deleteBuffer(b.vt);
        }
      }
      chunk.gpu = null;
    }

    _bind(buf) {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, buf.vp);
      gl.enableVertexAttribArray(this.aPos);
      gl.vertexAttribPointer(this.aPos, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf.vc);
      gl.enableVertexAttribArray(this.aCol);
      gl.vertexAttribPointer(this.aCol, 4, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf.vt);
      gl.enableVertexAttribArray(this.aUV);
      gl.vertexAttribPointer(this.aUV, 2, gl.FLOAT, false, 0, 0);
    }

    // ---------- 엔티티 큐브 (몹/드롭/투사체) ----------
    _initCube() {
      const gl = this.gl;
      const pos = [], col = [], uvs = [];
      const FACES = [
        [0, 1, 0, [[0,1,0],[0,1,1],[1,1,1],[1,1,0]], 1.0],
        [0, -1, 0, [[0,0,0],[1,0,0],[1,0,1],[0,0,1]], .45],
        [1, 0, 0, [[1,0,0],[1,1,0],[1,1,1],[1,0,1]], .8],
        [-1, 0, 0, [[0,0,1],[0,1,1],[0,1,0],[0,0,0]], .8],
        [0, 0, 1, [[1,0,1],[1,1,1],[0,1,1],[0,0,1]], .65],
        [0, 0, -1, [[0,0,0],[0,1,0],[1,1,0],[1,0,0]], .65],
      ];
      for (const [,, , corners, s] of FACES) {
        for (const o of [0, 1, 2, 0, 2, 3]) {
          const c = corners[o];
          pos.push(c[0] - .5, c[1] - .5, c[2] - .5);  // 중심 기준 단위 큐브
          col.push(s, s, s, 1);
          uvs.push(0.03125, 1 - 0.03125);             // 0번 흰 타일 중앙
        }
      }
      this.cube = {
        vp: gl.createBuffer(), vc: gl.createBuffer(),
        vt: gl.createBuffer(), count: pos.length / 3,
      };
      gl.bindBuffer(gl.ARRAY_BUFFER, this.cube.vp);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(pos), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.cube.vc);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(col), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.cube.vt);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(uvs), gl.STATIC_DRAW);
    }

    drawCube(x, y, z, sx, sy, sz, yaw, r, g, b, a) {
      const gl = this.gl;
      this._bind(this.cube);
      gl.uniformMatrix4fv(this.uModel, false,
        U.mat4Model(x, y, z, sx, sy, sz, yaw));
      gl.uniform4f(this.uTint, r, g, b, a === undefined ? 1 : a);
      gl.drawArrays(gl.TRIANGLES, 0, this.cube.count);
    }

    // ---------- 프레임 ----------
    beginFrame(camPos, yaw, pitch, fovDeg, sky, ambient, fogDensity) {
      const gl = this.gl;
      this.resize();
      gl.clearColor(sky[0], sky[1], sky[2], 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      const proj = U.mat4Perspective(fovDeg * Math.PI / 180, this.aspect,
                                     0.08, 300);
      const view = U.mat4View(camPos, yaw, pitch);
      gl.uniformMatrix4fv(this.uProj, false, proj);
      gl.uniformMatrix4fv(this.uView, false, view);
      gl.uniform1f(this.uAmbient, ambient);
      gl.uniform3f(this.uFogColor, sky[0], sky[1], sky[2]);
      gl.uniform1f(this.uFogDensity, fogDensity);
      gl.uniform4f(this.uTint, 1, 1, 1, 1);
      gl.uniformMatrix4fv(this.uModel, false, this.identity);
    }

    drawChunks(chunks) {
      const gl = this.gl;
      gl.uniformMatrix4fv(this.uModel, false, this.identity);
      gl.uniform4f(this.uTint, 1, 1, 1, 1);
      // 1) 불투명
      for (const c of chunks.values()) {
        if (c.gpu && c.gpu.solid) {
          this._bind(c.gpu.solid);
          gl.drawArrays(gl.TRIANGLES, 0, c.gpu.solid.count);
        }
      }
    }
    drawAlphaChunks(chunks) {
      const gl = this.gl;
      gl.uniformMatrix4fv(this.uModel, false, this.identity);
      gl.uniform4f(this.uTint, 1, 1, 1, 1);
      gl.depthMask(false);
      for (const c of chunks.values()) {
        if (c.gpu && c.gpu.alpha) {
          this._bind(c.gpu.alpha);
          gl.drawArrays(gl.TRIANGLES, 0, c.gpu.alpha.count);
        }
      }
      gl.depthMask(true);
    }
  }

  window.Renderer = Renderer;
})();
