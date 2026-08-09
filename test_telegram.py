"""
TEST TELEGRAM BOT CONNECTION
"""

import requests
import json

# Your bot token
BOT_TOKEN = "6667612277:AAFcTaNO4sjp_1LSgcUMy4UncCS9oMNOncU"
YOUR_CHAT_ID = "1821633392"  # Your chat ID from earlier

def test_telegram():
    print("🔍 Testing Telegram Bot Connection...")
    print("="*50)
    
    # Test 1: Check if bot token is valid
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('ok'):
            print(f"✅ Bot token is valid!")
            print(f"   Bot name: {data['result']['first_name']}")
            print(f"   Bot username: @{data['result']['username']}")
        else:
            print(f"❌ Bot token is invalid: {data}")
            return
    except Exception as e:
        print(f"❌ Error checking bot: {e}")
        return
    
    # Test 2: Send a test message
    print("\n📤 Sending test message...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': YOUR_CHAT_ID,
        'text': """
🚀 <b>TEST MESSAGE</b>

This is a test message from your Arbitrage Bot!

If you receive this, your bot is working correctly.

✅ Bot is connected and ready!
🕐 Time: Now
        """,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=data)
        result = response.json()
        if result.get('ok'):
            print(f"✅ Test message sent successfully!")
            print(f"   Check your Telegram now!")
        else:
            print(f"❌ Failed to send message: {result}")
            print(f"   Error: {result.get('description', 'Unknown error')}")
            
            # Check if chat_id is wrong
            if 'chat not found' in str(result):
                print("\n⚠️ Chat ID issue detected!")
                print("   Make sure your Chat ID is correct.")
                print("   To get your Chat ID:")
                print("   1. Search @userinfobot on Telegram")
                print("   2. Send /start")
                print("   3. Copy the ID")
    except Exception as e:
        print(f"❌ Error sending message: {e}")
    
    print("\n" + "="*50)
    print("💡 If you received the test message, the bot is working!")
    print("   You should now receive arbitrage alerts.")

if __name__ == "__main__":
    test_telegram()
