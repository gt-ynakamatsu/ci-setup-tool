"""生成した Jenkinsfile（Groovy）の引用符・括弧の対応を機械的に確かめる簡易チェッカ。

Jenkinsfile が構文エラーだと全ビルドが即失敗するのに、ローカルには Groovy 処理系が無く
Jenkins に載せるまで気付けない。三連引用符の閉じ忘れや括弧の不一致という「壊し方の大半」は
文字列・コメントを飛ばしながら数えるだけで検出できるため、その範囲だけを見る。
"""

from __future__ import annotations


class GroovySyntaxError(AssertionError):
    pass


def check_quotes_and_brackets(text: str) -> None:
    i = 0
    n = len(text)
    depth = {"{": 0, "(": 0, "[": 0}
    closer = {"}": "{", ")": "(", "]": "["}
    line = 1

    def fail(message: str) -> None:
        raise GroovySyntaxError(f"{message}（{line} 行目付近）")

    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        # コメント（文字列の外だけ）
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                fail("ブロックコメントが閉じていません")
            line += text.count("\n", i, end)
            i = end + 2
            continue
        # 文字列（三連 → 単一）。中身の括弧は数えない。
        for quote in ('"""', "'''", '"', "'"):
            if not text.startswith(quote, i):
                continue
            j = i + len(quote)
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text.startswith(quote, j):
                    break
                j += 1
            else:
                fail(f"文字列 {quote} が閉じていません")
            if not text.startswith(quote, j):
                fail(f"文字列 {quote} が閉じていません")
            line += text.count("\n", i, j)
            i = j + len(quote)
            break
        else:
            if ch in depth:
                depth[ch] += 1
            elif ch in closer:
                opener = closer[ch]
                depth[opener] -= 1
                if depth[opener] < 0:
                    fail(f"'{ch}' が多すぎます")
            i += 1

    for opener, count in depth.items():
        if count != 0:
            raise GroovySyntaxError(f"'{opener}' が {count} 個閉じられていません")
