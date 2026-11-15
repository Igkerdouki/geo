#!/usr/bin/env bash
# Publish the reviewed integration from a normal terminal with GitHub write access.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(git branch --show-current)" != main ]; then
  echo 'Expected main. Stop and review the current branch.' >&2; exit 1
fi
if ! git diff --cached --quiet; then
  echo 'Existing staged changes found; review them before publishing.' >&2; exit 1
fi
if git rev-parse -q --verify MERGE_HEAD >/dev/null; then
  echo 'Finish the existing merge first.' >&2; exit 1
fi
python3 - <<'CHECK'
import hashlib
from pathlib import Path
checks = {'.gitignore': '565acee8f6e35122c5f0be548b2c6bffe2e53410a2851d398c8a9856ca47c0fb', '.vercelignore': 'c16a16740095ce43f321eca83124ed5189ba4f8e0fa15a0502b9bedf43482c9c', 'AGENTS.md': 'e93054505a4024179f23559e7e8c6c2aebcde5253681728e2a48247271b95f6b', 'README.md': 'b4c36d0399bdbd071688a0f1420931d918ce9ceeaec731cfc8dd5a80dcc5ce39', 'api/index.py': '4e187b5c52d025d05949e5850816027466c7616196931fc6d8ecd0a1cd798e2c', 'backend/.env.example': 'da7c85b3a617e476fb4a72228a43963092fd914638ee71a97531f4c7acb99dc0', 'backend/app/api/investigations.py': 'e2f3e3c6bf0e72234d1be1173a2d4b4c983e28f2eb1aaa36d8b7fa11454cca21', 'backend/app/config.py': 'ec1f14795905de32eeef1dbfc255708a326fc950ef1d7df347b06a13457845bb', 'backend/app/database.py': '58739d284048b6e5185ee8cd46ed1e38a08d9ce089cb1c759f816d30aa765df9', 'backend/app/evidence_store.py': '6a98275f530374eca6aea8c98b98bd926ca374093f115772d6f246bf95539c8d', 'backend/app/evidence_tools.py': 'b7520ceba2b0e040087b2e7d9b86114520564f12c02c10300a0d16c339c0af06', 'backend/app/investigator.py': 'f5945d7e60d5f9fa98d59b296e13024a6c52891a3502da91bed88e66209da677', 'backend/app/main.py': '9fa3e3dbb92071fd75ad0b1152cb1d8db3c34b8f49890578fc1b33a1aabbcdff', 'backend/app/mcp_server.py': '91831f8cf3e10ae36ec859ca47e50779e4c08df96c4e435ac182f50b0858cdfb', 'backend/app/spatial_tools.py': 'c969f070e17785b09a56e0d6f234b6beb5620e2a69bc5fc6578ac115cbf0269a', 'backend/mcp_server.py': '3c5814bf3cb3fd85788251b838fcbf62634986367e1492e5e0ecd512fed2b821', 'backend/requirements.txt': '45f76214a12ef991cab991c58b569fd0ac6c74d9503b6bda65e9bc334a3d0746', 'backend/tests/test_combined_mcp.py': 'fd728a7f66699b50a0f58dfaaa1f004fad7bc6c151669d3a1cb584d3a773cd9e', 'backend/tests/test_evidence.py': '5b7b1eee7fff3f493f100116b265b50efb609c5be23e923bbfe2b75e247658e4', 'backend/tests/test_pur_neon.py': 'fc8fca149e34f2e089fd137e2f8570e5c95d544ee5ac3e01d026bb4c0b55ee81', 'docs/PROGRESS.md': '2fcf3df2577938818a70691fd019fe7fc84a86c5a3e624b5458b11296eacf594', 'frontend/index.html': '4f04a6fe1adbff3ba60612b990fdedfb0bd1537db06ea35ffec2913c037f6ba6', 'frontend/package-lock.json': 'ee25e033f5b583b8b697b2b9f2a75769022b204b7e1e6ecd5f683fd6e1fd1fc8', 'frontend/package.json': '23dd10c94b39a5039ffd44e2693e747e7465f6cef76f51a31bd3cc4cf4ec90c9', 'frontend/src/App.jsx': 'bd0e5dccda2da63179fdc052dde636a18a0eb81df33ffadb9d17d7c6f779f661', 'frontend/src/CityMap.css': 'c37b96cdd6f24bedbe18560da795d49c651cbd3c5cddf99620672515c6fc461e', 'frontend/src/CityMap.jsx': '21e5bd023221b60088ee0377c984d7895fcaa9a5ff7638d9b328a831e8de91e7', 'frontend/src/Investigator.css': '8b0d6089f155a243a0c0d7b8d5b46b89b47883e258b9a9632ccdf6eb7087fc53', 'frontend/src/Investigator.jsx': '0e7c666caabb6d03e33ba123fce28c291553d4b20bddba253e96fd818139637a', 'frontend/src/Landing.jsx': '20e75290ccfad3b0918cf9d5979644f97b8bebcca4d6a9fea84ef83fc85fbb50', 'frontend/src/MinimalUI.css': '5cdcef6339624d50986909a4b019af106981c4e013f8c754958b22532038317f', 'frontend/src/SceneWorkspace.css': '0a98e181c00bec68ce96721b0ff57208e37344fc57721cb2251b19af96af5120', 'frontend/src/ThreeScene.jsx': 'd645a97c933ed557c336f8073b18167a4fdaea1b08e5ae5e1fd51851c6545c80', 'frontend/src/main.jsx': '2a506248dcb5d342930b62fc087e6312120658a0015c5edd47a9c670ecb1c20f', 'frontend/src/windVector.mjs': '1774f0b095bf482647591605516f19ce21a308f60f6030782fb20add918360ff', 'frontend/tests/windVector.test.mjs': '0a38c301fbaf32d8d66977ebd6b712fc02ea0cbbf6a8be4c8b7ed85f5f2f8ecb', 'frontend/vite.config.js': '45cbf5dac1079385746d69fb8f64b797145ff068fbbe6fb9a158bf76710779e9', 'requirements.txt': '45f76214a12ef991cab991c58b569fd0ac6c74d9503b6bda65e9bc334a3d0746', 'vercel.json': '700c5ce3af8dd68c9de95db376a28f016ae9661f61e85817fa4df38ee5588732'}
changed = [p for p, digest in checks.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
if changed:
    raise SystemExit('Reviewed files changed; rerun integration before publishing: ' + ', '.join(changed))
CHECK
git fetch origin main
if [ "$(git rev-parse origin/main)" != "8f48e13005afed198b38b6e2cfbbc858542d27aa" ]; then
  echo 'Remote main changed. Stop and integrate the new changes before pushing.' >&2; exit 1
fi
if [ "$(git rev-parse HEAD)" != "bcf47df54e616ce6dfe794b5020f20a455576a79" ]; then
  echo 'Local HEAD changed. Stop and review before publishing.' >&2; exit 1
fi
git add -- .gitignore .vercelignore AGENTS.md README.md api/index.py backend/.env.example backend/app/api/investigations.py backend/app/config.py backend/app/database.py backend/app/evidence_store.py backend/app/evidence_tools.py backend/app/investigator.py backend/app/main.py backend/app/mcp_server.py backend/app/spatial_tools.py backend/mcp_server.py backend/requirements.txt backend/tests/test_combined_mcp.py backend/tests/test_evidence.py backend/tests/test_pur_neon.py docs/PROGRESS.md frontend/index.html frontend/package-lock.json frontend/package.json frontend/src/App.jsx frontend/src/CityMap.css frontend/src/CityMap.jsx frontend/src/Investigator.css frontend/src/Investigator.jsx frontend/src/Landing.jsx frontend/src/MinimalUI.css frontend/src/SceneWorkspace.css frontend/src/ThreeScene.jsx frontend/src/main.jsx frontend/src/windVector.mjs frontend/tests/windVector.test.mjs frontend/vite.config.js requirements.txt vercel.json
git commit -m "Integrate AskGaia workspace, Neon evidence and combined MCP tools"
if ! git merge --no-ff --no-edit origin/main; then
  conflicts="$(git diff --name-only --diff-filter=U)"
  if [ "$conflicts" != "backend/mcp_server.py" ]; then
    echo 'Unexpected conflict; merge left intact for review.' >&2; exit 1
  fi
  # Ioanna's implementation is preserved in app/spatial_tools.py and registered
  # by app/mcp_server.py. Keep the merged compatibility launcher at this path.
  git checkout --ours -- backend/mcp_server.py
  git add -- backend/mcp_server.py
  git commit --no-edit
fi
git push origin HEAD:main
