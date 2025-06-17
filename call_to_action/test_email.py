"""
Test email functionality for the call_to_action app.
Run with: python call_to_action/test_email.py
"""
import os
import sys
import django

# Get the directory containing the manage.py file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the project root to the Python path
sys.path.insert(0, project_root)

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kikapu.settings')

# Initialize Django
django.setup()

# Now we can import Django models and other modules
from call_to_action.email_utils import send_auto_reply_email

# Test data
test_data = {
    'name': 'Test User',
    'email': 'test@example.com',
    'form_type': 'Test Form',
    'message': 'This is a test email.'
}

if __name__ == "__main__":
    try:
        # Send test email
        send_auto_reply_email('athimassomo@gmail.com', test_data)
        print("✅ Test email sent successfully!")
        print("   Please check your inbox and spam folder.")
        print("   Also check the admin email (athimassomo@gmail.com) for the notification.")
    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        print("   Make sure your .env file is properly configured with email credentials.")
        print(f"   Current working directory: {os.getcwd()}")
        print(f"   Python path: {sys.path}")
