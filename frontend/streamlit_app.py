import streamlit as st
import sys
from pathlib import Path

# Put the repo root on sys.path so `from frontend.views import ...` resolves
# regardless of the directory streamlit was launched from.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure page
st.set_page_config(
    page_title="ATS Resume Scorer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 1. Initialize Authentication State
# -----------------------------------------------------------------------------
for key, default in [
    ("auth_session", None),
    ("access_token", None),
    ("refresh_token", None),
    ("user_id", None),       # Supabase auth user id (uuid); also used by api_client
    ("user_email", None),
    ("auth_error", None),
    ("auth_info", None),
    ("google_oauth", None),
    ("google_oauth_verifier", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

from frontend.services import supabase_client

# Restore and synchronize session if present across reruns
supabase_client.restore_auth_session()

print(f"[AUTH DEBUG] ===== NEW STREAMLIT SCRIPT RUN =====", flush=True)
print(f"[AUTH DEBUG] current_view = {st.session_state.get('current_view')}", flush=True)
print(f"[AUTH DEBUG] auth_session exists = {bool(st.session_state.get('auth_session'))}", flush=True)
print(f"[AUTH DEBUG] access_token exists = {bool(st.session_state.get('access_token'))}", flush=True)
print(f"[AUTH DEBUG] refresh_token exists = {bool(st.session_state.get('refresh_token'))}", flush=True)
print(f"[AUTH DEBUG] user_id = {st.session_state.get('user_id')}", flush=True)
print(f"[AUTH DEBUG] user_email = {st.session_state.get('user_email')}", flush=True)
print(f"[AUTH DEBUG] is_authenticated = {supabase_client.is_authenticated()}", flush=True)

# -----------------------------------------------------------------------------
# 2. OAuth Callback Handler
# -----------------------------------------------------------------------------
if "code" in st.query_params:
    raw_code = st.query_params.get("code")
    code_val = raw_code[0] if isinstance(raw_code, list) else str(raw_code)

    if code_val and not supabase_client.is_authenticated():
        saved_verifier = (
            st.session_state.get("google_oauth_verifier")
            or (
                st.session_state.get("google_oauth", {}).get("code_verifier")
                if isinstance(st.session_state.get("google_oauth"), dict)
                else None
            )
        )
        
        result = supabase_client.exchange_code_for_session(code_val, code_verifier=saved_verifier)
        
        if "error" in result:
            st.session_state.auth_error = f"Google sign-in failed: {result['error']}"
            st.query_params.clear()
        else:
            saved = supabase_client.set_auth_session(result)
            if saved:
                st.session_state.current_view = 'scorer'
                st.query_params.clear()
                st.rerun()
            else:
                st.session_state.auth_error = "Google sign-in failed: Incomplete session returned."
                st.query_params.clear()
    else:
        st.query_params.clear()

elif "error" in st.query_params or "error_description" in st.query_params:
    err_msg = (
        st.query_params.get("error_description")
        or st.query_params.get("error_code")
        or st.query_params.get("error")
    )
    if isinstance(err_msg, list):
        err_msg = err_msg[0] if err_msg else "Unknown OAuth error"
    st.session_state.auth_error = f"Google sign-in error: {err_msg}"
    st.query_params.clear()


#Load custom CSS
def load_css():
    try:
        css_path = Path(__file__).parent / 'assets' / 'styles.css'
        with open(css_path, 'r') as f:
            return f'<style>{f.read()}</style>'
    except FileNotFoundError:
        return ''

st.markdown(load_css(), unsafe_allow_html=True)

# Initialize session state for view management
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'landing'

# Sidebar navigation
with st.sidebar:
    st.markdown("## Navigation")
    
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.current_view = 'landing'
        st.rerun()
    
    if st.button("🎯 ATS Scorer", use_container_width=True):
        st.session_state.current_view = 'scorer'
        st.rerun()
    
    if st.button("📊 History", use_container_width=True):
        st.session_state.current_view = 'history'
        st.rerun()
    
    if st.button("📚 Resources", use_container_width=True):
        st.session_state.current_view = 'resources'
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 👤 Account")

    if supabase_client.is_authenticated():
        # Signed-in state: show email + sign-out button.
        st.caption(f"Signed in as **{st.session_state.user_email}**")
        if st.button("Sign out", use_container_width=True):
            supabase_client.sign_out()
            st.session_state.current_view = 'landing'
            st.rerun()
    else:
        # Signed-out state: tabs for sign-in vs sign-up + Google OAuth button.
        if st.session_state.auth_error:
            st.error(st.session_state.auth_error)
            st.session_state.auth_error = None
        if st.session_state.auth_info:
            st.info(st.session_state.auth_info)
            st.session_state.auth_info = None

        tab_in, tab_up = st.tabs(["Sign in", "Sign up"])

        with tab_in:
            with st.form("signin_form", clear_on_submit=False):
                email = st.text_input("Email", key="signin_email")
                password = st.text_input("Password", type="password", key="signin_pw")
                submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.session_state.auth_error = "Please provide both email and password."
                else:
                    result = supabase_client.sign_in_with_password(email, password)
                    if "error" in result:
                        st.session_state.auth_error = result["error"]
                    else:
                        supabase_client.set_auth_session(result)
                        st.session_state.current_view = 'scorer'
                st.rerun()

        with tab_up:
            with st.form("signup_form", clear_on_submit=False):
                email_up = st.text_input("Email", key="signup_email")
                password_up = st.text_input("Password (min 6 chars)", type="password", key="signup_pw")
                submitted_up = st.form_submit_button("Create account", use_container_width=True)
            if submitted_up:
                print(f"[AUTH DEBUG] signup started with email: {email_up}", flush=True)
                if not email_up or not password_up:
                    st.session_state.auth_error = "Please provide both email and password."
                elif len(password_up) < 6:
                    st.session_state.auth_error = "Password must be at least 6 characters."
                else:
                    result = supabase_client.sign_up_with_password(email_up, password_up)
                    print(f"[AUTH DEBUG] signup result received: {list(result.keys()) if isinstance(result, dict) else type(result)}", flush=True)
                    print(f"[AUTH DEBUG] session exists: {'access_token' in result}", flush=True)
                    print(f"[AUTH DEBUG] access token exists: {bool(result.get('access_token'))}", flush=True)
                    print(f"[AUTH DEBUG] refresh token exists: {bool(result.get('refresh_token'))}", flush=True)
                    print(f"[AUTH DEBUG] user id: {result.get('user_id')}", flush=True)
                    print(f"[AUTH DEBUG] email: {result.get('email')}", flush=True)
                    print(f"[AUTH DEBUG] session_state BEFORE set_auth_session: is_auth={supabase_client.is_authenticated()}", flush=True)
                    
                    if "error" in result:
                        st.session_state.auth_error = result["error"]
                    elif result.get("pending_confirmation"):
                        st.session_state.auth_info = (
                            f"Account created! Confirmation email sent to {result['email']}. Please confirm your email before signing in."
                        )
                    else:
                        supabase_client.set_auth_session(result)
                        print(f"[AUTH DEBUG] session_state AFTER set_auth_session: is_auth={supabase_client.is_authenticated()}", flush=True)
                        st.session_state.current_view = 'scorer'
                
                print(f"[AUTH DEBUG] is_authenticated BEFORE rerun: {supabase_client.is_authenticated()}", flush=True)
                print(f"[AUTH DEBUG] current_view BEFORE rerun: {st.session_state.get('current_view')}", flush=True)
                print("[AUTH DEBUG] calling st.rerun()", flush=True)
                st.rerun()

        st.markdown("<div style='text-align:center; margin: 8px 0; color:#94a3b8;'>or</div>",
                    unsafe_allow_html=True)

        if "google_oauth" not in st.session_state or not st.session_state.google_oauth or not st.session_state.google_oauth.get("url"):
            oauth_data = supabase_client.google_oauth_url()
            st.session_state.google_oauth = oauth_data
            if "code_verifier" in oauth_data:
                st.session_state.google_oauth_verifier = oauth_data["code_verifier"]

        oauth = st.session_state.google_oauth
        if "error" in oauth:
            st.caption(f"Google sign-in unavailable: {oauth['error']}")
        else:
            st.link_button(
                "Continue with Google",
                url=oauth["url"],
                use_container_width=True,
            )




# Main content area - render based on current view
if st.session_state.current_view == 'landing':
    # Import and render landing page
    from frontend.views import landing
    landing.render()

elif st.session_state.current_view == 'scorer':
    # Import and render scorer page
    from frontend.views import scorer
    scorer.render()

elif st.session_state.current_view == 'history':
    # Import and render history page
    from frontend.views import history
    history.render()

elif st.session_state.current_view == 'resources':
    # Import and render resources page
    from frontend.views import resources
    resources.render()
