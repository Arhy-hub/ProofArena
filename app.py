"""
app.py — Proof Committee Streamlit UI

Run with:
    streamlit run app.py
"""

import json
import tempfile
import time
from pathlib import Path

import streamlit as st

from orchestrator import ProofCommittee, CommitteeResult

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Proof Committee",
    page_icon=None,
    layout="wide",
)

st.title("Proof Committee", anchor=False)

# ── Load example proofs ────────────────────────────────────────────────────────

EXAMPLES = {
    "V1 · n² + n is even": {
        "conjecture": "For all integers n, n² + n is even.",
        "proof": "n² + n = n(n+1). One of any two consecutive integers is even, so their product is even. Therefore n² + n is even.",
    },
    "V2 · Square of odd is odd": {
        "conjecture": "If n is odd, then n² is odd.",
        "proof": "Let n = 2k + 1 for some integer k. Then n² = (2k+1)² = 4k² + 4k + 1 = 2(2k² + 2k) + 1. This is of the form 2m + 1, so n² is odd.",
    },
    "X1 · False: n²+n+41 always prime": {
        "conjecture": "For all integers n ≥ 1, n² + n + 41 is prime.",
        "proof": "For n = 1: 43 (prime). For n = 2: 47 (prime). For n = 3: 53 (prime). Therefore it always produces primes.",
    },
    "X3 · Wrong: (a+b)² = a²+b²": {
        "conjecture": "(a + b)² = a² + b² for all real a, b.",
        "proof": "Expand (a + b)² = a² + ab + ba + b² = a² + 2ab + b². Since multiplication is commutative, 2ab = 0. Therefore (a + b)² = a² + b².",
    },
}

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")
    model = st.selectbox(
        "Model",
        ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
        index=0,
    )
    n_skeptics = st.slider("Number of Skeptics", min_value=1, max_value=3, value=1)
    st.divider()
    st.header("Raw JSON")
    if "result" in st.session_state:
        r = st.session_state.result
        with st.expander("ProverOutput"):
            st.json(r.prover_output)
        with st.expander("SkepticReport"):
            st.json(r.skeptic_report)
        with st.expander("JudgeVerdict"):
            st.json(r.judge_verdict)
        with st.expander("LeanSearch"):
            st.json(r.lean_search)

# ── Input area ─────────────────────────────────────────────────────────────────

col_input, col_examples = st.columns([3, 1])

with col_examples:
    st.write("**Load example:**")
    for label, ex in EXAMPLES.items():
        if st.button(label, use_container_width=True):
            st.session_state["conjecture"] = ex["conjecture"]
            st.session_state["proof"] = ex["proof"]
            st.session_state["input_tab"] = 0
            st.rerun()

# Input state
conjecture = ""
proof = ""
submit = False
extraction_method = None

with col_input:
    tab_type, tab_photo = st.tabs(["Type proof", "Upload photo"])

    # ── Tab 1: Type ──────────────────────────────────────────────────────────
    with tab_type:
        conjecture = st.text_input(
            "Conjecture",
            value=st.session_state.get("conjecture", ""),
            placeholder="For all integers n, n² + n is even.",
        )
        if conjecture.strip():
            st.markdown(conjecture)

        proof = st.text_area(
            "Proof",
            value=st.session_state.get("proof", ""),
            placeholder="Write the proof here...",
            height=150,
        )
        if proof.strip():
            st.markdown(proof)

        submit = st.button("Submit to Committee", type="primary", use_container_width=True, key="submit_type")

    # ── Tab 2: Photo ─────────────────────────────────────────────────────────
    with tab_photo:
        img_file = st.file_uploader("Upload a photo of a proof", type=["jpg", "jpeg", "png"], key="img_upload")
        if img_file:
            suffix = Path(img_file.name).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(img_file.read())
                tmp_path = tmp.name

            st.image(img_file, use_container_width=True)

            with st.spinner("Extracting proof from image..."):
                from orchestrator import _call_worker
                from pathlib import Path as _Path
                extracted = _call_worker(
                    _Path("workers/pdf_extractor.py"),
                    {"file_path": tmp_path, "file_type": "image"},
                )

            if extracted.get("error") and not extracted.get("conjecture"):
                st.error(f"Extraction failed: {extracted['error']}")
            else:
                extraction_method = extracted.get("extraction_method")
                conjecture = st.text_input(
                    "Conjecture (edit if needed)",
                    value=extracted.get("conjecture") or "",
                    key="img_conjecture",
                )
                proof = st.text_area(
                    "Proof (edit if needed)",
                    value=extracted.get("proof") or "",
                    height=150,
                    key="img_proof",
                )
                if extraction_method:
                    st.caption(f"Extracted via {extraction_method}")
                submit = st.button("Submit to Committee", type="primary", use_container_width=True, key="submit_img")

# ── Run pipeline ───────────────────────────────────────────────────────────────

if submit:
    if not conjecture.strip() or not proof.strip():
        st.error("Please enter both a conjecture and a proof.")
    else:
        st.session_state.pop("result", None)

        # Agent status badges
        badge_cols = st.columns(3)
        prover_badge = badge_cols[0].status("Prover", state="running")
        skeptic_badge = badge_cols[1].status("Skeptic", state="running")
        judge_badge = badge_cols[2].status("Judge", state="running")

        timeline_placeholder = st.empty()
        timeline_messages = []

        def render_timeline():
            with timeline_placeholder.container():
                st.subheader("Timeline")
                for msg in timeline_messages:
                    role = msg.role
                    color = {"PROVER": "blue", "SKEPTIC": "red", "JUDGE": "green"}.get(role, "gray")
                    st.markdown(
                        f"<span style='color:{color};font-weight:bold'>[{role}]</span> {msg.content}",
                        unsafe_allow_html=True,
                    )

        try:
            committee = ProofCommittee(model=model)
            result = committee.evaluate(
                conjecture=conjecture,
                proof=proof,
                n_skeptics=n_skeptics,
            )

            # Update badges
            prover_badge.update(label="Prover", state="complete")
            skeptic_badge.update(label="Skeptic", state="complete")
            judge_badge.update(label="Judge", state="complete")

            # Render timeline with simulated delays
            for msg in result.timeline:
                timeline_messages.append(msg)
                render_timeline()
                if msg.delay_ms > 0:
                    time.sleep(msg.delay_ms / 1000)

            st.session_state.result = result

        except Exception as e:
            prover_badge.update(label="Prover", state="error")
            skeptic_badge.update(label="Skeptic", state="error")
            judge_badge.update(label="Judge", state="error")
            st.error(f"Pipeline error: {e}")
            st.stop()

# ── Verdict card ───────────────────────────────────────────────────────────────

if "result" in st.session_state:
    r: CommitteeResult = st.session_state.result

    st.divider()
    verdict_colors = {
        "valid": "green",
        "plausible": "orange",
        "incomplete": "orange",
        "invalid": "red",
        "uncertain": "gray",
    }
    verdict_icons = {
        "valid": "✅",
        "plausible": "🟡",
        "incomplete": "🔶",
        "invalid": "❌",
        "uncertain": "❓",
    }

    color = verdict_colors.get(r.verdict, "gray")
    icon = verdict_icons.get(r.verdict, "❓")

    st.subheader("Verdict")
    col_v, col_c = st.columns([2, 1])
    with col_v:
        st.markdown(
            f"<h2 style='color:{color}'>{icon} {r.verdict_label}</h2>",
            unsafe_allow_html=True,
        )
        st.write(r.explanation)
    with col_c:
        st.metric("Confidence", f"{r.confidence:.0%}")
        if r.issue_step:
            st.metric("Issue at", f"Step {r.issue_step}")

    if r.counterexample:
        st.error(f"**Counterexample:** {r.counterexample}")

    if r.suggestions:
        st.subheader("Suggestions")
        for s in r.suggestions:
            st.info(s)

    if r.lean_statement:
        st.subheader("Lean 4 sketch")
        st.code(r.lean_statement, language="lean")

    # ── Formal Verification ────────────────────────────────────────────────────
    st.subheader("Formal Verification")
    ls = r.lean_search
    if ls.get("mathlib_found"):
        for match in ls["mathlib_matches"]:
            st.success(f"**Found in Mathlib:** `{match['name']}`")
            st.code(match["statement"], language="lean")
            if match.get("docstring"):
                st.caption(match["docstring"])
        if ls.get("lean4web_link"):
            top_name = ls["mathlib_matches"][0]["name"]
            st.link_button(f"▶ Open in Lean 4 Playground · grounded in `{top_name}`", ls["lean4web_link"])
    else:
        st.info("Not found in Mathlib")
        if ls.get("lean4web_link"):
            st.link_button("▶ Open in Lean 4 Playground (sketch unverified)", ls["lean4web_link"])

    st.caption(f"Completed in {r.duration_ms}ms · Model: {r.model} · {r.timestamp}")
