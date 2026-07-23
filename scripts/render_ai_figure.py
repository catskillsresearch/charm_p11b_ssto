#!/usr/bin/env python3
"""Render (or validate) an AI figure from a ``*.prompt.txt`` artifact.

Workflow (same idea as mermaid ``.mmd`` → ``.pdf``):

  research/figures/prompts/<stem>.prompt.txt   # source of truth (caption + gen input)
  research/figures/<stem>.png                  # cached raster
  research/figures/<stem>.ai.meta              # sha256 of prompt that produced the PNG

By default this script **does not** call a remote image model (slow / interactive).
It only rebuilds when:

  * ``FORCE_AI_FIGURES=1``, or
  * the PNG is missing, or
  * the prompt hash differs from ``.ai.meta`` **and** ``AI_IMAGE_CMD`` is set.

``AI_IMAGE_CMD`` is a shell template with ``{prompt_file}`` and ``{output_png}``.
Example::

  export AI_IMAGE_CMD='my-image-cli --prompt-file {prompt_file} --out {output_png}'
  make ai-figures

During Cursor prototyping, the agent regenerates PNGs via GenerateImage, writes the
prompt file, then runs::

  python3 scripts/render_ai_figure.py --stamp research/figures/prompts/foo.prompt.txt

which updates ``.ai.meta`` to match the committed PNG without re-calling a model.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def paths_for(prompt_path: Path) -> tuple[Path, Path, Path]:
    prompt_path = prompt_path.resolve()
    stem = prompt_path.name.replace(".prompt.txt", "")
    if prompt_path.name.endswith(".prompt.txt"):
        stem = prompt_path.name[: -len(".prompt.txt")]
    else:
        stem = prompt_path.stem
    png = ROOT / "research" / "figures" / f"{stem}.png"
    meta = ROOT / "research" / "figures" / f"{stem}.ai.meta"
    return prompt_path, png, meta


def stamp(prompt_path: Path, png: Path, meta: Path) -> None:
    text = prompt_path.read_text(encoding="utf-8")
    if not png.is_file():
        raise SystemExit(f"error: cannot stamp; missing PNG {png}")
    meta.write_text(prompt_hash(text) + "\n", encoding="utf-8")
    print(f"stamped {meta.relative_to(ROOT)} ← {png.relative_to(ROOT)}")


def render(prompt_path: Path, png: Path, meta: Path, *, force: bool) -> int:
    text = prompt_path.read_text(encoding="utf-8")
    h = prompt_hash(text)
    up_to_date = (
        png.is_file()
        and meta.is_file()
        and meta.read_text(encoding="utf-8").strip() == h
    )
    if up_to_date and not force:
        print(f"up-to-date {png.relative_to(ROOT)}")
        return 0

    cmd_tmpl = os.environ.get("AI_IMAGE_CMD", "").strip()
    if not cmd_tmpl:
        if png.is_file() and not force:
            # Prompt changed but no backend: keep PNG, refresh stamp only if asked.
            print(
                f"warning: prompt changed for {png.relative_to(ROOT)} but "
                "AI_IMAGE_CMD is unset; keeping existing PNG. "
                "Re-generate in Cursor then: "
                f"python3 scripts/render_ai_figure.py --stamp {prompt_path.relative_to(ROOT)}",
                file=sys.stderr,
            )
            return 0
        if png.is_file() and force and not cmd_tmpl:
            print(
                "error: FORCE_AI_FIGURES set but AI_IMAGE_CMD unset; "
                "cannot regenerate remotely. Use Cursor GenerateImage, then --stamp.",
                file=sys.stderr,
            )
            return 1
        print(
            f"error: missing {png.relative_to(ROOT)}; set AI_IMAGE_CMD or "
            "generate via Cursor and --stamp",
            file=sys.stderr,
        )
        return 1

    cmd = cmd_tmpl.format(
        prompt_file=str(prompt_path),
        output_png=str(png),
        stem=png.stem,
    )
    print(f"==> AI render: {cmd}")
    proc = subprocess.run(cmd, shell=True, check=False)
    if proc.returncode != 0 or not png.is_file():
        print("error: AI_IMAGE_CMD failed", file=sys.stderr)
        return 1
    meta.write_text(h + "\n", encoding="utf-8")
    print(f"wrote {png.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prompt", type=Path, help="path to *.prompt.txt")
    p.add_argument(
        "--stamp",
        action="store_true",
        help="record prompt hash for an existing PNG (no model call)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="ignore up-to-date cache (requires AI_IMAGE_CMD unless --stamp)",
    )
    args = p.parse_args(argv)
    prompt_path, png, meta = paths_for(args.prompt)
    if not prompt_path.is_file():
        print(f"error: missing {prompt_path}", file=sys.stderr)
        return 1
    force = args.force or os.environ.get("FORCE_AI_FIGURES", "") == "1"
    if args.stamp:
        stamp(prompt_path, png, meta)
        return 0
    return render(prompt_path, png, meta, force=force)


if __name__ == "__main__":
    raise SystemExit(main())
