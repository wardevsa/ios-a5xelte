// S7GE Lab: what the graphics stack of this phone does, shown on its own screen, and a first OpenGL ES app through the project's EAGL bridge
// (EAGLContext -> OSMesa -> Panfrost -> the Mali-T880, docs/S7GE_EAGL_BRIDGES.md). UIKit only, no async, plain arm64.
//  - top half: a GLES2 triangle that turns, drawn by a CADisplayLink; the lines below say what the context and the renderer are, and the frames per second;
//  - the button "Probar Metal" calls MTLCreateSystemDefaultDevice() and shows what they return (if the app dies there, that is the result);
//  - the same text is appended to Documents/s7ge-lab.txt and to /private/var/tmp/s7ge-lab.txt for the PC.
import UIKit
import Metal
import OpenGLES

final class GLView: UIView {
    override class var layerClass: AnyClass { return CAEAGLLayer.self }
    private var context: EAGLContext?
    private var framebuffer: GLuint = 0
    private var renderbuffer: GLuint = 0
    private var program: GLuint = 0
    private var angleLocation: GLint = 0
    private var link: CADisplayLink?
    private var width: GLint = 0
    private var height: GLint = 0
    private var frames = 0
    private var clock = CACurrentMediaTime()
    private var angle: Float = 0
    private(set) var report = "GL: not started"
    private(set) var fps = 0.0
    private var heavy = false
    private(set) var fpsLight = 0.0
    private(set) var fpsHeavy = 0.0

    private func compile(_ type: GLenum, _ source: String) -> GLuint {
        let shader = glCreateShader(type)
        source.withCString { text in
            var pointer: UnsafePointer<GLchar>? = text
            glShaderSource(shader, 1, &pointer, nil)
        }
        glCompileShader(shader)
        var ok: GLint = 0
        glGetShaderiv(shader, GLenum(GL_COMPILE_STATUS), &ok)
        if ok == 0 {
            var log = [GLchar](repeating: 0, count: 512)
            glGetShaderInfoLog(shader, 512, nil, &log)
            report += "\nshader error: " + String(cString: log)
        }
        return shader
    }

    func start() {
        guard let eagl = layer as? CAEAGLLayer else { report = "GL: the layer is not a CAEAGLLayer"; return }
        eagl.isOpaque = true
        eagl.drawableProperties = [kEAGLDrawablePropertyRetainedBacking: false,
                                   kEAGLDrawablePropertyColorFormat: kEAGLColorFormatRGBA8]
        guard let ctx = EAGLContext(api: .openGLES2) else { report = "GL: EAGLContext(api: .openGLES2) returned nil"; return }
        guard EAGLContext.setCurrent(ctx) else { report = "GL: EAGLContext.setCurrent failed"; return }
        context = ctx
        glGenFramebuffers(1, &framebuffer)
        glGenRenderbuffers(1, &renderbuffer)
        glBindFramebuffer(GLenum(GL_FRAMEBUFFER), framebuffer)
        glBindRenderbuffer(GLenum(GL_RENDERBUFFER), renderbuffer)
        let storage = ctx.renderbufferStorage(Int(GL_RENDERBUFFER), from: eagl)
        glFramebufferRenderbuffer(GLenum(GL_FRAMEBUFFER), GLenum(GL_COLOR_ATTACHMENT0), GLenum(GL_RENDERBUFFER), renderbuffer)
        glGetRenderbufferParameteriv(GLenum(GL_RENDERBUFFER), GLenum(GL_RENDERBUFFER_WIDTH), &width)
        glGetRenderbufferParameteriv(GLenum(GL_RENDERBUFFER), GLenum(GL_RENDERBUFFER_HEIGHT), &height)
        let status = glCheckFramebufferStatus(GLenum(GL_FRAMEBUFFER))
        func text(_ name: Int32) -> String {
            if let p = glGetString(GLenum(name)) { return String(cString: p) }
            return "nil"
        }
        report = "GL: context ok, storage \(storage), \(width) x \(height), framebuffer status 0x\(String(status, radix: 16))\n"
            + "GL_RENDERER \(text(GL_RENDERER))\nGL_VERSION \(text(GL_VERSION))\nGL_VENDOR \(text(GL_VENDOR))"
        let vertex = "attribute vec2 pos; attribute vec3 col; uniform float a; varying vec3 c;\n"
            + "void main() { float s = sin(a), k = cos(a); gl_Position = vec4(pos.x * k - pos.y * s, pos.x * s + pos.y * k, 0.0, 1.0); c = col; }"
        let fragment = "precision mediump float; varying vec3 c; void main() { gl_FragColor = vec4(c, 1.0); }"
        program = glCreateProgram()
        glAttachShader(program, compile(GLenum(GL_VERTEX_SHADER), vertex))
        glAttachShader(program, compile(GLenum(GL_FRAGMENT_SHADER), fragment))
        glBindAttribLocation(program, 0, "pos")
        glBindAttribLocation(program, 1, "col")
        glLinkProgram(program)
        var linked: GLint = 0
        glGetProgramiv(program, GLenum(GL_LINK_STATUS), &linked)
        report += "\nprogram linked \(linked)"
        angleLocation = glGetUniformLocation(program, "a")
        link = CADisplayLink(target: self, selector: #selector(drawFrame))
        link?.add(to: .main, forMode: .common)
    }


    /// H1: pause or resume the on-screen GL animation, so that the bench is alone on the GPU.
    func setPaused(_ paused: Bool) { link?.isPaused = paused }

    /// H1: the same (a) clear, (b) one triangle, (c) 48 overdrawn triangles as the Metal bench, off screen at 512x512, each frame ended by glFinish.
    /// kind 0 = clear, 1 = one triangle, 48 = that many. Returns (iterations, ms, centre RGBA) or nil when there is no context.
    func benchOffscreen(kind: Int, seconds: Double) -> (Int, Double, [UInt8])? {
        guard let ctx = context else { return nil }
        EAGLContext.setCurrent(ctx)
        var fbo: GLuint = 0, rb: GLuint = 0
        glGenFramebuffers(1, &fbo); glGenRenderbuffers(1, &rb)
        glBindFramebuffer(GLenum(GL_FRAMEBUFFER), fbo); glBindRenderbuffer(GLenum(GL_RENDERBUFFER), rb)
        glRenderbufferStorage(GLenum(GL_RENDERBUFFER), GLenum(GL_RGBA8_OES), 512, 512)
        glFramebufferRenderbuffer(GLenum(GL_FRAMEBUFFER), GLenum(GL_COLOR_ATTACHMENT0), GLenum(GL_RENDERBUFFER), rb)
        glViewport(0, 0, 512, 512)
        glUseProgram(program)
        glUniform1f(angleLocation, 0)
        let vertices: [Float] = [0, 0.9, 1, 0, 0, -0.9, -0.9, 1, 0, 0, 0.9, -0.9, 1, 0, 0]
        var n = 0
        let start = CACurrentMediaTime()
        var now = start
        while n < 10 || now - start < seconds {
            if kind == 0 { glClearColor(0.25, 0.5, 0.75, 1) } else { glClearColor(0, 0, 0, 1) }
            glClear(GLbitfield(GL_COLOR_BUFFER_BIT))
            if kind > 0 {
                vertices.withUnsafeBufferPointer { buffer in
                    let base = UnsafeRawPointer(buffer.baseAddress!)
                    glVertexAttribPointer(0, 2, GLenum(GL_FLOAT), GLboolean(GL_FALSE), 20, base)
                    glVertexAttribPointer(1, 3, GLenum(GL_FLOAT), GLboolean(GL_FALSE), 20, base.advanced(by: 8))
                    glEnableVertexAttribArray(0); glEnableVertexAttribArray(1)
                    for _ in 0..<kind { glDrawArrays(GLenum(GL_TRIANGLES), 0, 3) }
                }
            }
            glFinish()
            n += 1
            now = CACurrentMediaTime()
        }
        var px = [UInt8](repeating: 0, count: 4)
        glReadPixels(256, 256, 1, 1, GLenum(GL_RGBA), GLenum(GL_UNSIGNED_BYTE), &px)
        glBindFramebuffer(GLenum(GL_FRAMEBUFFER), 0); glBindRenderbuffer(GLenum(GL_RENDERBUFFER), 0)
        glDeleteFramebuffers(1, &fbo); glDeleteRenderbuffers(1, &rb)
        return (n, (now - start) * 1000, px)
    }

    @objc private func drawFrame() {
        guard let ctx = context else { return }
        EAGLContext.setCurrent(ctx)
        angle += 0.03
        glBindFramebuffer(GLenum(GL_FRAMEBUFFER), framebuffer)
        glViewport(0, 0, width, height)
        glClearColor(0.05, 0.05, 0.12 + 0.08 * sin(angle), 1)
        glClear(GLbitfield(GL_COLOR_BUFFER_BIT))
        glUseProgram(program)
        glUniform1f(angleLocation, angle)
        let vertices: [Float] = [0, 0.7, 1, 0.2, 0.2, -0.65, -0.5, 0.2, 1, 0.2, 0.65, -0.5, 0.2, 0.4, 1]
        vertices.withUnsafeBufferPointer { buffer in
            let base = UnsafeRawPointer(buffer.baseAddress!)
            glVertexAttribPointer(0, 2, GLenum(GL_FLOAT), GLboolean(GL_FALSE), 20, base)
            glVertexAttribPointer(1, 3, GLenum(GL_FLOAT), GLboolean(GL_FALSE), 20, base.advanced(by: 8))
            glEnableVertexAttribArray(0)
            glEnableVertexAttribArray(1)
            for _ in 0..<(heavy ? 48 : 1) { glDrawArrays(GLenum(GL_TRIANGLES), 0, 3) }
        }
        glBindRenderbuffer(GLenum(GL_RENDERBUFFER), renderbuffer)
        ctx.presentRenderbuffer(Int(GL_RENDERBUFFER))
        frames += 1
        let now = CACurrentMediaTime()
        if now - clock >= 2 {
            fps = Double(frames) / (now - clock)
            if heavy { fpsHeavy = fps } else { fpsLight = fps }
            heavy.toggle()
            frames = 0
            clock = now
        }
    }
}


/// S7GE M1: a strip whose colour is cleared and presented through Metal (a CAMetalLayer, a command queue, a render pass that clears), at the display's rate.
final class MetalStrip: UIView {
    override class var layerClass: AnyClass { return CAMetalLayer.self }
    private let queue: MTLCommandQueue
    private var link: CADisplayLink?
    private(set) var frames = 0
    func setPaused(_ paused: Bool) { link?.isPaused = paused }
    private var phase: Double = 0
    private let device: MTLDevice
    private var pipeline: MTLRenderPipelineState?
    private(set) var triangle = "Metal triangle: not set up"
    private static let source = """
    #include <metal_stdlib>
    using namespace metal;
    struct VIn { packed_float2 position; packed_float4 color; };
    struct VOut { float4 position [[position]]; float4 color; };
    vertex VOut tri_vertex(const device VIn *v [[buffer(0)]], uint id [[vertex_id]]) { VOut o; o.position = float4(v[id].position, 0, 1); o.color = v[id].color; return o; }
    fragment float4 tri_fragment(VOut in [[stage_in]]) { return in.color; }
    """
    init?(device: MTLDevice) {
        guard let q = device.makeCommandQueue() else { return nil }
        queue = q
        self.device = device
        super.init(frame: .zero)
        let metal = layer as! CAMetalLayer
        metal.device = device
        metal.pixelFormat = .bgra8Unorm
        metal.framebufferOnly = false
        do {
            let library = try device.makeLibrary(source: MetalStrip.source, options: nil)
            let d = MTLRenderPipelineDescriptor()
            d.vertexFunction = library.makeFunction(name: "tri_vertex")
            d.fragmentFunction = library.makeFunction(name: "tri_fragment")
            d.colorAttachments[0].pixelFormat = .bgra8Unorm
            pipeline = try device.makeRenderPipelineState(descriptor: d)
            triangle = "Metal triangle: pipeline ok"
        } catch {
            triangle = "Metal triangle: \(error.localizedDescription)"
        }
        link = CADisplayLink(target: self, selector: #selector(tick))
        link?.add(to: .main, forMode: .common)
    }
    required init?(coder: NSCoder) { fatalError() }
    override func layoutSubviews() {
        super.layoutSubviews()
        (layer as! CAMetalLayer).drawableSize = CGSize(width: bounds.width * contentScaleFactor, height: bounds.height * contentScaleFactor)
    }
    @objc private func tick() {
        let metal = layer as! CAMetalLayer
        guard let drawable = metal.nextDrawable(), let buffer = queue.makeCommandBuffer() else { return }
        phase += 0.04
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = drawable.texture
        pass.colorAttachments[0].loadAction = .clear
        pass.colorAttachments[0].storeAction = .store
        pass.colorAttachments[0].clearColor = MTLClearColor(red: 0.5 + 0.5 * sin(phase), green: 0.5 + 0.5 * sin(phase + 2.1), blue: 0.5 + 0.5 * sin(phase + 4.2), alpha: 1)
        let encoder = buffer.makeRenderCommandEncoder(descriptor: pass)
        if let pipeline = pipeline, let encoder = encoder {
            let a = Float(phase)
            func vertex(_ k: Float, _ r: Float, _ g: Float, _ b: Float) -> [Float] {
                let angle = a + k * 2.0944
                return [0.8 * cos(angle + 1.5708), 0.8 * sin(angle + 1.5708), r, g, b, 1]
            }
            let vertices = vertex(0, 1, 0.1, 0.1) + vertex(1, 0.1, 1, 0.1) + vertex(2, 0.1, 0.3, 1)
            encoder.setRenderPipelineState(pipeline)
            encoder.setVertexBytes(vertices, length: vertices.count * 4, index: 0)
            encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
        }
        encoder?.endEncoding()
        buffer.present(drawable)
        buffer.commit()
        frames += 1
    }
}

final class LabController: UIViewController {
    private let gl = GLView()
    private let text = UITextView()
    private var metal = "Metal: not tried (press the button)"
    private var strip: MetalStrip?
    private var timer: Timer?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        gl.frame = CGRect(x: 0, y: 44, width: view.bounds.width, height: view.bounds.height * 0.42)
        gl.autoresizingMask = [.flexibleWidth, .flexibleBottomMargin]
        view.addSubview(gl)
        let button = UIButton(type: .system)
        button.setTitle("Probar Metal", for: .normal)
        button.frame = CGRect(x: 12, y: gl.frame.maxY + 4, width: 160, height: 36)
        button.addTarget(self, action: #selector(tryMetal), for: .touchUpInside)
        view.addSubview(button)
        let benchButton = UIButton(type: .system)
        benchButton.setTitle("Banco Metal", for: .normal)
        benchButton.frame = CGRect(x: 12, y: button.frame.maxY + 2, width: 160, height: 36)
        benchButton.addTarget(self, action: #selector(runBench), for: .touchUpInside)
        view.addSubview(benchButton)
        text.frame = CGRect(x: 8, y: benchButton.frame.maxY + 4, width: view.bounds.width - 16, height: view.bounds.height - benchButton.frame.maxY - 8)
        text.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        text.backgroundColor = .black
        text.textColor = .green
        text.font = UIFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        text.isEditable = false
        view.addSubview(text)
        gl.start()
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.refresh() }
    }

    @objc private func tryMetal() {
        metal = "Metal: calling MTLCreateSystemDefaultDevice()..."
        refresh()
        if let device = MTLCreateSystemDefaultDevice() {
            metal = "Metal: device \(device.name), max threads \(device.maxThreadsPerThreadgroup), unified memory \(device.hasUnifiedMemory)"
            if strip == nil, let s = MetalStrip(device: device) {
                s.frame = CGRect(x: 180, y: gl.frame.maxY + 2, width: 150, height: 70)
                view.addSubview(s)
                strip = s
            }
        } else {
            metal = "Metal: MTLCreateSystemDefaultDevice() = nil"
        }
        refresh()
    }

    private var benchText = ""

    @objc private func runBench() {
        guard let device = MTLCreateSystemDefaultDevice(), let probe = MetalBench(device: device) else { benchText = "Banco Metal: no hay dispositivo"; refresh(); return }
        _ = probe
        benchText = "Banco Metal H1b: en marcha (tres pasadas y la presentacion, unos 70 s, la pantalla se queda quieta)..."
        refresh()
        gl.setPaused(true); strip?.setPaused(true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
            guard let self = self else { return }
            let seconds = 1.5, passes = 3
            var order: [String] = [], samples: [String: [BenchRow]] = [:]
            func add(_ r: BenchRow) {
                let key = r.api + " " + r.name
                if samples[key] == nil { order.append(key) }
                samples[key, default: []].append(r)
            }
            for _ in 0..<passes {
                guard let bench = MetalBench(device: device) else { break }
                bench.run(seconds: seconds)
                bench.rows.forEach(add)
                for (kind, name) in [(0, "a clear"), (1, "b 1 triangle"), (48, "c 48 overdrawn triangles")] {
                    if let (n, ms, px) = self.gl.benchOffscreen(kind: kind, seconds: seconds) {
                        let expect: [UInt8] = kind == 0 ? [64, 128, 191, 255] : [255, 0, 0, 255]   // RGBA
                        let ok = zip(px, expect).allSatisfy { abs(Int($0) - Int($1)) <= 3 }
                        add(BenchRow(api: "GLES", name: name, ok: ok, iterations: n, totalMs: ms, note: "centre RGBA \(px)"))
                    } else {
                        add(BenchRow(api: "GLES", name: name, ok: false, iterations: 0, totalMs: 0, note: "no context"))
                    }
                }
            }
            // presentation, full screen, at the panel's pixel size
            let pv = PresentView(frame: self.view.bounds)
            self.view.addSubview(pv)
            if let bench = MetalBench(device: device) { add(bench.presentTest(view: pv, seconds: 4)) }
            pv.removeFromSuperview()
            var lines = ["Banco Metal H1b (512x512 fuera de pantalla, \(seconds) s por prueba, \(passes) pasadas; ms/it = commit a waitUntilCompleted, o glFinish)", "device \(device.name)",
                         "prueba                              todas  ms/it min / media / max    /s (media)"]
            var passed = 0
            for key in order {
                let rs = samples[key]!
                let ms = rs.map { $0.msPerIteration }, ok = rs.allSatisfy { $0.ok }
                if ok { passed += 1 }
                let mean = ms.reduce(0, +) / Double(ms.count)
                lines.append(String(format: "%-34@ %@ %9.2f / %8.2f / %8.2f  %8.1f  %@", key as NSString, (ok ? "PASS" : "FAIL") as NSString, ms.min() ?? 0, mean, ms.max() ?? 0, mean > 0 ? 1000 / mean : 0, rs.last!.note as NSString))
            }
            lines.append("PASS \(passed) de \(order.count)")
            self.benchText = lines.joined(separator: "\n")
            if let data = (self.benchText + "\n---\n").data(using: .utf8) {
                let path = "/private/var/tmp/s7ge-bench.txt"
                if let handle = FileHandle(forWritingAtPath: path) { handle.seekToEndOfFile(); handle.write(data); handle.closeFile() }
                else { FileManager.default.createFile(atPath: path, contents: data, attributes: [.posixPermissions: 0o666]) }
            }
            self.gl.setPaused(false); self.strip?.setPaused(false)
            self.refresh()
        }
    }

    private func refresh() {
        let s = UIScreen.main
        var lines = ["\(UIDevice.current.model), iOS \(UIDevice.current.systemVersion)",
                     "screen \(s.bounds.width) x \(s.bounds.height) pt @\(s.scale), native \(s.nativeBounds.width) x \(s.nativeBounds.height)",
                     "safe area \(view.safeAreaInsets.top) \(view.safeAreaInsets.bottom)",
                     "Metal strip frames \(strip?.frames ?? -1); \(strip?.triangle ?? "no strip")",
                     String(format: "frames %.1f per second (1 triangle %.1f, 48 overdrawn triangles %.1f)", gl.fps, gl.fpsLight, gl.fpsHeavy), "", gl.report, "", metal, "", benchText]
        lines.append("")
        text.text = lines.joined(separator: "\n")
        let shown = text.text ?? ""
        if let data = (shown + "\n---\n").data(using: .utf8) {
            for path in ["/private/var/tmp/s7ge-lab.txt"] {
                if let handle = FileHandle(forWritingAtPath: path) {
                    handle.seekToEndOfFile()
                    handle.write(data)
                    handle.closeFile()
                } else {
                    FileManager.default.createFile(atPath: path, contents: data, attributes: [.posixPermissions: 0o666])
                }
            }
        }
    }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ app: UIApplication,
                     didFinishLaunchingWithOptions opts: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let w = UIWindow(frame: UIScreen.main.bounds)
        w.rootViewController = LabController()
        w.makeKeyAndVisible()
        window = w
        return true
    }
}
