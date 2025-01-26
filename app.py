# Standard library imports
import datetime
import base64

# Third-party imports
import streamlit as st
import pandas as pd
from st_google_auth import GoogleAuth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import searchconsole

# Configuration constants
SEARCH_TYPES = ["web", "image", "video", "news", "discover", "googleNews"]
DATE_RANGE_OPTIONS = [
    "Last 7 Days", "Last 30 Days", "Last 3 Months",
    "Last 6 Months", "Last 12 Months", "Last 16 Months", "Custom Range"
]
BASE_DIMENSIONS = ["page", "query", "country", "date"]
MAX_ROWS = 1_000_000
DF_PREVIEW_ROWS = 100

# --------------------
# Authentication Setup
# --------------------

def setup_authentication():
    """Handles Google authentication using st-google-auth"""
    gauth = GoogleAuth(
        client_id=st.secrets["google_auth"]["client_id"],
        client_secret=st.secrets["google_auth"]["client_secret"],
        redirect_uri=st.secrets["google_auth"]["redirect_uri"],
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    
    if 'credentials' not in st.session_state:
        st.session_state.credentials = None
    
    # Handle authentication flow
    if not st.session_state.credentials:
        auth_url = gauth.get_authorization_url()
        st.markdown(f'[🔑 Login with Google]({auth_url})', unsafe_allow_html=True)
        return None
    
    # Process callback after login
    if st.experimental_get_query_params().get('code'):
        code = st.experimental_get_query_params()['code'][0]
        st.session_state.credentials = gauth.get_credentials(code)
        st.experimental_set_query_params()  # Clear URL parameters
    
    return st.session_state.credentials

# --------------------
# Core Application
# --------------------

def setup_streamlit():
    """Configures Streamlit page settings"""
    st.set_page_config(
        page_title="Google Search Console Connector",
        layout="wide",
        page_icon="📊"
    )
    st.title("Google Search Console Data Connector")
    st.markdown(f"### Extract and Analyze Search Performance Data (Max {MAX_ROWS:,} Rows)")
    st.divider()

def init_session_state():
    """Initializes session state variables"""
    defaults = {
        'selected_property': None,
        'selected_search_type': 'web',
        'selected_date_range': 'Last 7 Days',
        'start_date': datetime.date.today() - datetime.timedelta(days=7),
        'end_date': datetime.date.today(),
        'selected_dimensions': ['page', 'query'],
        'custom_start_date': datetime.date.today() - datetime.timedelta(days=7),
        'custom_end_date': datetime.date.today()
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --------------------
# Data Operations
# --------------------

def list_gsc_properties(credentials):
    """Fetches list of available GSC properties"""
    service = build('webmasters', 'v3', credentials=credentials)
    site_list = service.sites().list().execute()
    return [site['siteUrl'] for site in site_list.get('siteEntry', [])] or ["No properties found"]

def fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions):
    """Fetches and processes GSC data with proper formatting"""
    try:
        query = webproperty.query.range(start_date, end_date)
        query = query.search_type(search_type).dimension(*dimensions)
        df = query.limit(MAX_ROWS).get().to_dataframe()
        
        if not df.empty:
            # Format metrics
            df = df.rename(columns={
                'position': 'Avg Pos',
                'ctr': 'URL CTR'
            })
            if 'URL CTR' in df.columns:
                df['URL CTR'] = (df['URL CTR'] * 100).round(2).astype(str) + '%'
            if 'Avg Pos' in df.columns:
                df['Avg Pos'] = df['Avg Pos'].round(1)
        
        return df
    
    except Exception as e:
        st.error(f"Data fetch error: {str(e)}")
        return pd.DataFrame()

# --------------------
# UI Components
# --------------------

def show_property_selector(properties):
    """Displays GSC property selector"""
    return st.selectbox(
        "Select Search Console Property:",
        properties,
        index=0
    )

def show_date_selector():
    """Displays date range selector"""
    col1, col2 = st.columns(2)
    with col1:
        date_range = st.selectbox(
            "Date Range:",
            DATE_RANGE_OPTIONS,
            index=DATE_RANGE_OPTIONS.index(st.session_state.selected_date_range)
        )
    
    with col2:
        if date_range == 'Custom Range':
            st.session_state.custom_start_date = st.date_input("Start Date", st.session_state.custom_start_date)
            st.session_state.custom_end_date = st.date_input("End Date", st.session_state.custom_end_date)
    
    return date_range

def show_dimension_selector():
    """Displays dimension selector"""
    return st.multiselect(
        "Select Dimensions:",
        BASE_DIMENSIONS + ['device'],
        default=st.session_state.selected_dimensions
    )

# --------------------
# Main Application
# --------------------

def main():
    setup_streamlit()
    credentials = setup_authentication()
    
    if not credentials:
        return  # Stop execution if not authenticated
    
    init_session_state()
    
    try:
        # Fetch and display GSC properties
        properties = list_gsc_properties(credentials)
        selected_property = show_property_selector(properties)
        
        # Date selection
        date_range = show_date_selector()
        
        # Calculate date range
        if date_range == 'Custom Range':
            start_date = st.session_state.custom_start_date
            end_date = st.session_state.custom_end_date
        else:
            start_date, end_date = calc_date_range(date_range)
        
        # Dimension selection
        dimensions = show_dimension_selector()
        
        # Search type selection
        search_type = st.selectbox("Search Type:", SEARCH_TYPES)
        
        # Fetch data button
        if st.button("🚀 Fetch Data", type="primary"):
            with st.spinner("Fetching data from Google Search Console..."):
                account = searchconsole.authenticate(credentials=credentials)
                webproperty = account[selected_property]
                report = fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions)
                
                if not report.empty:
                    st.success(f"Successfully fetched {len(report)} rows!")
                    with st.expander("📊 Data Preview", expanded=True):
                        st.dataframe(report.head(DF_PREVIEW_ROWS))
                    
                    # Generate download link
                    csv = report.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name="gsc_data.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No data found for the selected parameters")

    except Exception as e:
        st.error(f"Application error: {str(e)}")

def calc_date_range(selection):
    """Calculates date range from selection"""
    range_map = {
        'Last 7 Days': 7,
        'Last 30 Days': 30,
        'Last 3 Months': 90,
        'Last 6 Months': 180,
        'Last 12 Months': 365,
        'Last 16 Months': 480
    }
    today = datetime.date.today()
    return today - datetime.timedelta(days=range_map.get(selection, 0)), today

if __name__ == "__main__":
    main()
