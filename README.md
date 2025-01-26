# Google Search Console Data Connector

A Streamlit-based application for fetching and analyzing Google Search Console data with proper formatting for metrics like CTR and Average Position.

## Features

- 🔐 Secure Google OAuth2 authentication
- 📊 Data fetching with customizable parameters:
  - Multiple search types (web, image, video, news, discover, googleNews)
  - Flexible date ranges (7 days to 16 months)
  - Custom dimension selection
  - Device filtering
- 📈 Properly formatted metrics:
  - CTR displayed as percentages (e.g., "12.34%")
  - Average Position with 2 decimal places (e.g., "4.56")
- 💾 Export capabilities:
  - Preview first 100 rows
  - Download complete data as CSV
- 🎯 Support for up to 1,000,000 rows of data

## Prerequisites

- Python 3.8 or higher
- Google Search Console API access
- Google OAuth2 credentials

## Installation

1. Clone the repository or download the source code
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Set up Google Search Console API:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the Google Search Console API
   - Create OAuth2 credentials (Desktop application type)
   - Download the client configuration file

2. Create a `.streamlit/secrets.toml` file in your project directory:
```toml
[installed]
client_id = "your-client-id"
client_secret = "your-client-secret"
redirect_uris = ["http://localhost:8501"]
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run gsc_script.py
```

2. Follow the authentication flow:
   - Click "Sign in with Google"
   - Authorize the application
   - Select your Search Console property

3. Configure your data fetch:
   - Choose search type (web, image, etc.)
   - Select date range
   - Pick dimensions (page, query, country, date)
   - Click "Fetch Data"

4. View and download your data:
   - Preview the first 100 rows
   - Download complete dataset as CSV

## Data Formatting

The application automatically formats the following metrics:
- **CTR (Click-Through Rate)**: Displayed as percentage with 2 decimal places
  - Example: 0.1234 → "12.34%"
- **Average Position**: Displayed with 2 decimal places
  - Example: 4.5647382 → "4.56"

## Limitations

- Maximum of 1,000,000 rows per data fetch
- Date range limited to 16 months
- API quotas apply as per Google Search Console API limits

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## Credits

Created by [Lee Foot](https://leefoot.co.uk/)
- Website: [https://leefoot.co.uk/](https://leefoot.co.uk/)
- Twitter: [@LeeFootSEO](https://twitter.com/LeeFootSEO)
- LinkedIn: [Lee Foot](https://www.linkedin.com/in/lee-foot/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
