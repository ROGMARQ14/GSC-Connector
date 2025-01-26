# Standard library imports
import datetime
import base64

# Related third-party imports
import streamlit as st
import pandas as pd
import searchconsole

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
    """
    Configures Streamlit's page settings and displays the app title and markdown information.
    """
    st.set_page_config(page_title="Google Search Console Connector", layout="wide")
    st.title("Google Search Console Connector")
    st.markdown(f"### Lightweight GSC Data Extractor. (Max {MAX_ROWS:,} Rows)")
    st.divider()


def init_session_state():
    """
    Initialises or updates the Streamlit session state variables.
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
# Authentication Functions
# -------------

def authenticate_gsc():
    """
    Authenticates with Google Search Console using OAuth2.
    Returns an authenticated account object.
    """
    if 'account' not in st.session_state:
        st.sidebar.info("🔐 Sign in with your Google account to access Search Console data")
        if st.sidebar.button("Sign in with Google"):
            try:
                account = searchconsole.authenticate(
                    client_config='client_secrets.json',
                    serialize='credentials.json'
                )
                st.session_state.account = account
                st.success("✅ Successfully authenticated!")
                st.rerun()
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
                return None
    
    return st.session_state.get('account')


# -------------
# Data Fetching Functions
# -------------

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
        
        # Format CTR, position, impressions, and clicks
        if 'ctr' in df.columns:
            df['ctr'] = df['ctr'].apply(lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "0.00%")
        if 'position' in df.columns:
            df['position'] = df['position'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")
        if 'impressions' in df.columns:
            df['impressions'] = df['impressions'].apply(lambda x: f"{x:,}" if pd.notnull(x) else "0")
        if 'clicks' in df.columns:
            df['clicks'] = df['clicks'].apply(lambda x: f"{x:,}" if pd.notnull(x) else "0")
            
        return df
    except Exception as e:
        show_error(e)
        return pd.DataFrame()


def fetch_data_loading(webproperty, search_type, start_date, end_date, dimensions, device_type=None):
    """
    Fetches Google Search Console data with a loading indicator.
    """
    with st.spinner('Fetching data...'):
        return fetch_gsc_data(webproperty, search_type, start_date, end_date, dimensions, device_type)


# -------------
# Utility Functions
# -------------

def update_dimensions(selected_search_type):
    """Updates dimensions based on search type"""
    return BASE_DIMENSIONS + ['device'] if selected_search_type in SEARCH_TYPES else BASE_DIMENSIONS


def calc_date_range(selection, custom_start=None, custom_end=None):
    """Calculates date range based on selection"""
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
    """Shows error message"""
    st.error(f"An error occurred: {e}")


def property_change():
    """Updates selected property"""
    st.session_state.selected_property = st.session_state['selected_property_selector']


# -------------
# File & Download Operations
# -------------

def show_dataframe(report):
    """Shows data preview"""
    with st.expander("Preview the First 100 Rows"):
        st.dataframe(report.head(DF_PREVIEW_ROWS))


def download_csv_link(report):
    """Creates download link"""
    def to_csv(df):
        return df.to_csv(index=False, encoding='utf-8-sig')

    csv = to_csv(report)
    b64_csv = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64_csv}" download="search_console_data.csv">Download CSV File</a>'
    st.markdown(href, unsafe_allow_html=True)


# -------------
# Streamlit UI Components
# -------------

def show_property_selector(properties, account):
    """Shows property selector"""
    selected_property = st.selectbox(
        "Select a Search Console Property:",
        properties,
        index=0 if not st.session_state.selected_property else properties.index(st.session_state.selected_property),
        key='selected_property_selector',
        on_change=property_change
    )
    return account[selected_property]


def show_search_type_selector():
    """Shows search type selector"""
    return st.selectbox(
        "Select Search Type:",
        SEARCH_TYPES,
        index=SEARCH_TYPES.index(st.session_state.selected_search_type),
        key='search_type_selector'
    )


def show_date_range_selector():
    """Shows date range selector"""
    return st.selectbox(
        "Select Date Range:",
        DATE_RANGE_OPTIONS,
        index=DATE_RANGE_OPTIONS.index(st.session_state.selected_date_range),
        key='date_range_selector'
    )


def show_custom_date_inputs():
    """Shows custom date inputs"""
    st.session_state.custom_start_date = st.date_input("Start Date", st.session_state.custom_start_date)
    st.session_state.custom_end_date = st.date_input("End Date", st.session_state.custom_end_date)


def show_dimensions_selector(search_type):
    """Shows dimensions selector"""
    available_dimensions = update_dimensions(search_type)
    return st.multiselect(
        "Select Dimensions:",
        available_dimensions,
        default=st.session_state.selected_dimensions,
        key='dimensions_selector'
    )


def show_fetch_data_button(webproperty, search_type, start_date, end_date, selected_dimensions):
    """Shows fetch data button and handles data fetching"""
    if st.button("Fetch Data"):
        report = fetch_data_loading(webproperty, search_type, start_date, end_date, selected_dimensions)
        if report is not None:
            show_dataframe(report)
            download_csv_link(report)


# -------------
# Main App
# -------------

def main():
    """Main app function"""
    setup_streamlit()
    init_session_state()
    
    # Authenticate
    account = authenticate_gsc()
    
    if account:
        # Show main interface
        properties = account.webproperties
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
