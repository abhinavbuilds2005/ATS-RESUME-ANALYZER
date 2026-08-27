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

# Auth state. Populated by Supabase sign-in / sign-up / OAuth.
# All four are None when signed out, all four are set when signed in.
for key, default in [
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

# -----------------------------------------------------------------------------
# OAuth Callback Handler
# -----------------------------------------------------------------------------
# Process OAuth response BEFORE rendering components.
# Order:
# 1. Detect if ?code=... is present
# 2. Extract code value immediately
# 3. Read saved PKCE code_verifier
# 4. Exchange code for session with Supabase
# 5. Validate access_token, refresh_token, user_id, email
# 6. Store all four in st.session_state
# 7. Set current_view = 'scorer'
# 8. Clear st.query_params
# 9. Call st.rerun()
# 10. Handle errors cleanly without premature query param deletion
if "code" in st.query_params:
    raw_code = st.query_params.get("code")
    code_val = raw_code[0] if isinstance(raw_code, list) else str(raw_code)

    if code_val and not st.session_state.access_token:
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
            # Validate all required session fields
            acc_token = result.get("access_token")
            ref_token = result.get("refresh_token")
            uid = result.get("user_id")
            mail = result.get("email")

            if acc_token and ref_token and uid and mail:
                st.session_state.access_token = acc_token
                st.session_state.refresh_token = ref_token
                st.session_state.user_id = uid
                st.session_state.user_email = mail
                st.session_state.auth_error = None
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

    from frontend.services import supabase_client

    if st.session_state.access_token:
        # Signed-in state: show email + sign-out button.
        st.caption(f"Signed in as **{st.session_state.user_email}**")
        if st.button("Sign out", use_container_width=True):
            supabase_client.sign_out()
            for k in ("access_token", "refresh_token", "user_id", "user_email", "google_oauth", "google_oauth_verifier"):
                st.session_state[k] = None
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
                result = supabase_client.sign_in_with_password(email, password)
                if "error" in result:
                    st.session_state.auth_error = result["error"]
                else:
                    st.session_state.access_token  = result["access_token"]
                    st.session_state.refresh_token = result["refresh_token"]
                    st.session_state.user_id       = result["user_id"]
                    st.session_state.user_email    = result["email"]
                    st.session_state.current_view  = 'scorer'
                st.rerun()

        with tab_up:
            with st.form("signup_form", clear_on_submit=False):
                email_up = st.text_input("Email", key="signup_email")
                password_up = st.text_input("Password (min 6 chars)", type="password", key="signup_pw")
                submitted_up = st.form_submit_button("Create account", use_container_width=True)
            if submitted_up:
                result = supabase_client.sign_up_with_password(email_up, password_up)
                if "error" in result:
                    st.session_state.auth_error = result["error"]
                elif result.get("pending_confirmation"):
                    st.session_state.auth_info = (
                        f"Check your inbox — confirmation email sent to {result['email']}."
                    )
                else:
                    st.session_state.access_token  = result["access_token"]
                    st.session_state.refresh_token = result["refresh_token"]
                    st.session_state.user_id       = result["user_id"]
                    st.session_state.user_email    = result["email"]
                    st.session_state.current_view  = 'scorer'
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
