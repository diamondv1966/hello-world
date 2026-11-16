"""Create a personal preset from a reference clip.
python3 -I tools/make_user_preset.py <ref.mp4> <preset-name> [--lang th] [--base thai-clear]
-> presets/user/<preset-name>.json  (base preset + measured overrides) + presets/user/<preset-name>.ref/ (profile, sheet)
Use afterwards: tools/edit_like.sh <clip> user/<preset-name> <project>   or  auto_edit.py --preset presets/user/<name>.json
"""
import sys, os, json, subprocess, copy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ref, name = sys.argv[1], sys.argv[2]
lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "th"
out_dir = f"{ROOT}/presets/user/{name}.ref"; os.makedirs(out_dir, exist_ok=True)
subprocess.run([sys.executable, "-I", f"{ROOT}/tools/analyze_ref.py", ref, out_dir, "--lang", lang], check=True)
prof = json.load(open(f"{out_dir}/style_profile.json"))
base_name = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else prof.get("suggested_base_preset", "thai-clear")
p = copy.deepcopy(json.load(open(f"{ROOT}/presets/{base_name}.json")))
def deep(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict): deep(a[k], v)
        else: a[k] = v
deep(p, prof["preset_overrides"])
p["name"] = f"user/{name}"; p["description"] = f"preset ส่วนตัวจากเรฟ {os.path.basename(ref)} (base {base_name})"
p["ref_colour"] = prof["colour"]; p["grade"]["match_ref"] = True
json.dump(p, open(f"{ROOT}/presets/user/{name}.json", "w"), ensure_ascii=False, indent=1)
print(f"✅ presets/user/{name}.json (base {base_name}) — ตรวจ {out_dir}/ref_sheet.jpg ด้วยตาแล้วปรับค่าได้")
