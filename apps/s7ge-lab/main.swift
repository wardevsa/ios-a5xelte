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
        text.frame = CGRect(x: 8, y: button.frame.maxY + 4, width: view.bounds.width - 16, height: view.bounds.height - button.frame.maxY - 8)
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

    private func refresh() {
        let s = UIScreen.main
        var lines = ["\(UIDevice.current.model), iOS \(UIDevice.current.systemVersion)",
                     "screen \(s.bounds.width) x \(s.bounds.height) pt @\(s.scale), native \(s.nativeBounds.width) x \(s.nativeBounds.height)",
                     "safe area \(view.safeAreaInsets.top) \(view.safeAreaInsets.bottom)",
                     "Metal strip frames \(strip?.frames ?? -1); \(strip?.triangle ?? "no strip")",
                     String(format: "frames %.1f per second (1 triangle %.1f, 48 overdrawn triangles %.1f)", gl.fps, gl.fpsLight, gl.fpsHeavy), "", gl.report, "", metal]
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
