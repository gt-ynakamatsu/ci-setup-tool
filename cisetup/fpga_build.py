"""FPGA プリセットのビルドコマンド欄（`ci-fpga.ps1` のオプション）の読み書き。

`ci-build.ps1` はビルドコマンド欄を次の 2 通りに解釈する。

* ``-`` 始まり … `ci-fpga.ps1` へのオプション（``-Project`` / ``-Tcl``）
* それ以外 …… 利用者が用意した独自コマンド（ヘルパーを使わずそのまま実行）

GUI では前者を「FPGA プロジェクト」「ビルド Tcl」の入力欄として見せたいので、
ここで文字列 ⇔ 各値の変換を行う。独自コマンドは解釈せずそのまま保持する
（画面で編集していないコマンドを勝手に消さないため）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FpgaBuildCommand:
    """ビルドコマンド欄の内容を GUI の入力欄単位に分解したもの。"""

    project: str = ""
    tcl: str = ""
    # ヘルパーを使わない独自コマンド（設定されていれば project / tcl より優先される）。
    raw: str = ""


def _option_value(text: str, name: str) -> str:
    match = re.search(rf'(?i)-{name}(?:\s+|=)("[^"]+"|\S+)', text)
    return match.group(1).strip('"') if match else ""


def parse_fpga_build_command(command: str | None) -> FpgaBuildCommand:
    text = (command or "").strip()
    if not text:
        return FpgaBuildCommand()
    if not text.startswith("-"):
        return FpgaBuildCommand(raw=text)
    return FpgaBuildCommand(
        project=_option_value(text, "Project"),
        tcl=_option_value(text, "Tcl"),
    )


def compose_fpga_build_command(project: str = "", tcl: str = "", raw: str = "") -> str:
    """入力欄の値から、ビルドコマンド欄に保存する文字列を作る。

    どちらも空なら空文字（= ci-fpga.ps1 の自動検出に任せる）を返す。
    """
    if (raw or "").strip():
        return raw.strip()
    parts: list[str] = []
    for name, value in (("Project", project), ("Tcl", tcl)):
        normalized = (value or "").strip().replace("\\", "/")
        if not normalized:
            continue
        # 空白を含むパスは ci-build.ps1 側の \S+ で切れるため引用符で囲む。
        quoted = f'"{normalized}"' if " " in normalized else normalized
        parts.append(f"-{name} {quoted}")
    return " ".join(parts)
