"""Model-card registry for the AI-assisted development acknowledgements block.

Pattern borrowed from the sibling repo `catskillsresearch/scott_models`
(`scripts/ai_model_cards.py`). Injected into `arxiv.md` / `arxiv.tex` by
`build_arxiv_tex.py` at:

  <!-- AI_MODEL_TOOL_BULLETS --> ... <!-- /AI_MODEL_TOOL_BULLETS -->
  <!-- AI_MODEL_REFERENCES --> ... <!-- /AI_MODEL_REFERENCES -->

`arxiv.md` uses plain numeric bracket citations, not the bracket-key style
scott_models uses, so each card's ``cite_key`` here is the next free
reference number, kept in sync by hand.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCard:
    label: str
    cite_key: str
    tool_note: str
    reference: str


MODEL_CARDS: tuple[ModelCard, ...] = (
    ModelCard(
        label="Cursor",
        cite_key="18",
        tool_note=(
            "agent-assisted development environment for this repository: the OpenVSP "
            "floorplan/profile CAD and Blender drop-in-cutaway pipeline, the "
            "`constants_model.py` mass/energy-closure derivations, the interactive assembly "
            "outliner, and drafting/maintaining this narrative (`arxiv.md`), including "
            "splitting the original monorepo into this vehicle-integration paper plus the "
            "companion CHARM reactor and combined-cycle-engine papers."
        ),
        reference=(
            "Anysphere, Inc. *Cursor: AI-native code editor and agent environment*. "
            "<https://cursor.com> (accessed 2026)."
        ),
    ),
    ModelCard(
        label="xAI Grok 4.5",
        cite_key="19",
        tool_note=(
            "primary agent model for large stretches of the vehicle-packaging work: "
            "OpenVSP geometry iteration (body flap, OMS pods), the CHARM/engine bottom-up "
            "mass roll-up in `constants_model.py`, and the `assembly.json`-driven Blender "
            "drop-in figures. Used via the Cursor agent environment."
        ),
        reference=(
            "xAI. *Grok 4.5*. Model documentation, "
            "<https://docs.x.ai/developers/models/grok-4.5>; Cursor announcement, "
            "<https://cursor.com/blog/grok-4-5> (accessed 2026)."
        ),
    ),
    ModelCard(
        label="Anthropic Claude Sonnet 5",
        cite_key="20",
        tool_note=(
            "session work including narrative maintenance (table of contents, appendix "
            "reordering), rewriting \u00a79/\u00a710 into short vehicle-level summaries that cite the "
            "companion reactor and engine papers for full derivations, pruning the "
            "generic multi-architecture survey scaffold from this repository, and this "
            "AI-assistance disclosure. Used via the Cursor agent environment."
        ),
        reference=(
            "Anthropic. *Claude Sonnet 5*. System card, "
            "<https://www.anthropic.com/claude-sonnet-5-system-card>; model documentation "
            "as integrated in Cursor, <https://cursor.com/docs/models> (accessed 2026)."
        ),
    ),
    ModelCard(
        label="Google Nano Banana Pro (Gemini 3 Pro Image)",
        cite_key="21",
        tool_note=(
            "generated Fig.~\\ref{fig:catskills-ssto-beauty-shot}, an illustrative exterior "
            "concept render of the vehicle taking off from a municipal airport, and "
            "Fig.~\\ref{fig:catskills-ssto-cabin-liftoff-view}, a companion flight-deck "
            "interior render at the same moment, both prompted from the CAD floorplan/profile "
            "wireframes as reference images "
            "(Figs.~\\ref{fig:charm-ssto-interior-floorplan}, "
            "\\ref{fig:charm-ssto-exterior-profile}). Concept art only — proportions, "
            "panel lines, cabin layout, and the runway scene are AI interpretation, not CAD; "
            "the wireframe figures remain the dimensioned source of truth."
        ),
        reference=(
            "Google DeepMind. *Nano Banana Pro (Gemini 3 Pro Image)*. Product "
            "announcement, <https://blog.google/innovation-and-ai/products/nano-banana-pro/>; "
            "model documentation, <https://ai.google.dev/gemini-api/docs/image-generation> "
            "(accessed 2026)."
        ),
    ),
)

TOOL_BULLETS_BEGIN = "<!-- AI_MODEL_TOOL_BULLETS -->"
TOOL_BULLETS_END = "<!-- /AI_MODEL_TOOL_BULLETS -->"
REFERENCES_BEGIN = "<!-- AI_MODEL_REFERENCES -->"
REFERENCES_END = "<!-- /AI_MODEL_REFERENCES -->"


def render_tool_bullets() -> str:
    return "\n".join(
        f"- **{card.label}** [{card.cite_key}] — {card.tool_note}" for card in MODEL_CARDS
    )


def render_model_references() -> str:
    return "\n\n".join(f"[{card.cite_key}] {card.reference}" for card in MODEL_CARDS)


def inject_model_cards(text: str) -> str:
    """Expand the AI model-card markers already present in `arxiv.md`."""
    if TOOL_BULLETS_BEGIN not in text:
        raise RuntimeError(f"missing {TOOL_BULLETS_BEGIN} in Acknowledgments")
    if REFERENCES_BEGIN not in text:
        raise RuntimeError(f"missing {REFERENCES_BEGIN} in References")
    text = _replace_between(text, TOOL_BULLETS_BEGIN, TOOL_BULLETS_END, render_tool_bullets())
    text = _replace_between(text, REFERENCES_BEGIN, REFERENCES_END, render_model_references())
    return text


def _replace_between(text: str, begin: str, end: str, body: str) -> str:
    start = text.index(begin)
    stop = text.index(end, start)
    stop_end = stop + len(end)
    inner_start = start + len(begin)
    if inner_start < stop and text[inner_start : inner_start + 1] == "\n":
        inner_start += 1
    if inner_start < stop and text[stop - 1 : stop] == "\n":
        stop -= 1
    return text[:start] + begin + "\n" + body + "\n" + end + text[stop_end:]
