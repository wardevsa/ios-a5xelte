// HeroReddit: a small Reddit reader for the S7's iOS 16, and the first test of
// tools/herolte-drop.py's app= entries with an app built from source.
// Reads Reddit's public JSON listings (https://www.reddit.com/r/NAME/hot.json);
// no login, no API key. UIKit only, no async/await, plain arm64.
import UIKit

struct Post {
    let title: String
    let sub: String
    let author: String
    let score: Int
    let comments: Int
    let text: String
    let link: String
}

final class ListController: UITableViewController {
    private var sub = UserDefaults.standard.string(forKey: "sub") ?? "popular"
    private var posts: [Post] = []
    private var status = "Cargando..."

    override func viewDidLoad() {
        super.viewDidLoad()
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "c")
        refreshControl = UIRefreshControl()
        refreshControl?.addTarget(self, action: #selector(load), for: .valueChanged)
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Sub", style: .plain,
                                                            target: self, action: #selector(pickSub))
        load()
    }

    @objc private func pickSub() {
        let a = UIAlertController(title: "Subreddit", message: nil, preferredStyle: .alert)
        a.addTextField { $0.text = self.sub; $0.autocapitalizationType = .none; $0.autocorrectionType = .no }
        a.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        a.addAction(UIAlertAction(title: "Abrir", style: .default) { _ in
            let s = (a.textFields?.first?.text ?? "").trimmingCharacters(in: .whitespaces)
            guard !s.isEmpty else { return }
            self.sub = s.hasPrefix("r/") ? String(s.dropFirst(2)) : s
            UserDefaults.standard.set(self.sub, forKey: "sub")
            self.load()
        })
        present(a, animated: true)
    }

    @objc private func load() {
        title = "r/" + sub
        let name = sub.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? sub
        var req = URLRequest(url: URL(string: "https://www.reddit.com/r/\(name)/hot.json?limit=50&raw_json=1")!)
        req.setValue("ios:herolte.heroreddit:0.1 (S7 iOS port)", forHTTPHeaderField: "User-Agent")
        req.timeoutInterval = 20
        URLSession.shared.dataTask(with: req) { data, resp, err in
            var got: [Post] = []
            var msg = ""
            if let err = err {
                msg = "Sin conexión: \(err.localizedDescription)"
            } else if let http = resp as? HTTPURLResponse, http.statusCode != 200 {
                msg = "Reddit respondió \(http.statusCode)"
            } else if let data = data,
                      let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let d = root["data"] as? [String: Any],
                      let children = d["children"] as? [[String: Any]] {
                for c in children {
                    guard let p = c["data"] as? [String: Any] else { continue }
                    got.append(Post(title: p["title"] as? String ?? "",
                                    sub: p["subreddit"] as? String ?? "",
                                    author: p["author"] as? String ?? "",
                                    score: p["score"] as? Int ?? 0,
                                    comments: p["num_comments"] as? Int ?? 0,
                                    text: p["selftext"] as? String ?? "",
                                    link: p["url"] as? String ?? ""))
                }
                if got.isEmpty { msg = "No hay posts" }
            } else {
                msg = "Respuesta que no se entiende"
            }
            DispatchQueue.main.async {
                self.posts = got
                self.status = msg
                self.refreshControl?.endRefreshing()
                self.tableView.reloadData()
            }
        }.resume()
    }

    override func tableView(_ tv: UITableView, numberOfRowsInSection s: Int) -> Int {
        posts.isEmpty ? 1 : posts.count
    }

    override func tableView(_ tv: UITableView, cellForRowAt ip: IndexPath) -> UITableViewCell {
        let cell = tv.dequeueReusableCell(withIdentifier: "c", for: ip)
        var cfg = UIListContentConfiguration.subtitleCell()
        if posts.isEmpty {
            cfg.text = status
        } else {
            let p = posts[ip.row]
            cfg.text = p.title
            cfg.secondaryText = "r/\(p.sub) · u/\(p.author) · \(p.score) ▲ · \(p.comments) comentarios"
            cfg.secondaryTextProperties.color = .secondaryLabel
        }
        cell.contentConfiguration = cfg
        return cell
    }

    override func tableView(_ tv: UITableView, didSelectRowAt ip: IndexPath) {
        tv.deselectRow(at: ip, animated: true)
        guard !posts.isEmpty else { return }
        navigationController?.pushViewController(PostController(post: posts[ip.row]), animated: true)
    }
}

final class PostController: UIViewController {
    private let post: Post
    init(post: Post) { self.post = post; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        title = "r/" + post.sub
        let tv = UITextView(frame: view.bounds)
        tv.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        tv.isEditable = false
        tv.dataDetectorTypes = .link
        tv.font = .preferredFont(forTextStyle: .body)
        tv.textContainerInset = UIEdgeInsets(top: 16, left: 12, bottom: 16, right: 12)
        let body = NSMutableAttributedString(string: post.title + "\n\n",
                                             attributes: [.font: UIFont.preferredFont(forTextStyle: .title2),
                                                          .foregroundColor: UIColor.label])
        let rest = (post.text.isEmpty ? post.link : post.text) +
            "\n\n\(post.score) ▲ · \(post.comments) comentarios · u/\(post.author)"
        body.append(NSAttributedString(string: rest, attributes: [.font: UIFont.preferredFont(forTextStyle: .body),
                                                                  .foregroundColor: UIColor.label]))
        tv.attributedText = body
        view.addSubview(tv)
    }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ app: UIApplication,
                     didFinishLaunchingWithOptions opts: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let w = UIWindow(frame: UIScreen.main.bounds)
        let nav = UINavigationController(rootViewController: ListController(style: .plain))
        nav.navigationBar.prefersLargeTitles = true
        w.rootViewController = nav
        w.makeKeyAndVisible()
        window = w
        return true
    }
}
