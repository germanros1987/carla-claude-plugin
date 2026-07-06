# List all Blueprint-class assets in the CarlaUE4 project via the AssetRegistry.
#
# Runs inside UE4's embedded Python (3.7.7) through PythonScriptPlugin. Reads
# parent class from asset-registry TAGS only — no per-asset load — so it is safe
# under -nullrhi and fast over 40k+ assets. Writes results to RESULT_PATH so a
# late engine crash can't swallow stdout.
import os
import unreal
from collections import Counter

# Result file next to this script unless overridden.
RESULT_PATH = os.environ.get(
    "UEPY_RESULT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_result.txt"),
)

ar = unreal.AssetRegistryHelpers.get_asset_registry()
bps = ar.get_assets_by_class("Blueprint")

out = ["CARLA_BP_BEGIN", "TOTAL_BLUEPRINTS=%d" % len(bps)]

cats = Counter()
rows = []
for a in bps:
    name = str(a.asset_name)
    path = str(a.package_path)
    parent = a.get_tag_value("NativeParentClass") or a.get_tag_value("ParentClass") or ""
    parent = str(parent).split(".")[-1].rstrip("'")
    seg = path.split("/")
    cat = "/".join(seg[:6]) if len(seg) >= 6 else path
    cats[cat] += 1
    rows.append((path, name, parent))

out.append("CATEGORY_COUNTS_BEGIN")
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    out.append("%5d  %s" % (n, c))
out.append("CATEGORY_COUNTS_END")

pc = Counter(p for _, _, p in rows if p)
out.append("PARENT_CLASS_TOP_BEGIN")
for p, n in pc.most_common(15):
    out.append("%5d  %s" % (n, p))
out.append("PARENT_CLASS_TOP_END")

out.append("SAMPLE_BEGIN")
for path, name, parent in sorted(rows)[:30]:
    out.append("%s/%s  [%s]" % (path, name, parent))
out.append("SAMPLE_END")
out.append("CARLA_BP_END")

text = "\n".join(out)
unreal.log(text)
with open(RESULT_PATH, "w") as f:
    f.write(text + "\n")
