# Standard library imports
import datetime
import base64

# Related third-party imports
import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pandas as pd
import searchconsole

# Configuration: Set to False for Streamlit Cloud deployment
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
# Data Formatting Functions
# -------------

def format_gsc_data(df):
    """
    Formats the Google Search Console data with proper formatting for CTR and Average Position.
    """
    if not df.empty:
        # Format CTR as percentage
        if 'ctr' in df.columns:
            df['ctr'] = df['ctr'].apply(lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "0.00%")
        
        # Format average position to 2 decimal places
        if 'position' in df.columns:
            df['position'] = df['position'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")
    
    return df


# -------------
# Streamlit App Configuration
# -------------

def setup_streamlit():
    """
    Configures Streamlit's page settings and displays the app title and markdown information.
    Sets the page layout, title, and markdown content with links and app description.
    """
    st.set_page_config(
        page_title="Google Search Console Connector",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊Google Search Console Connector")
    st.markdown("### 🚀 Lightweight GSC Data Extractor (Max {:,} Rows)".format(MAX_ROWS))

    st.markdown("### 🛠️ Features")
    st.markdown("""
    - Multiple search types (web, image, video, etc.)
    - Flexible date ranges
    - Custom dimension selection
    - CSV export
    - Automatic data formatting
    """)
    st.divider()


def init_session_state():
    """
    Initialises or updates the Streamlit session state variables for property selection,
    search type, date range, dimensions, and device type.
    """
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
    """
    Loads the Google API client configuration from Streamlit secrets.
    Returns a dictionary with the client configuration for OAuth.
    """
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
    """
    Initialises the OAuth flow for Google API authentication using the client configuration.
    Sets the necessary scopes and returns the configured Flow object.
    """
    scopes = ["https://www.googleapis.com/auth/webmasters"]
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=client_config["installed"]["redirect_uris"][0],
    )


def google_auth(client_config):
    """
    Starts the Google authentication process using OAuth.
    Generates and returns the OAuth flow and the authentication URL.
    """
    flow = init_oauth_flow(client_config)
    auth_url, _ = flow.authorization_url(prompt="consent")
    return flow, auth_url


def auth_search_console(client_config, credentials):
    """
    Authenticates the user with the Google Search Console API using provided credentials.
    Returns an authenticated searchconsole client.
    """
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
    """
    Lists all Google Search Console properties accessible with the given credentials.
    Returns a list of property URLs or a message if no properties are found.
    """
    service = build('webmasters', 'v3', credentials=credentials)
    site_list = service.sites().list().execute()
    return [site['siteUrl'] for site in site_list.get('siteEntry', [])] or ["No properties found"]


def fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """
    Fetches Google Search Console data for a specified property, date range, dimensions, and device type.
    Handles errors and returns the data as a DataFrame.
    """
    query = webproperty.query.range(start_date, end_date).search_type(search_type).dimension(*dimensions)

    if 'device' in dimensions and device_type and device_type != 'All Devices':
        query = query.filter('device', 'equals', device_type.lower())

    try:
        df = query.limit(MAX_ROWS).get().to_dataframe()
        return format_gsc_data(df)  # Format the data before returning
    except Exception as e:
        show_error(e)
        return pd.DataFrame()


def fetch_data_loading(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """
    Fetches Google Search Console data with a loading indicator. Utilises 'fetch_gsc_data' for data retrieval.
    Returns the fetched data as a DataFrame.
    """
    with st.spinner('Fetching data...'):
        return fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type)


# -------------
# Utility Functions
# -------------

def update_dimensions(selected_search_type):
    """
    Updates and returns the list of dimensions based on the selected search type.
    Adds 'device' to dimensions if the search type requires it.
    """
    return BASE_DIMENSIONS + ['device'] if selected_search_type in SEARCH_TYPES else BASE_DIMENSIONS


def calc_date_range(selection, custom_start=None, custom_end=None):
    """
    Calculates the date range based on the selected range option.
    Returns the start and end dates for the specified range.
    """
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
        if custom_start and custom_end:
            return custom_start, custom_end
        else:
            return today - datetime.timedelta(days=7), today
    return today - datetime.timedelta(days=range_map.get(selection, 0)), today


def show_error(e):
    """
    Displays an error message in the Streamlit app.
    Formats and shows the provided error 'e'.
    """
    error_message = str(e)
    st.error(f"""
    ❌ Error: {error_message}
    
    If this persists:
    1. Check your Google Search Console access
    2. Try signing out and back in
    3. Verify your date range selection
    """)


def property_change():
    """
    Updates the 'selected_property' in the Streamlit session state.
    Triggered on change of the property selection.
    """
    st.session_state.selected_property = st.session_state['selected_property_selector']


# -------------
# File & Download Operations
# -------------

def show_dataframe(report):
    """
    Shows a preview of the first 100 rows of the report DataFrame in an expandable section.
    """
    with st.expander("👁️ Preview Data (First {} Rows)".format(DF_PREVIEW_ROWS)):
        st.dataframe(
            report.head(DF_PREVIEW_ROWS),
            use_container_width=True,
            hide_index=True
        )


def download_csv_link(report):
    """
    Generates and displays a download link for the report DataFrame in CSV format.
    """
    csv = report.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    filename = "gsc_data_{}.csv".format(
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    st.download_button(
        label="📥 Download Full Report as CSV",
        data=csv,
        file_name=filename,
        mime="text/csv",
        help="Click to download the complete dataset as a CSV file"
    )


# -------------
# Streamlit UI Components
# -------------

def show_google_sign_in(auth_url):
    """
    Displays the Google sign-in button and authentication URL in the Streamlit sidebar.
    """
    st.sidebar.markdown("### Authentication")
    st.sidebar.info("To use this app, you need to authenticate with your Google Search Console account. Your data remains private and is not stored anywhere.")
    
    if st.sidebar.button("🔐 Sign in with Google"):
        st.sidebar.markdown("### Next Steps:")
        st.sidebar.markdown("""
        1. Click the link below to sign in
        2. Choose your Google account
        3. Review and accept the permissions
        4. You'll be redirected back automatically
        """)
        st.sidebar.markdown(f'[🔑 Authenticate with Google]({auth_url})', unsafe_allow_html=True)


def show_property_selector(properties, account):
    """
    Displays a dropdown selector for Google Search Console properties.
    Returns the selected property's webproperty object.
    """
    st.markdown("### 🌐 Select Property")
    
    if not properties:
        st.warning("⚠️ No properties found. Please make sure you have access to Google Search Console properties.")
        return None
        
    property_urls = [prop.url for prop in properties]
    
    selected = st.selectbox(
        "Choose a property:",
        property_urls,
        key="selected_property",
        on_change=property_change,
        help="Select the website you want to analyze"
    )
    
    return account[selected]


def show_search_type_selector():
    """
    Displays a dropdown selector for choosing the search type.
    Returns the selected search type.
    """
    st.markdown("### 🔎 Search Type")
    return st.selectbox(
        "Select search type:",
        SEARCH_TYPES,
        help="Choose the type of search data you want to analyze"
    )


def show_date_range_selector():
    """
    Displays a dropdown selector for choosing the date range.
    Returns the selected date range option.
    """
    st.markdown("### 📅 Date Range")
    return st.selectbox(
        "Select date range:",
        DATE_RANGE_OPTIONS,
        help="Choose the time period for your data"
    )


def show_custom_date_inputs():
    """
    Displays date input fields for custom date range selection.
    Updates session state with the selected dates.
    """
    st.session_state.custom_start_date = st.date_input("Start Date", st.session_state.custom_start_date)
    st.session_state.custom_end_date = st.date_input("End Date", st.session_state.custom_end_date)


def show_dimensions_selector(search_type):
    """
    Displays a multi-select box for choosing dimensions based on the selected search type.
    Returns the selected dimensions.
    """
    st.markdown("### 📊 Dimensions")
    dimensions = update_dimensions(search_type)
    
    return st.multiselect(
        "Select dimensions:",
        dimensions,
        default=["query", "page"],
        help="Choose the data dimensions you want to include in your report"
    )


def show_fetch_data_button(webproperty, search_type, start_date, end_date, selected_dimensions):
    """
    Displays a button to fetch data based on selected parameters.
    Shows the report DataFrame and download link upon successful data fetching.
    """
    if st.button("🔄 Fetch Data", help="Click to retrieve your GSC data"):
        try:
            with st.spinner("🔄 Fetching data from Google Search Console..."):
                report = fetch_data_loading(
                    webproperty,
                    search_type,
                    start_date,
                    end_date,
                    selected_dimensions
                )
            
            if report is not None and not report.empty:
                st.success("✅ Data fetched successfully! {} rows retrieved.".format(len(report)))
                show_dataframe(report)
                download_csv_link(report)
            else:
                st.warning("⚠️ No data found for the selected criteria. Try adjusting your filters.")
        except Exception as e:
            show_error(e)


# -------------
# Main Streamlit App Function
# -------------

def main():
    """
    The main function for the Streamlit application.
    Handles the app setup, authentication, UI components, and data fetching logic.
    """
    setup_streamlit()
    
    # Add welcome message and instructions
    if not st.session_state.get('credentials'):
        st.markdown("""
        ## Welcome to the GSC Data Connector! 👋
        
        This app allows you to easily fetch and analyze your Google Search Console data.
        To get started:
        
        1. Click the "Sign in with Google" button in the sidebar
        2. Authorize the app to access your GSC data
        3. Select your property and customize your report
        
        Your data remains private and secure - no data is stored on our servers.
        """)
    
    client_config = load_config()
    st.session_state.auth_flow, st.session_state.auth_url = google_auth(client_config)

    query_params = st.experimental_get_query_params()
    auth_code = query_params.get("code", [None])[0]

    if auth_code and not st.session_state.get('credentials'):
        with st.spinner('Completing authentication...'):
            st.session_state.auth_flow.fetch_token(code=auth_code)
            st.session_state.credentials = st.session_state.auth_flow.credentials
        st.success('Successfully authenticated! You can now access your GSC data.')
        st.rerun()

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
