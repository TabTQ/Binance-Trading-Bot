#!/usr/bin/env python3
"""
Zerodha Kite Authentication Helper

This script helps you obtain the access token required for Zerodha Kite API.
Zerodha uses OAuth 2.0 flow which requires:
1. Redirecting user to Kite login page
2. User logs in and authorizes the app
3. Kite redirects back with a request_token
4. Exchange request_token for access_token

The access token expires daily at 7:30 AM IST and needs to be refreshed.
"""

from flask import Flask, request, redirect
from kiteconnect import KiteConnect
import zerodha_config as config
import webbrowser
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global Kite instance
kite = KiteConnect(api_key=config.API_KEY)
access_token = None


@app.route('/')
def home():
    """Home page with login button"""
    login_url = kite.login_url()
    return f'''
    <html>
    <head>
        <title>Zerodha Kite Authentication</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: #f5f5f5;
            }}
            .container {{
                text-align: center;
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .btn {{
                background: #387ed1;
                color: white;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 5px;
                font-size: 18px;
                display: inline-block;
                margin-top: 20px;
            }}
            .btn:hover {{
                background: #2d6ab8;
            }}
            code {{
                background: #f0f0f0;
                padding: 2px 6px;
                border-radius: 3px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Zerodha Kite Authentication</h1>
            <p>Click the button below to login to your Zerodha account and authorize the trading bot.</p>
            <p><small>This will redirect you to Kite login page.</small></p>
            <a href="{login_url}" class="btn">Login to Zerodha</a>
            <br><br>
            <p><small>API Key: <code>{config.API_KEY}</code></small></p>
        </div>
    </body>
    </html>
    '''


@app.route('/callback')
def callback():
    """OAuth callback endpoint - Kite redirects here after login"""
    global access_token

    request_token = request.args.get('request_token')

    if not request_token:
        return '''
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error: No request token received</h1>
            <p>Please try logging in again.</p>
            <a href="/">Go back</a>
        </body>
        </html>
        '''

    logger.info(f"Received request_token: {request_token}")

    try:
        # Exchange request token for access token
        data = kite.generate_session(request_token, api_secret=config.API_SECRET)

        access_token = data['access_token']
        user_id = data.get('user_id', 'Unknown')
        user_name = data.get('user_name', 'Unknown')

        logger.info(f"Access token generated successfully!")
        logger.info(f"User: {user_name} ({user_id})")

        # Display success page with access token
        return f'''
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }}
                .container {{
                    text-align: center;
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 800px;
                }}
                .success {{
                    color: #28a745;
                }}
                .token-box {{
                    background: #f0f0f0;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                    word-break: break-all;
                    font-family: monospace;
                    font-size: 14px;
                }}
                .warning {{
                    color: #dc3545;
                    background: #fff3cd;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .instructions {{
                    text-align: left;
                    background: #e7f3ff;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                code {{
                    background: #f0f0f0;
                    padding: 2px 6px;
                    border-radius: 3px;
                }}
                .copy-btn {{
                    background: #387ed1;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="success">Authentication Successful!</h1>
                <p>Welcome, <strong>{user_name}</strong> ({user_id})</p>

                <h3>Your Access Token:</h3>
                <div class="token-box" id="token">
                    {access_token}
                </div>
                <button class="copy-btn" onclick="copyToken()">Copy Token</button>

                <div class="warning">
                    <strong>Important:</strong> This access token expires daily at 7:30 AM IST.
                    You will need to regenerate it every day before trading.
                </div>

                <div class="instructions">
                    <h4>Next Steps:</h4>
                    <ol>
                        <li>Open <code>zerodha_config.py</code></li>
                        <li>Replace the <code>ACCESS_TOKEN</code> value with the token above</li>
                        <li>Save the file</li>
                        <li>Run <code>python zerodha_bot.py</code> to start trading</li>
                    </ol>
                </div>

                <p><small>You can close this window and stop the authentication server (Ctrl+C in terminal).</small></p>
            </div>
            <script>
                function copyToken() {{
                    const token = document.getElementById('token').innerText;
                    navigator.clipboard.writeText(token).then(() => {{
                        alert('Token copied to clipboard!');
                    }});
                }}
            </script>
        </body>
        </html>
        '''

    except Exception as e:
        logger.error(f"Error generating session: {e}")
        return f'''
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error generating access token</h1>
            <p>{str(e)}</p>
            <p>Please check your API credentials and try again.</p>
            <a href="/">Go back</a>
        </body>
        </html>
        '''


def main():
    """Main function to start authentication server"""
    print("=" * 50)
    print("Zerodha Kite Authentication Server")
    print("=" * 50)
    print()
    print(f"API Key: {config.API_KEY}")
    print()

    if config.API_KEY == 'your_api_key_here':
        print("ERROR: Please update your API credentials in zerodha_config.py first!")
        sys.exit(1)

    print("Starting authentication server on http://127.0.0.1:5000")
    print("Opening browser automatically...")
    print()
    print("If browser doesn't open, manually visit: http://127.0.0.1:5000")
    print()
    print("Press Ctrl+C to stop the server after getting your access token.")
    print()

    # Open browser automatically
    webbrowser.open('http://127.0.0.1:5000')

    # Start Flask server
    app.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == "__main__":
    main()
