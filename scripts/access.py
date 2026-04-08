#this class is proof
from kiteconnect import KiteConnect

def generate_access_token(api_key, api_secret):
    """
    Generates an access token for the Zerodha Kite SDK.
    """
    # Step 1: Initialize KiteConnect
    kite = KiteConnect(api_key=api_key)
    
    # Step 2: Get the login URL
    login_url = kite.login_url()
    print(f"Login URL: {login_url}")
    print("Please log in using the above URL and obtain the request_token from the redirected URL.")
    
    # Step 3: Input the request token from the redirected URL
    request_token = input("Enter the request_token from the URL: ").strip()
    
    # Step 4: Generate session
    try:
        session_data = kite.generate_session(request_token=request_token, api_secret=api_secret)
        print("Access Token:", session_data["access_token"])
        print("User ID:", session_data["user_id"])
        
        # Save access token for later use (optional)
        with open("access_token.txt", "w") as token_file:
            token_file.write(session_data["access_token"])
        print("Access token saved to access_token.txt")
        
    except Exception as e:
        print("Error generating access token:", e)

if __name__ == "__main__":
    # Replace with your Zerodha API Key and API Secret
    api_key = "zy7p41049ggnphlu"
    api_secret = "70mrzeu71ce5ukknuzzwzzn8nmizoi93"
    generate_access_token(api_key, api_secret)
