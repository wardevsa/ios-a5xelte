// S7GE Net: where does the network of this phone stop? Wi-Fi is up at the link (E-0386) and Safari still says "no connection", with 32
// "connectx() - failed necp_set_socket_domain_attributes" and sandbox denials in the kernel log (E-0371). Each step below isolates one layer and
// writes its errno/error, so that the next step is chosen from data:
//   1. the interfaces (getifaddrs): is en0 up, with an address?
//   2. DNS through the system resolver (getaddrinfo): example.com and neverssl.com; and a numeric address (no DNS at all)
//   3. TCP to numeric addresses of three different providers (no DNS): connect time or errno
//   4. DNS over UDP straight to 8.8.8.8 and 1.1.1.1 (no mDNSResponder): is there a reply, how many answers
//   5. URLSession over HTTP to a numeric address and to neverssl.com; then HTTPS to example.com (TLS, trustd)
// The text goes on screen and to /private/var/tmp/s7ge-net.txt. Plain arm64 UIKit, valid on a real iPhone.
import UIKit
import Darwin
import Foundation

enum Probe {
    static func now() -> Double { return CFAbsoluteTimeGetCurrent() }

    static func interfaces() -> [String] {
        var out: [String] = []
        var list: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&list) == 0, let first = list else { return ["getifaddrs failed errno \(errno)"] }
        defer { freeifaddrs(list) }
        var p: UnsafeMutablePointer<ifaddrs>? = first
        while let a = p?.pointee {
            if let addr = a.ifa_addr, addr.pointee.sa_family == UInt8(AF_INET) {
                var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                getnameinfo(addr, socklen_t(addr.pointee.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST)
                let flags = a.ifa_flags
                out.append("\(String(cString: a.ifa_name)) \(String(cString: host)) \((flags & UInt32(IFF_UP)) != 0 ? "UP" : "down")\((flags & UInt32(IFF_RUNNING)) != 0 ? " RUNNING" : "")")
            }
            p = a.ifa_next
        }
        return out.isEmpty ? ["no IPv4 interface"] : out
    }

    static func resolve(_ name: String) -> String {
        var hints = addrinfo(); hints.ai_family = AF_INET; hints.ai_socktype = SOCK_STREAM
        var res: UnsafeMutablePointer<addrinfo>?
        let t = now()
        let rc = getaddrinfo(name, "80", &hints, &res)
        let ms = (now() - t) * 1000
        if rc != 0 { return String(format: "getaddrinfo(%@) FAILED rc %d \"%@\" errno %d in %.0f ms", name, rc, String(cString: gai_strerror(rc)), errno, ms) }
        var addrs: [String] = []
        var q = res
        while let r = q?.pointee, addrs.count < 4 {
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            getnameinfo(r.ai_addr, r.ai_addrlen, &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST)
            addrs.append(String(cString: host)); q = r.ai_next
        }
        freeaddrinfo(res)
        return String(format: "getaddrinfo(%@) ok in %.0f ms: %@", name, ms, addrs.joined(separator: " "))
    }

    static func sockaddr4(_ ip: String, _ port: UInt16) -> sockaddr_in {
        var a = sockaddr_in(); a.sin_len = UInt8(MemoryLayout<sockaddr_in>.size); a.sin_family = sa_family_t(AF_INET); a.sin_port = port.bigEndian
        inet_pton(AF_INET, ip, &a.sin_addr); return a
    }

    static func tcp(_ ip: String, _ port: UInt16) -> String {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        if fd < 0 { return "tcp \(ip):\(port) socket() FAILED errno \(errno) \(String(cString: strerror(errno)))" }
        defer { close(fd) }
        _ = fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK)
        var a = sockaddr4(ip, port)
        let t = now()
        let rc = withUnsafePointer(to: &a) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        if rc == 0 { return String(format: "tcp %@:%d connected at once in %.0f ms", ip, Int(port), (now() - t) * 1000) }
        if errno != EINPROGRESS { return "tcp \(ip):\(port) connect() FAILED errno \(errno) \(String(cString: strerror(errno)))" }
        var pfd = pollfd(fd: fd, events: Int16(POLLOUT), revents: 0)
        let pr = poll(&pfd, 1, 6000)
        let ms = (now() - t) * 1000
        if pr == 0 { return String(format: "tcp %@:%d TIMEOUT after %.0f ms (no answer)", ip, Int(port), ms) }
        var err: Int32 = 0; var len = socklen_t(MemoryLayout<Int32>.size)
        getsockopt(fd, SOL_SOCKET, SO_ERROR, &err, &len)
        return err == 0 ? String(format: "tcp %@:%d CONNECTED in %.0f ms", ip, Int(port), ms) : String(format: "tcp %@:%d refused/failed errno %d %@ in %.0f ms", ip, Int(port), err, String(cString: strerror(err)), ms)
    }

    static func dnsOverUDP(_ server: String) -> String {
        let fd = socket(AF_INET, SOCK_DGRAM, 0)
        if fd < 0 { return "udp dns \(server) socket() FAILED errno \(errno)" }
        defer { close(fd) }
        var tv = timeval(tv_sec: 3, tv_usec: 0)
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
        var q: [UInt8] = [0x12, 0x34, 0x01, 0x00, 0, 1, 0, 0, 0, 0, 0, 0]
        for label in "example.com".split(separator: ".") { q.append(UInt8(label.count)); q += Array(label.utf8) }
        q += [0, 0, 1, 0, 1]
        var a = sockaddr4(server, 53)
        let t = now()
        let sent = withUnsafePointer(to: &a) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sendto(fd, q, q.count, 0, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        if sent < 0 { return "udp dns \(server) sendto() FAILED errno \(errno) \(String(cString: strerror(errno)))" }
        var buf = [UInt8](repeating: 0, count: 512)
        let n = recv(fd, &buf, buf.count, 0)
        let ms = (now() - t) * 1000
        if n < 12 { return String(format: "udp dns %@ NO REPLY (recv %d errno %d) after %.0f ms", server, n, errno, ms) }
        return String(format: "udp dns %@ reply %d bytes in %.0f ms: rcode %d, answers %d", server, n, ms, Int(buf[3] & 0x0f), Int(buf[6]) << 8 | Int(buf[7]))
    }

    static func http(_ url: String) -> String {
        guard let u = URL(string: url) else { return "bad url" }
        var request = URLRequest(url: u); request.timeoutInterval = 12
        let sem = DispatchSemaphore(value: 0)
        var result = ""
        let t = now()
        URLSession(configuration: .ephemeral).dataTask(with: request) { data, response, error in
            let ms = (now() - t) * 1000
            if let e = error as NSError? { result = String(format: "GET %@ ERROR %@ %d \"%@\" in %.0f ms", url, e.domain, e.code, e.localizedDescription, ms) }
            else if let h = response as? HTTPURLResponse { result = String(format: "GET %@ HTTP %d, %d bytes in %.0f ms", url, h.statusCode, data?.count ?? 0, ms) }
            else { result = "GET \(url) no response" }
            sem.signal()
        }.resume()
        if sem.wait(timeout: .now() + 20) == .timedOut { return "GET \(url) no callback in 20 s" }
        return result
    }
}

final class NetController: UIViewController {
    private let text = UITextView()
    private var running = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        let button = UIButton(type: .system)
        button.setTitle("Repetir", for: .normal)
        button.frame = CGRect(x: 12, y: 50, width: 120, height: 36)
        button.addTarget(self, action: #selector(run), for: .touchUpInside)
        view.addSubview(button)
        text.frame = CGRect(x: 8, y: 92, width: view.bounds.width - 16, height: view.bounds.height - 100)
        text.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        text.backgroundColor = .black; text.textColor = .green
        text.font = UIFont.monospacedSystemFont(ofSize: 10, weight: .regular)
        text.isEditable = false
        view.addSubview(text)
    }

    override func viewDidAppear(_ animated: Bool) { super.viewDidAppear(animated); run() }

    @objc private func run() {
        if running { return }
        running = true
        var lines = ["S7GE Net  \(Date())", ""]
        func show(_ s: String) { lines.append(s); let all = lines.joined(separator: "\n"); DispatchQueue.main.async { self.text.text = all } }
        DispatchQueue.global().async {
            show("1 interfaces"); Probe.interfaces().forEach { show("  " + $0) }
            show("2 DNS del sistema"); for n in ["example.com", "neverssl.com", "1.1.1.1"] { show("  " + Probe.resolve(n)) }
            show("3 TCP a direcciones numericas")
            for (ip, port) in [("1.1.1.1", UInt16(80)), ("8.8.8.8", UInt16(53)), ("9.9.9.9", UInt16(443))] { show("  " + Probe.tcp(ip, port)) }
            show("4 DNS por UDP directo"); for s in ["8.8.8.8", "1.1.1.1"] { show("  " + Probe.dnsOverUDP(s)) }
            show("5 URLSession")
            for u in ["http://1.1.1.1/", "http://neverssl.com/", "https://example.com/"] { show("  " + Probe.http(u)) }
            show("fin")
            if let data = (lines.joined(separator: "\n") + "\n---\n").data(using: .utf8) {
                let path = "/private/var/tmp/s7ge-net.txt"
                if let h = FileHandle(forWritingAtPath: path) { h.seekToEndOfFile(); h.write(data); h.closeFile() }
                else { FileManager.default.createFile(atPath: path, contents: data, attributes: [.posixPermissions: 0o666]) }
            }
            DispatchQueue.main.async { self.running = false }
        }
    }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions opts: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let w = UIWindow(frame: UIScreen.main.bounds)
        w.rootViewController = NetController()
        w.makeKeyAndVisible()
        window = w
        return true
    }
}
