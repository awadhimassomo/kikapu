from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class PhoneNumberOrEmailBackend(ModelBackend):
    """
    Authenticate using phone number or email.
    
    This allows users to log in with either their phone number or email address.
    Phone number is the primary identifier, but email is supported for backward compatibility.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Handle different phone number formats
            if username:
                # Try various phone number formats
                cleaned_phone = username.strip()
                # Remove leading zero if present
                if cleaned_phone.startswith('0'):
                    cleaned_phone_alt = cleaned_phone[1:]
                else:
                    cleaned_phone_alt = cleaned_phone
                
                # Create alternate formats with/without country code
                alt_formats = [
                    cleaned_phone,                  # As entered
                    '+255' + cleaned_phone_alt,     # With country code +255
                    '255' + cleaned_phone_alt,      # With country code 255
                    '0' + cleaned_phone_alt         # With leading zero
                ]
                
                # Try to find a user matching any phone format or the email
                user = User.objects.filter(
                    Q(phoneNumber__in=alt_formats) | Q(email=username)
                ).first()
            else:
                user = None
            
            if user and user.check_password(password):
                # Explicitly set the backend attribute on the user object
                user.backend = 'registration.auth_backends.PhoneNumberOrEmailBackend'
                return user
                
        except User.DoesNotExist:
            return None
        except Exception as e:
            # Log any unexpected errors
            print(f"Login error: {e}")
            return None
            
        return None
