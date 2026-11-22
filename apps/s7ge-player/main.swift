// S7GE Player: a small audio player for this phone, where "Save to Files" does not work yet (the Files provider "On My iPhone" never starts, E-0409/E-0410) and so a song
// downloaded by Safari cannot be moved anywhere that a normal player looks. This app looks where such files really are, since nothing here is sandboxed:
//   - its own Documents folder;
//   - Safari's download folders: /private/var/mobile/Containers/Data/Application/<each>/Library/Safari/Downloads/<each>/ ;
//   - /private/var/mobile/Media/Downloads and /private/var/mobile/Media/Books (where other apps leave files).
// It lists the audio files found (mp3, m4a, aac, wav, aif, caf, flac), plays one with AVAudioPlayer (play/pause, next, previous, a progress bar to move in the song) and
// writes what it found and every error to /private/var/tmp/s7ge-player.txt for the PC. Plain arm64 UIKit/AVFoundation, valid on a real iPhone.
import UIKit
import AVFoundation

struct Track { let url: URL; let name: String; let size: Int64 }

enum Library {
    static let extensions: Set<String> = ["mp3", "m4a", "aac", "wav", "aif", "aiff", "caf", "flac"]

    static func log(_ line: String) {
        guard let data = (line + "\n").data(using: .utf8) else { return }
        let path = "/private/var/tmp/s7ge-player.txt"
        if let h = FileHandle(forWritingAtPath: path) { h.seekToEndOfFile(); h.write(data); h.closeFile() }
        else { FileManager.default.createFile(atPath: path, contents: data, attributes: [.posixPermissions: 0o666]) }
    }

    static func scan(_ directory: String, depth: Int, into out: inout [Track]) {
        let fm = FileManager.default
        guard let names = try? fm.contentsOfDirectory(atPath: directory) else { return }
        for n in names {
            let full = directory + "/" + n
            var isDir: ObjCBool = false
            guard fm.fileExists(atPath: full, isDirectory: &isDir) else { continue }
            if isDir.boolValue {
                if depth > 0 { scan(full, depth: depth - 1, into: &out) }
            } else if extensions.contains((n as NSString).pathExtension.lowercased()) {
                let size = ((try? fm.attributesOfItem(atPath: full))?[.size] as? NSNumber)?.int64Value ?? 0
                out.append(Track(url: URL(fileURLWithPath: full), name: (n as NSString).deletingPathExtension, size: size))
            }
        }
    }

    static func tracks() -> [Track] {
        var out: [Track] = []
        let fm = FileManager.default
        if let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first { scan(docs.path, depth: 2, into: &out) }
        let apps = "/private/var/mobile/Containers/Data/Application"
        for uuid in (try? fm.contentsOfDirectory(atPath: apps)) ?? [] {
            scan(apps + "/" + uuid + "/Library/Safari/Downloads", depth: 2, into: &out)
        }
        scan("/private/var/mobile/Media/Downloads", depth: 3, into: &out)
        scan("/private/var/mobile/Media/Books", depth: 3, into: &out)
        var seen = Set<String>()
        return out.filter { seen.insert($0.url.path).inserted }.sorted { $0.name.lowercased() < $1.name.lowercased() }
    }
}

final class PlayerController: UIViewController, UITableViewDataSource, UITableViewDelegate, AVAudioPlayerDelegate {
    private let table = UITableView()
    private let title1 = UILabel(), time1 = UILabel(), state1 = UILabel()
    private let slider = UISlider()
    private let playButton = UIButton(type: .system)
    private var tracks: [Track] = []
    private var current = -1
    private var player: AVAudioPlayer?
    private var timer: Timer?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        title1.textColor = .white; title1.font = .boldSystemFont(ofSize: 17); title1.numberOfLines = 2; title1.text = "S7GE Player"
        time1.textColor = .lightGray; time1.font = .monospacedDigitSystemFont(ofSize: 13, weight: .regular)
        state1.textColor = .systemGreen; state1.font = .systemFont(ofSize: 12); state1.numberOfLines = 3
        slider.addTarget(self, action: #selector(seek), for: .valueChanged)
        playButton.setTitle("Play", for: .normal); playButton.addTarget(self, action: #selector(togglePlay), for: .touchUpInside)
        let prev = UIButton(type: .system); prev.setTitle("<<", for: .normal); prev.addTarget(self, action: #selector(previous), for: .touchUpInside)
        let next = UIButton(type: .system); next.setTitle(">>", for: .normal); next.addTarget(self, action: #selector(nextTrack), for: .touchUpInside)
        let rescan = UIButton(type: .system); rescan.setTitle("Buscar", for: .normal); rescan.addTarget(self, action: #selector(reload), for: .touchUpInside)
        let buttons = UIStackView(arrangedSubviews: [prev, playButton, next, rescan]); buttons.distribution = .fillEqually
        let head = UIStackView(arrangedSubviews: [title1, time1, slider, buttons, state1]); head.axis = .vertical; head.spacing = 6
        head.translatesAutoresizingMaskIntoConstraints = false
        table.translatesAutoresizingMaskIntoConstraints = false
        table.dataSource = self; table.delegate = self; table.backgroundColor = .black
        view.addSubview(head); view.addSubview(table)
        let g = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            head.topAnchor.constraint(equalTo: g.topAnchor, constant: 8),
            head.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 12), head.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -12),
            table.topAnchor.constraint(equalTo: head.bottomAnchor, constant: 8),
            table.leadingAnchor.constraint(equalTo: g.leadingAnchor), table.trailingAnchor.constraint(equalTo: g.trailingAnchor), table.bottomAnchor.constraint(equalTo: g.bottomAnchor),
        ])
        do { try AVAudioSession.sharedInstance().setCategory(.playback); try AVAudioSession.sharedInstance().setActive(true) }
        catch { Library.log("AVAudioSession: \(error)"); state1.text = "AVAudioSession: \(error.localizedDescription)" }
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.tick() }
        reload()
    }

    @objc private func reload() {
        tracks = Library.tracks()
        Library.log("\(Date()): \(tracks.count) audio file(s)")
        for t in tracks { Library.log("  \(t.size) bytes  \(t.url.path)") }
        state1.text = tracks.isEmpty ? "No hay audio: baja uno en Safari o copialo a la carpeta Documents de esta app" : "\(tracks.count) archivo(s)"
        table.reloadData()
    }

    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int { return tracks.count }
    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let c = tableView.dequeueReusableCell(withIdentifier: "c") ?? UITableViewCell(style: .subtitle, reuseIdentifier: "c")
        let t = tracks[indexPath.row]
        c.textLabel?.text = t.name; c.textLabel?.textColor = indexPath.row == current ? .systemGreen : .white
        c.detailTextLabel?.text = String(format: "%.1f MB", Double(t.size) / 1_048_576); c.detailTextLabel?.textColor = .lightGray
        c.backgroundColor = .black
        return c
    }
    func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) { play(indexPath.row) }

    private func play(_ index: Int) {
        guard index >= 0, index < tracks.count else { return }
        current = index
        let t = tracks[index]
        do {
            let p = try AVAudioPlayer(contentsOf: t.url)
            p.delegate = self
            p.prepareToPlay()
            let ok = p.play()
            player = p
            title1.text = t.name
            state1.text = ok ? "Reproduciendo (\(Int(p.duration)) s, \(p.format.sampleRate) Hz, \(p.numberOfChannels) canales)" : "play() devolvio false"
            Library.log("play \(t.url.lastPathComponent): ok \(ok), duration \(p.duration), format \(p.format)")
        } catch {
            player = nil
            state1.text = "No se puede abrir: \(error.localizedDescription)"
            Library.log("AVAudioPlayer(\(t.url.path)): \(error)")
        }
        playButton.setTitle(player?.isPlaying == true ? "Pause" : "Play", for: .normal)
        table.reloadData()
    }

    @objc private func togglePlay() {
        guard let p = player else { if current < 0 { play(0) }; return }
        if p.isPlaying { p.pause() } else { p.play() }
        playButton.setTitle(p.isPlaying ? "Pause" : "Play", for: .normal)
    }
    @objc private func nextTrack() { play(current + 1 < tracks.count ? current + 1 : 0) }
    @objc private func previous() { play(current > 0 ? current - 1 : max(tracks.count - 1, 0)) }
    @objc private func seek() { if let p = player { p.currentTime = Double(slider.value) * p.duration } }
    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) { Library.log("finished, ok \(flag)"); nextTrack() }
    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) { Library.log("decode error: \(String(describing: error))"); state1.text = "Error de decodificacion" }

    private func tick() {
        guard let p = player else { return }
        if !slider.isTracking { slider.value = p.duration > 0 ? Float(p.currentTime / p.duration) : 0 }
        time1.text = String(format: "%d:%02d / %d:%02d", Int(p.currentTime) / 60, Int(p.currentTime) % 60, Int(p.duration) / 60, Int(p.duration) % 60)
    }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions opts: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let w = UIWindow(frame: UIScreen.main.bounds)
        w.rootViewController = PlayerController()
        w.makeKeyAndVisible()
        window = w
        return true
    }
}
