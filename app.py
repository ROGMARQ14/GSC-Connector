# Standard library imports
import datetime
import base64

# Related third-party imports
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pandas as pd
import searchconsole

# Configuration: Set to True if running locally, False if running on Streamlit Cloud
# IS_LOCAL = True
IS_LOCAL = False

# Constants
SEARCH_TYPES = ["web", "image", "video", "news", "discover", "googleNews"]
DATE_RANGE_OPTIONS = [
    "Last 7 Days",
    "Last 30 Days",
    "Last 3 Months",
    "Last 6 Months",
    "Last 12 Months",
    "Last 16 Months",
    "Custom Range"
]
DEVICE_OPTIONS = ["All Devices", "desktop", "mobile", "tablet"]
BASE_DIMENSIONS = ["page", "query", "country", "date"]
MAX_ROWS = 1_000_000
DF_PREVIEW_ROWS = 100

# -------------
# Streamlit App Configuration
# -------------

def setup_streamlit():
    """Configures Streamlit's page settings and displays the app title."""
    st.set_page_config(page_title="Google Search Console Connector", layout="wide")
    st.title("Google Search Console Connector")
    st.markdown(f"### Extract and Analyze Your GSC Data (Max {MAX_ROWS:,} Rows)")
    st.divider()

def init_session_state():
    """Initializes session state variables."""
    if 'selected_property' not in st.session_state:
        st.session_state.selected_property = None
    if 'selected_search_type' not in st.session_state:
        st.session_state.selected_search_type = 'web'
    if 'selected_date_range' not in st.session_state:
        st.session_state.selected_date_range = 'Last 7 Days'
    if 'start_date' not in st.session_state:
        st.session_state.start_date = datetime.date.today() - datetime.timedelta(days=7)
    if 'end_date' not in st.session_state:
        st.session_state.end_date = datetime.date.today()
    if 'selected_dimensions' not in st.session_state:
        st.session_state.selected_dimensions = ['page', 'query']
    if 'selected_device' not in st.session_state:
        st.session_state.selected_device = 'All Devices'
    if 'custom_start_date' not in st.session_state:
        st.session_state.custom_start_date = datetime.date.today() - datetime.timedelta(days=7)
    if 'custom_end_date' not in st.session_state:
        st.session_state.custom_end_date = datetime.date.today()

# -------------
# Google Authentication Functions
# -------------

def load_config():
    """Loads Google API client configuration from Streamlit secrets."""
    client_config = {
        "installed": {
            "client_id": str(st.secrets["installed"]["client_id"]),
            "client_secret": str(st.secrets["installed"]["client_secret"]),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://accounts.google.com/o/oauth2/token",
            "redirect_uris": (
                ["http://localhost:8501"]
                if IS_LOCAL
                else [str(st.secrets["installed"]["redirect_uris"][0])]
            ),
        }
    }
    return client_config

def init_oauth_flow(client_config):
    """Initializes OAuth flow for Google API authentication."""
    scopes = ["https://www.googleapis.com/auth/webmasters"]
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=client_config["installed"]["redirect_uris"][0],
    )

def google_auth(client_config):
    """Starts Google authentication process."""
    flow = init_oauth_flow(client_config)
    auth_url, _ = flow.authorization_url(prompt="consent")
    return flow, auth_url

def auth_search_console(client_config, credentials):
    """Authenticates with Google Search Console API."""
    token = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "id_token": getattr(credentials, "id_token", None),
    }
    return searchconsole.authenticate(client_config=client_config, credentials=token)

# -------------
# Data Fetching Functions
# -------------

def list_gsc_properties(credentials):
    """Lists Google Search Console properties."""
    service = build('webmasters', 'v3', credentials=credentials)
    site_list = service.sites().list().execute()
    return [site['siteUrl'] for site in site_list.get('siteEntry', [])] or ["No properties found"]

def fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """Fetches and processes GSC data with metric formatting."""
    query = webproperty.query.range(start_date, end_date).search_type(search_type).dimension(*dimensions)

    if 'device' in dimensions and device_type and device_type != 'All Devices':
        query = query.filter('device', 'equals', device_type.lower())

    try:
        df = query.limit(MAX_ROWS).get().to_dataframe()
        if not df.empty:
            # Rename and format metrics
            df = df.rename(columns={
                'position': 'Avg Pos',
                'ctr': 'URL CTR'
            })
            if 'URL CTR' in df.columns:
                df['URL CTR'] = (df['URL CTR'] * 100).round(2)
            if 'Avg Pos' in df.columns:
                df['Avg Pos'] = df['Avg Pos'].round(1)
        return df
    except Exception as e:
        show_error(e)
        return pd.DataFrame()

def fetch_data_loading(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """Handles data loading with progress indicator."""
    with st.spinner('Fetching data...'):
        return fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type)

# -------------
# Utility Functions
# -------------

def update_dimensions(selected_search_type):
    """Updates dimensions based on search type."""
    return BASE_DIMENSIONS + ['device'] if selected_search_type in SEARCH_TYPES else BASE_DIMENSIONS

def calc_date_range(selection, custom_start=None, custom_end=None):
    """Calculates date range based on selection."""
    range_map = {
        'Last 7 Days': 7,
        'Last 30 Days': 30,
        'Last 3 Months': 90,
        'Last 6 Months': 180,
        'Last 12 Months': 365,
        'Last 16 Months': 480
    }
    today = datetime.date.today()
    if selection == 'Custom Range':
        return (custom_start, custom_end) if custom_start and custom_end else (today - datetime.timedelta(days=7), today)
    return today - datetime.timedelta(days=range_map.get(selection, 0)), today

def show_error(e):
    """Displays error messages."""
    st.error(f"An error occurred: {e}")

def property_change():
    """Handles property selection changes."""
    st.session_state.selected_property = st.session_state['selected_property_selector']

# -------------
# File & Download Operations
# -------------

def show_dataframe(report):
    """Displays a preview of the data."""
    with st.expander("Preview the First 100 Rows"):
        st.dataframe(report.head(DF_PREVIEW_ROWS))

def download_csv_link(report):
    """Generates CSV download link."""
    def to_csv(df):
        return df.to_csv(index=False, encoding='utf-8-sig')
    
    csv = to_csv(report)
    b64_csv = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64_csv}" download="search_console_data.csv">Download CSV File</a>'
    st.markdown(href, unsafe_allow_html=True)

# -------------
# Streamlit UI Components
# -------------

def show_google_sign_in(auth_url):
    """Displays Google sign-in button."""
    with st.sidebar:
        if st.button("Sign in with Google"):
            st.write('Please click the link below to sign in:')
            st.markdown(f'[Google Sign-In]({auth_url})', unsafe_allow_html=True)

def show_property_selector(properties, account):
    """Displays property selector dropdown."""
    selected_property = st.selectbox(
        "Select a Search Console Property:",
        properties,
        index=properties.index(
            st.session_state.selected_property) if st.session_state.selected_property in properties else 0,
        key='selected_property_selector',
        on_change=property_change
    )
    return account[selected_property]

def show_search_type_selector():
    """Displays search type selector."""
    return st.selectbox(
        "Select Search Type:",
        SEARCH_TYPES,
        index=SEARCH_TYPES.index(st.session_state.selected_search_type),
        key='search_type_selector'
    )

def show_date_range_selector():
    """Displays date range selector."""
    return st.selectbox(
        "Select Date Range:",
        DATE_RANGE_OPTIONS,
        index=DATE_RANGE_OPTIONS.index(st.session_state.selected_date_range),
        key='date_range_selector'
    )

def show_custom_date_inputs():
    """Displays custom date inputs."""
    st.session_state.custom_start_date = st.date_input("Start Date", st.session_state.custom_start_date)
    st.session_state.custom_end_date = st.date_input("End Date", st.session_state.custom_end_date)

def show_dimensions_selector(search_type):
    """Displays dimensions selector."""
    available_dimensions = update_dimensions(search_type)
    return st.multiselect(
        "Select Dimensions:",
        available_dimensions,
        default=st.session_state.selected_dimensions,
        key='dimensions_selector'
    )

def show_fetch_data_button(webproperty, search_type, start_date, end_date, selected_dimensions):
    """Displays data fetch button."""
    if st.button("Fetch Data"):
        report = fetch_data_loading(webproperty, search_type, start_date, end_date, selected_dimensions)
        if report is not None and not report.empty:
            show_dataframe(report)
            download_csv_link(report)

# -------------
# Main Function
# -------------

def main():
    """Main application function."""
    setup_streamlit()
    client_config = load_config()
    st.session_state.auth_flow, st.session_state.auth_url = google_auth(client_config)

    query_params = st.experimental_get_query_params()
    auth_code = query_params.get("code", [None])[0]

    if auth_code and not st.session_state.get('credentials'):
        st.session_state.auth_flow.fetch_token(code=auth_code)
        st.session_state.credentials = st.session_state.auth_flow.credentials

    if not st.session_state.get('credentials'):
        show_google_sign_in(st.session_state.auth_url)
    else:
        init_session_state()
        account = auth_search_console(client_config, st.session_state.credentials)
        properties = list_gsc_properties(st.session_state.credentials)

        if properties:
            webproperty = show_property_selector(properties, account)
            search_type = show_search_type_selector()
            date_range_selection = show_date_range_selector()

            if date_range_selection == 'Custom Range':
                show_custom_date_inputs()
                start_date, end_date = st.session_state.custom_start_date, st.session_state.custom_end_date
            else:
                start_date, end_date = calc_date_range(date_range_selection)

            selected_dimensions = show_dimensions_selector(search_type)
            show_fetch_data_button(webproperty, search_type, start_date, end_date, selected_dimensions)

if __name__ == "__main__":
    main()
