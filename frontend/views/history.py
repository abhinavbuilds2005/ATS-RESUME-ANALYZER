import requests
import streamlit as st

from frontend.services import api_client


def _show_backend_error(exc: Exception) -> None:
    if isinstance(exc, api_client.BackendConfigError):
        st.error(f"⚠️ Configuration Error: {exc}")
    elif isinstance(exc, requests.ConnectionError):
        st.error("Could not reach the backend API. If running locally, start the backend with `uvicorn backend.main:app --port 8000`.")
    elif isinstance(exc, requests.HTTPError) and exc.response is not None:
        st.error(f"Backend returned {exc.response.status_code}: {exc.response.text}")
    else:
        st.error(f"Unexpected error: {exc}")



def render() -> None:
    st.title("📊 Analysis History")
    st.markdown("Past analyses saved against your account.")

    access_token = st.session_state.get("access_token")
    if not access_token:
        st.warning("⚠️ Sign in from the sidebar to view your history.")
        return

    try:
        history = api_client.get_history(access_token)
    except requests.RequestException as exc:
        _show_backend_error(exc)
        return

    if not history:
        st.info("No analyses yet for this account. Run a scoring on the ATS Scorer page first.")
        if st.button("🎯 Go to ATS Scorer"):
            st.session_state.current_view = "scorer"
            st.rerun()
        return

    st.markdown(f"**Total analyses:** {len(history)}")
    st.markdown("---")

    for idx, entry in enumerate(history):
        filename = entry.get("filename", "resume")
        ats_score = float(entry.get("ats_score", 0))
        created_at = entry.get("created_at", "")
        analysis = entry.get("analysis_result", {}) or {}

        component_scores = analysis.get("component_scores", {}) or {}
        jd_comparison = analysis.get("jd_comparison") or analysis.get("jd_match_analysis")

        with st.expander(f"📄 {filename} — Score: {ats_score:.0f}/100 — {created_at}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Overall", f"{ats_score:.0f}/100")
                st.metric("Formatting", f"{component_scores.get('formatting', 0):.0f}/20")
            with c2:
                st.metric("Keywords", f"{component_scores.get('keywords', 0):.0f}/25")
                st.metric("Content", f"{component_scores.get('content', 0):.0f}/25")
            with c3:
                st.metric("Skill Validation", f"{component_scores.get('skill_validation', 0):.0f}/15")
                st.metric("ATS Compatibility", f"{component_scores.get('ats_compatibility', 0):.0f}/15")

            if jd_comparison:
                st.markdown(f"**JD Match:** {jd_comparison.get('match_percentage', 0):.0f}%")

            entry_id = entry.get("id")
            if entry_id:
                btn_col1, btn_col2 = st.columns(2)
                pdf_key = f"pdf_bytes_{entry_id}"
                with btn_col1:
                    if st.button("📑 Get PDF Report", key=f"get_pdf_{idx}", use_container_width=True):
                        try:
                            with st.spinner("Fetching PDF report..."):
                                pdf_data = api_client.get_history_pdf(str(entry_id), access_token)
                            st.session_state[pdf_key] = pdf_data
                        except requests.RequestException as exc:
                            _show_backend_error(exc)

                    if pdf_key in st.session_state:
                        st.download_button(
                            "⬇️ Save PDF",
                            data=st.session_state[pdf_key],
                            file_name=f"ats_report_{filename}.pdf",
                            mime="application/pdf",
                            key=f"download_pdf_{idx}",
                            use_container_width=True,
                        )

                with btn_col2:
                    if st.button("🗑️ Delete", key=f"delete_{idx}", use_container_width=True):
                        try:
                            api_client.delete_history_entry(str(entry_id), access_token)
                            st.session_state.pop(pdf_key, None)
                            st.success("Deleted.")
                            st.rerun()
                        except requests.RequestException as exc:
                            _show_backend_error(exc)
