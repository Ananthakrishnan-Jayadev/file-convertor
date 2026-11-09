# Running File Converter on the home server (Docker)

File Converter runs in Docker on the always-on Ubuntu laptop, next to Job Radar and the other
apps, and is reachable from any device on your Wi-Fi at `http://<server-ip>:8010`. Updating it
to the latest code on GitHub is one command.

- **Port:** 8010, because Job Radar already uses 8000. Change it with `FC_PORT` in `.env`.
- **Where its files are:** `~/file-convertor/data` on the server: uploads, results and the job
  list. Uploads and results are deleted after an hour, so this folder stays small.
- **No login:** keep it on your home network. Don't forward the port on the router. For access
  away from home, use Tailscale rather than opening ports.

Below, the server is `ananthu@192.168.1.113` and `~` is your home folder on it.

## 1. Once: set up the server

On the **server** (Docker and the compose plugin are already there for your other apps):

```bash
# Check that port 8010 is free. No output means it is.
ss -ltn | grep ':8010 '

# The code
git clone https://github.com/Ananthakrishnan-Jayadev/file-convertor.git ~/file-convertor
cd ~/file-convertor
mkdir -p data

# Your user and group ids (so files in data/ stay yours) and the port
echo "UID=$(id -u)" > .env
echo "GID=$(id -g)" >> .env
echo "FC_PORT=8010" >> .env
```

If 8010 is taken, pick another free port and use it in `.env` instead.

Optional settings for `.env`:

| Setting | Default | Meaning |
|---|---|---|
| `FC_PORT` | `8010` | The port on the server |
| `FC_WORKERS` | `2` | Conversions at the same time. Raise it if the laptop has cores to spare |
| `FC_MAX_UPLOAD_MB` | `500` | Largest upload; raise it for long videos |

`.env` and `data/` are git-ignored: they never reach GitHub.

## 2. Start it

On the **server**:

```bash
~/file-convertor/deploy/deploy.sh
```

The first build takes several minutes: it builds the web UI, then an image with LibreOffice,
Ghostscript and FFmpeg. When it prints `up at http://...:8010`, open that address on your laptop
or phone.

It restarts by itself after a crash or a reboot (`restart: unless-stopped`).

## 3. Every update afterwards

After pushing changes to GitHub (`main`), from the **laptop**:

```bash
ssh ananthu@192.168.1.113 '~/file-convertor/deploy/deploy.sh'
```

It pulls the code, rebuilds, restarts, and waits until the app answers. Anything being converted
at that moment is marked as failed after the restart (convert it again); finished results from
the last hour stay downloadable.

**If an update goes wrong**, go back to the previous code and rebuild:

```bash
cd ~/file-convertor
git log --oneline -5          # find the last good commit
git checkout <commit>
docker compose up -d --build
# later, back to the latest: git checkout main && ./deploy/deploy.sh
```

## Everyday commands (on the server, in `~/file-convertor`)

```bash
docker compose ps                    # is it running?
docker compose logs -f fileconvert   # its log (Ctrl+C to stop following)
docker compose restart fileconvert   # restart it
docker compose down                  # stop it (the job list in data/ stays)
docker stats fileconvert             # CPU and memory while converting
```

## Troubleshooting

- **`port is already allocated`:** another app uses the port. Set a free one as `FC_PORT` in
  `.env` and run `deploy.sh` again.
- **`Permission denied` under `data/`:** the folder belongs to another user, for example after
  running Docker with `sudo` once. Fix it with `sudo chown -R $(id -u):$(id -g) ~/file-convertor/data`.
- **`git pull` refuses (`Not possible to fast-forward`):** something was edited on the server.
  See what with `git status`; throw it away with `git checkout -- .` (your `.env` and `data/`
  are untouched).
- **Big videos are slow:** that's the old laptop's CPU. Lower `FC_WORKERS` to 1 if the other apps
  get sluggish while converting.
