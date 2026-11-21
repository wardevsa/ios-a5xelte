// S7GE Lab, H1: the Metal bench. Five tests on the real Metal of this phone (HeroMetal + libhakiosair, the device "Mali-T880 (Panfrost) (Hakios)") into an
// OFF-SCREEN 512x512 BGRA texture, so that presentation is not in the numbers: (a) clear, (b) one triangle, (c) 48 overdrawn triangles, (d) a textured quad
// through a sampler, (e) a compute kernel that adds two vectors. Each one is CHECKED (a pixel read back, or the whole result vector) and TIMED (commit to
// waitUntilCompleted). The same (a)-(c) are timed through OpenGL ES (GLView.benchOffscreen) for comparison. The table goes to the screen and to
// /private/var/tmp/s7ge-bench.txt. Plain arm64 Swift, valid on a real iPhone.
import Metal
import UIKit

struct BenchRow {
    let api: String, name: String
    let ok: Bool
    let iterations: Int
    let totalMs: Double
    let note: String
    var msPerIteration: Double { return iterations > 0 ? totalMs / Double(iterations) : 0 }
    var perSecond: Double { return totalMs > 0 ? Double(iterations) * 1000 / totalMs : 0 }
    var line: String {
        return String(format: "%-6@ %-26@ %@  %5d it  %8.2f ms/it  %7.1f /s  %@", api as NSString, name as NSString, ok ? "PASS" : "FAIL", iterations, msPerIteration, perSecond, note as NSString)
    }
}

final class MetalBench {
    static let source = """
    #include <metal_stdlib>
    using namespace metal;
    struct VIn { packed_float2 position; packed_float4 color; };
    struct VOut { float4 position [[position]]; float4 color; };
    vertex VOut tri_vertex(const device VIn *v [[buffer(0)]], uint id [[vertex_id]]) { VOut o; o.position = float4(v[id].position, 0, 1); o.color = v[id].color; return o; }
    fragment float4 tri_fragment(VOut in [[stage_in]]) { return in.color; }
    struct QOut { float4 position [[position]]; float2 uv; };
    vertex QOut quad_vertex(uint id [[vertex_id]]) {
        float2 p = float2((id & 1) ? 1.0 : -1.0, (id & 2) ? 1.0 : -1.0);
        QOut o; o.position = float4(p, 0, 1); o.uv = (p + 1.0) * 0.5; return o;
    }
    fragment float4 quad_fragment(QOut in [[stage_in]], texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]]) { return t.sample(s, in.uv); }
    kernel void add_arrays(device const float *a [[buffer(0)]], device const float *b [[buffer(1)]], device float *r [[buffer(2)]], uint i [[thread_position_in_grid]]) { r[i] = a[i] + b[i]; }
    """
    static let size = 512

    let device: MTLDevice
    let queue: MTLCommandQueue
    var rows: [BenchRow] = []

    init?(device: MTLDevice) {
        guard let q = device.makeCommandQueue() else { return nil }
        self.device = device
        queue = q
    }

    private func target() -> MTLTexture? {
        let d = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .bgra8Unorm, width: MetalBench.size, height: MetalBench.size, mipmapped: false)
        d.usage = [.renderTarget, .shaderRead]
        d.storageMode = .shared
        return device.makeTexture(descriptor: d)
    }

    /// B, G, R, A of the middle pixel.
    private func center(_ t: MTLTexture) -> [UInt8] {
        var px = [UInt8](repeating: 0, count: 4)
        t.getBytes(&px, bytesPerRow: 4, from: MTLRegionMake2D(MetalBench.size / 2, MetalBench.size / 2, 1, 1), mipmapLevel: 0)
        return px
    }

    private func close(_ a: [UInt8], _ b: [UInt8], _ tolerance: Int = 3) -> Bool {
        return zip(a, b).allSatisfy { abs(Int($0) - Int($1)) <= tolerance }
    }

    /// Runs `body` (which must commit and wait) for about `seconds`, at least `minimum` times.
    private func timed(seconds: Double, minimum: Int, _ body: () -> Void) -> (Int, Double) {
        var n = 0
        let start = CACurrentMediaTime()
        var now = start
        while n < minimum || now - start < seconds {
            body()
            n += 1
            now = CACurrentMediaTime()
        }
        return (n, (now - start) * 1000)
    }

    private func finish(_ buffer: MTLCommandBuffer) -> Bool {
        buffer.commit()
        buffer.waitUntilCompleted()
        return buffer.status == .completed
    }

    func run(seconds: Double) {
        guard let rt = target() else { rows.append(BenchRow(api: "Metal", name: "render target", ok: false, iterations: 0, totalMs: 0, note: "no texture")); return }
        let clearPass: (MTLClearColor) -> MTLRenderPassDescriptor = { color in
            let p = MTLRenderPassDescriptor()
            p.colorAttachments[0].texture = rt
            p.colorAttachments[0].loadAction = .clear
            p.colorAttachments[0].storeAction = .store
            p.colorAttachments[0].clearColor = color
            return p
        }

        // (a) clear
        var okA = true
        let (nA, msA) = timed(seconds: seconds, minimum: 10) {
            guard let b = queue.makeCommandBuffer(), let e = b.makeRenderCommandEncoder(descriptor: clearPass(MTLClearColorMake(0.25, 0.5, 0.75, 1))) else { okA = false; return }
            e.endEncoding()
            okA = finish(b) && okA
        }
        let pA = center(rt)   // BGRA: 0.75 -> 191, 0.5 -> 128, 0.25 -> 64
        rows.append(BenchRow(api: "Metal", name: "a clear", ok: okA && close(pA, [191, 128, 64, 255]), iterations: nA, totalMs: msA, note: "centre BGRA \(pA)"))

        // pipelines from MSL text: compiled by the phone's own Metal compiler, then for the Mali by libhakiosair
        let library: MTLLibrary
        do { library = try device.makeLibrary(source: MetalBench.source, options: nil) } catch {
            rows.append(BenchRow(api: "Metal", name: "library from MSL", ok: false, iterations: 0, totalMs: 0, note: "\(error.localizedDescription)"))
            return
        }
        var triPipeline: MTLRenderPipelineState?, quadPipeline: MTLRenderPipelineState?, addPipeline: MTLComputePipelineState?
        var pipeNote = ""
        let t0 = CACurrentMediaTime()
        do {
            let d = MTLRenderPipelineDescriptor()
            d.vertexFunction = library.makeFunction(name: "tri_vertex"); d.fragmentFunction = library.makeFunction(name: "tri_fragment")
            d.colorAttachments[0].pixelFormat = .bgra8Unorm
            triPipeline = try device.makeRenderPipelineState(descriptor: d)
            let q = MTLRenderPipelineDescriptor()
            q.vertexFunction = library.makeFunction(name: "quad_vertex"); q.fragmentFunction = library.makeFunction(name: "quad_fragment")
            q.colorAttachments[0].pixelFormat = .bgra8Unorm
            quadPipeline = try device.makeRenderPipelineState(descriptor: q)
        } catch { pipeNote += " render: \(error.localizedDescription)" }
        do { if let f = library.makeFunction(name: "add_arrays") { addPipeline = try device.makeComputePipelineState(function: f) } } catch { pipeNote += " compute: \(error.localizedDescription)" }
        let compileMs = (CACurrentMediaTime() - t0) * 1000
        rows.append(BenchRow(api: "Metal", name: "pipelines (3) compile", ok: triPipeline != nil && quadPipeline != nil && addPipeline != nil, iterations: 1, totalMs: compileMs, note: pipeNote))

        // (b) one triangle, (c) 48 overdrawn: all red, covering the centre
        func triangles(_ count: Int, name: String) {
            guard let pipeline = triPipeline else { rows.append(BenchRow(api: "Metal", name: name, ok: false, iterations: 0, totalMs: 0, note: "no pipeline")); return }
            let v: [Float] = [0, 0.9, 1, 0, 0, 1,  -0.9, -0.9, 1, 0, 0, 1,  0.9, -0.9, 1, 0, 0, 1]
            var ok = true
            let (n, ms) = timed(seconds: seconds, minimum: 10) {
                guard let b = queue.makeCommandBuffer(), let e = b.makeRenderCommandEncoder(descriptor: clearPass(MTLClearColorMake(0, 0, 0, 1))) else { ok = false; return }
                e.setRenderPipelineState(pipeline)
                e.setVertexBytes(v, length: v.count * 4, index: 0)
                for _ in 0..<count { e.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3) }
                e.endEncoding()
                ok = finish(b) && ok
            }
            let p = center(rt)
            rows.append(BenchRow(api: "Metal", name: name, ok: ok && close(p, [0, 0, 255, 255]), iterations: n, totalMs: ms, note: "centre BGRA \(p)"))
        }
        triangles(1, name: "b 1 triangle")
        triangles(48, name: "c 48 overdrawn triangles")

        // (d) textured quad: a 256x256 horizontal gradient, red = x, blue = 255 - x; the middle samples to about (128, 0, 127)
        if let pipeline = quadPipeline {
            let td = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .rgba8Unorm, width: 256, height: 256, mipmapped: false)
            td.usage = .shaderRead; td.storageMode = .shared
            let sd = MTLSamplerDescriptor()
            sd.minFilter = .linear; sd.magFilter = .linear; sd.sAddressMode = .clampToEdge; sd.tAddressMode = .clampToEdge
            if let tex = device.makeTexture(descriptor: td), let sampler = device.makeSamplerState(descriptor: sd) {
                var data = [UInt8](repeating: 255, count: 256 * 256 * 4)
                for y in 0..<256 { for x in 0..<256 { let o = (y * 256 + x) * 4; data[o] = UInt8(x); data[o + 1] = 0; data[o + 2] = UInt8(255 - x) } }
                tex.replace(region: MTLRegionMake2D(0, 0, 256, 256), mipmapLevel: 0, withBytes: data, bytesPerRow: 256 * 4)
                var ok = true
                let (n, ms) = timed(seconds: seconds, minimum: 10) {
                    guard let b = queue.makeCommandBuffer(), let e = b.makeRenderCommandEncoder(descriptor: clearPass(MTLClearColorMake(0, 0, 0, 1))) else { ok = false; return }
                    e.setRenderPipelineState(pipeline)
                    e.setFragmentTexture(tex, index: 0)
                    e.setFragmentSamplerState(sampler, index: 0)
                    e.drawPrimitives(type: .triangleStrip, vertexStart: 0, vertexCount: 4)
                    e.endEncoding()
                    ok = finish(b) && ok
                }
                let p = center(rt)   // BGRA
                rows.append(BenchRow(api: "Metal", name: "d textured quad", ok: ok && close(p, [127, 0, 128, 255], 4), iterations: n, totalMs: ms, note: "centre BGRA \(p)"))
            } else {
                rows.append(BenchRow(api: "Metal", name: "d textured quad", ok: false, iterations: 0, totalMs: 0, note: "no texture or sampler"))
            }
        } else {
            rows.append(BenchRow(api: "Metal", name: "d textured quad", ok: false, iterations: 0, totalMs: 0, note: "no pipeline"))
        }

        // (e) compute: r = a + b over 4096 floats, the whole vector checked
        if let pipeline = addPipeline {
            let count = 4096
            let a = (0..<count).map { Float($0) }, bb = (0..<count).map { Float($0) * 0.5 }
            if let ba = device.makeBuffer(bytes: a, length: count * 4, options: []), let bbuf = device.makeBuffer(bytes: bb, length: count * 4, options: []),
               let br = device.makeBuffer(length: count * 4, options: []) {
                var ok = true
                let (n, ms) = timed(seconds: seconds, minimum: 10) {
                    guard let b = queue.makeCommandBuffer(), let e = b.makeComputeCommandEncoder() else { ok = false; return }
                    e.setComputePipelineState(pipeline)
                    e.setBuffer(ba, offset: 0, index: 0); e.setBuffer(bbuf, offset: 0, index: 1); e.setBuffer(br, offset: 0, index: 2)
                    e.dispatchThreads(MTLSize(width: count, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: min(pipeline.maxTotalThreadsPerThreadgroup, 64), height: 1, depth: 1))
                    e.endEncoding()
                    ok = finish(b) && ok
                }
                let out = br.contents().bindMemory(to: Float.self, capacity: count)
                var wrong = 0
                for i in 0..<count where out[i] != a[i] + bb[i] { wrong += 1 }
                rows.append(BenchRow(api: "Metal", name: "e compute add 4096", ok: ok && wrong == 0, iterations: n, totalMs: ms, note: "\(wrong) wrong of \(count)"))
            } else {
                rows.append(BenchRow(api: "Metal", name: "e compute add 4096", ok: false, iterations: 0, totalMs: 0, note: "no buffers"))
            }
        } else {
            rows.append(BenchRow(api: "Metal", name: "e compute add 4096", ok: false, iterations: 0, totalMs: 0, note: "no pipeline"))
        }
    }
}
