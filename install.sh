#!/usr/bin/env bash
# qlc_dmx_bridge のユーザー側ファイルを所定の場所へ配置する
#   - ブリッジ本体          -> ~/.local/bin/dmx2artnet
#   - systemd ユーザーサービス -> ~/.config/systemd/user/dmx2artnet.service
#   - 診断スクリプト        -> ~/dmx_diag.py
#   - フィクスチャ定義      -> ~/.qlcplus/fixtures/
#   - ワークスペース        -> ~/QLC+/stage1_5.qxw (既にあれば上書きしない)
# udev ルールだけは root 権限が要るので、最後に表示するコマンドを手で実行する。
set -euo pipefail
cd "$(dirname "$0")"

install -Dm755 bridge/dmx2artnet          "$HOME/.local/bin/dmx2artnet"
install -Dm644 bridge/dmx2artnet.service  "$HOME/.config/systemd/user/dmx2artnet.service"
install -Dm755 bridge/dmx_diag.py         "$HOME/dmx_diag.py"
install -Dm644 fixtures/STAGE-EVO-HPAR64-9-7ch.qxf "$HOME/.qlcplus/fixtures/STAGE-EVO-HPAR64-9-7ch.qxf"
mkdir -p "$HOME/QLC+"
if [ ! -e "$HOME/QLC+/stage1_5.qxw" ]; then
    install -m644 qlcplus/stage1_5.qxw "$HOME/QLC+/stage1_5.qxw"
    echo "ワークスペースを ~/QLC+/stage1_5.qxw に配置しました"
else
    echo "~/QLC+/stage1_5.qxw は既にあるので触っていません (必要なら手でコピー)"
fi

systemctl --user daemon-reload
systemctl --user enable --now dmx2artnet.service
systemctl --user --no-pager status dmx2artnet.service | head -5

cat <<EOF

残り: udev ルール (root 権限) を入れてから Open DMX を抜き差ししてください
  sudo install -m 644 udev/z65-dmxusb.rules /etc/udev/rules.d/z65-dmxusb.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
EOF
