import json
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GTA6_FILE = os.path.join(DATA_DIR, "history_gta6.json")
POSTED_FILE = os.path.join(DATA_DIR, "history_posted.json")


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _merge_gta6(remote, local):
    out = {
        "used_ids": list(dict.fromkeys((remote.get("used_ids") or []) + (local.get("used_ids") or []))),
        "short_angles": list(dict.fromkeys((remote.get("short_angles") or []) + (local.get("short_angles") or []))),
        "long_angles": list(dict.fromkeys((remote.get("long_angles") or []) + (local.get("long_angles") or []))),
        "posts": [],
    }
    seen = set()
    for p in (remote.get("posts") or []) + (local.get("posts") or []):
        key = p.get("yt_uploaded_id") or p.get("viral_id") or json.dumps(p, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out["posts"].append(p)
    return out


def _merge_posted(remote, local):
    if isinstance(remote, dict) and isinstance(local, dict):
        merged = dict(remote)
        for k, v in local.items():
            if isinstance(v, list) and isinstance(merged.get(k), list):
                seen = set()
                res = []
                for item in merged[k] + v:
                    key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
                    if key not in seen:
                        seen.add(key)
                        res.append(item)
                merged[k] = res
            else:
                merged[k] = v
        return merged
    return local or remote


def main():
    st = subprocess.run(["git", "status", "--porcelain", "ReactFactory/data"], capture_output=True, text=True).stdout.strip()
    if not st:
        print("[MERGE HISTORY] Nenhuma alteração em history*.json.")
        return

    bak_gta6 = _load_json(GTA6_FILE, {}) if os.path.exists(GTA6_FILE) else None
    bak_posted = _load_json(POSTED_FILE, {}) if os.path.exists(POSTED_FILE) else None

    for attempt in range(4):
        subprocess.run(["git", "checkout", "--", "ReactFactory/data"], check=False)
        subprocess.run(["git", "clean", "-fd", "ReactFactory/data"], check=False)
        subprocess.run(["git", "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "reset", "--hard", "origin/main"], check=True)

        os.makedirs(DATA_DIR, exist_ok=True)
        if bak_gta6:
            remote_g = _load_json(GTA6_FILE, {"used_ids": [], "short_angles": [], "long_angles": [], "posts": []})
            with open(GTA6_FILE, "w", encoding="utf-8") as f:
                json.dump(_merge_gta6(remote_g, bak_gta6), f, indent=2, ensure_ascii=False)
        if bak_posted:
            remote_p = _load_json(POSTED_FILE, {})
            with open(POSTED_FILE, "w", encoding="utf-8") as f:
                json.dump(_merge_posted(remote_p, bak_posted), f, indent=2, ensure_ascii=False)

        subprocess.run(["git", "add", "ReactFactory/data/history*.json"], check=False)
        if subprocess.run(["git", "diff", "--staged", "--quiet"]).returncode == 0:
            print("[MERGE HISTORY] Nada novo para commitar após merge.")
            return
        subprocess.run(["git", "commit", "-m", "chore: sync GTA 6 history [skip ci]"], check=True)
        push = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        if push.returncode == 0:
            print("[MERGE HISTORY] Histórico sincronizado e salvo sem conflitos!")
            return
        print(f"[MERGE HISTORY] Retry {attempt + 1} por push simultâneo...")
    raise RuntimeError("Falha ao enviar histórico após retries")


if __name__ == "__main__":
    main()
