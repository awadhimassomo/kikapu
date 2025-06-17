from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, BusinessProfile, CustomerProfile, LoyaltyCard, CardTransaction
import datetime

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    firstName = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    lastName = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phoneNumber = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ('phoneNumber', 'email', 'firstName', 'lastName', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['phoneNumber'].widget.attrs['placeholder'] = '+255 XXX XXX XXX'
        self.fields['phoneNumber'].help_text = 'This will be your primary identifier for login'
        
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        phoneNumber = cleaned_data.get('phoneNumber')
        
        if not phoneNumber:
            self.add_error('phoneNumber', 'Phone number is required')
        else:
            # Explicitly set the username to be the same as phoneNumber
            # This is needed to avoid unique constraint issues
            cleaned_data['username'] = phoneNumber
            
        return cleaned_data
        
    def save(self, commit=True):
        user = super().save(commit=False)
        # Ensure username is set to phoneNumber
        user.username = self.cleaned_data.get('phoneNumber')
        
        if commit:
            user.save()
        
        return user

class CustomerRegistrationForm(UserRegistrationForm):
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    
    class Meta(UserRegistrationForm.Meta):
        fields = UserRegistrationForm.Meta.fields + ('address', 'date_of_birth')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add placeholders for better UX
        self.fields['phoneNumber'].widget.attrs['placeholder'] = '+255 XXX XXX XXX'
        self.fields['email'].widget.attrs['placeholder'] = 'Email (Optional)'
        self.fields['firstName'].widget.attrs['placeholder'] = 'First Name'
        self.fields['lastName'].widget.attrs['placeholder'] = 'Last Name'
        self.fields['address'].widget.attrs['placeholder'] = 'Your delivery address (Optional)'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'CUSTOMER'
        
        if commit:
            user.save()
            try:
                # If profile already exists, update it
                customer_profile = CustomerProfile.objects.get(user=user)
                customer_profile.address = self.cleaned_data.get('address', '')
                customer_profile.date_of_birth = self.cleaned_data.get('date_of_birth')
                customer_profile.save()
            except CustomerProfile.DoesNotExist:
                # Create new profile
                CustomerProfile.objects.create(
                    user=user,
                    address=self.cleaned_data.get('address', ''),
                    date_of_birth=self.cleaned_data.get('date_of_birth')
                )
                
        return user

class BusinessRegistrationForm(UserRegistrationForm):
    BUSINESS_TYPE_CHOICES = [
        ('farmer', 'Farmer / Producer'),
        ('processor', 'Food Processor'),
        ('wholesaler', 'Wholesaler'),
        ('retailer', 'Retailer / Shop'),
    ]
    
    # Make email optional for business registration
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    existing_account = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    existing_phone = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    business_type = forms.ChoiceField(required=True, choices=BUSINESS_TYPE_CHOICES, widget=forms.HiddenInput())
    business_name = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    business_address = forms.CharField(required=True, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    business_description = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    registration_number = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    business_phone = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    business_email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    business_hours = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Mon-Fri: 9AM-5PM, Sat: 10AM-3PM'}))
    business_logo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
    
    class Meta(UserRegistrationForm.Meta):
        fields = UserRegistrationForm.Meta.fields + ('business_type', 'business_name', 'business_address', 'business_description', 
                                                   'registration_number', 'business_phone', 'business_email', 
                                                   'business_hours', 'business_logo', 'existing_account', 'existing_phone')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False  # Make email optional
        self.fields['phoneNumber'].help_text = "Used for account login and verification"
        
    def clean(self):
        cleaned_data = super().clean()
        existing_account = cleaned_data.get('existing_account')
        existing_phone = cleaned_data.get('existing_phone')
        phoneNumber = cleaned_data.get('phoneNumber')
        email = cleaned_data.get('email')
        
        # If using existing account, the phone must be provided
        if existing_account and not existing_phone:
            self.add_error('existing_phone', 'Please provide the phone number of your existing account')
        
        # Require either email or phone for new accounts
        if not existing_account and not email and not phoneNumber:
            self.add_error('phoneNumber', 'Either a phone number or email is required')
        
        return cleaned_data
    
    def save(self, commit=True):
        existing_account = self.cleaned_data.get('existing_account')
        existing_phone = self.cleaned_data.get('existing_phone')
        
        if existing_account and existing_phone:
            # Try to find existing user by phone number
            try:
                existing_user = User.objects.get(phoneNumber=existing_phone)
                user = existing_user
                # No need to save the user as it already exists
                commit_user = False
            except User.DoesNotExist:
                self.add_error('existing_phone', 'No account with this phone number was found')
                return None
        else:
            # Create new user account
            user = super().save(commit=False)
            commit_user = True
        
        # Set or update user_type to include BUSINESS
        if user.user_type != 'BUSINESS':
            if user.user_type == 'ADMIN':
                # Keep admin privileges
                pass
            else:
                # Set to business or maintain customer+business status
                user.user_type = 'BUSINESS'
        
        if commit:
            if commit_user:
                user.save()
            
            # Check if business profile already exists for this user
            try:
                business_profile = BusinessProfile.objects.get(user=user)
                # Update existing business profile
                business_profile.business_name = self.cleaned_data.get('business_name')
                business_profile.business_address = self.cleaned_data.get('business_address')
                business_profile.business_description = self.cleaned_data.get('business_description', '')
                business_profile.registration_number = self.cleaned_data.get('registration_number', '')
                business_profile.business_phone = self.cleaned_data.get('business_phone', '')
                business_profile.business_email = self.cleaned_data.get('business_email', '')
                business_profile.business_hours = self.cleaned_data.get('business_hours', '')
                business_profile.business_type = self.cleaned_data.get('business_type', 'retailer')
                
                if self.cleaned_data.get('business_logo'):
                    business_profile.business_logo = self.cleaned_data.get('business_logo')
                
                business_profile.save()
            except BusinessProfile.DoesNotExist:
                # Create new business profile
                business_profile = BusinessProfile.objects.create(
                    user=user,
                    business_name=self.cleaned_data.get('business_name'),
                    business_address=self.cleaned_data.get('business_address'),
                    business_description=self.cleaned_data.get('business_description', ''),
                    registration_number=self.cleaned_data.get('registration_number', ''),
                    business_phone=self.cleaned_data.get('business_phone', ''),
                    business_email=self.cleaned_data.get('business_email', ''),
                    business_hours=self.cleaned_data.get('business_hours', ''),
                    business_type=self.cleaned_data.get('business_type', 'retailer'),
                    business_logo=self.cleaned_data.get('business_logo', None)
                )
        return user

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': '712345678'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Password'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Phone Number'
        
    def clean_username(self):
        """Format the phone number to ensure it works with our authentication"""
        phone = self.cleaned_data.get('username')
        
        # Remove any non-digit characters the user might have entered
        phone = ''.join(filter(str.isdigit, phone))
        
        # Handle cases where user might still enter the country code or leading zero
        if phone.startswith('255'):
            phone = phone[3:]
        elif phone.startswith('0'):
            phone = phone[1:]
            
        # The system expects numbers in the format 0XXXXXXXXX
        # So we add the leading zero back
        phone = '0' + phone
            
        return phone

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('firstName', 'lastName', 'phoneNumber', 'profile_image')
        widgets = {
            'firstName': forms.TextInput(attrs={'class': 'form-control'}),
            'lastName': forms.TextInput(attrs={'class': 'form-control'}),
            'phoneNumber': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
        }

class CustomerProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ('address', 'date_of_birth')
        widgets = {
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

class BusinessProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = ('business_name', 'business_address', 'business_description', 
                 'registration_number', 'business_logo', 'business_phone', 
                 'business_email', 'business_hours')
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'business_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'business_logo': forms.FileInput(attrs={'class': 'form-control'}),
            'business_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'business_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'business_hours': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Mon-Fri: 9AM-5PM, Sat: 10AM-3PM'}),
        }

class LoyaltyCardForm(forms.ModelForm):
    """Form for creating and updating loyalty cards"""
    # Calculate default expiry date (2 years from now)
    default_expiry = datetime.date.today() + datetime.timedelta(days=730)
    
    expiry_date = forms.DateField(
        initial=default_expiry,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    nfc_tag_id = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Scan NFC tag or enter ID manually'})
    )
    
    card_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter card number'})
    )
    
    class Meta:
        model = LoyaltyCard
        fields = ('card_number', 'nfc_tag_id', 'expiry_date', 'tier', 'status')
        widgets = {
            'tier': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        # Check if card number already exists
        if LoyaltyCard.objects.filter(card_number=card_number).exists():
            # If this is an update (instance exists) and we're checking the same card, it's ok
            if self.instance and self.instance.card_number == card_number:
                return card_number
            raise forms.ValidationError("This card number is already in use.")
        return card_number
    
    def clean_nfc_tag_id(self):
        nfc_tag_id = self.cleaned_data.get('nfc_tag_id')
        # Check if NFC tag ID already exists
        if LoyaltyCard.objects.filter(nfc_tag_id=nfc_tag_id).exists():
            # If this is an update (instance exists) and we're checking the same tag, it's ok
            if self.instance and self.instance.nfc_tag_id == nfc_tag_id:
                return nfc_tag_id
            raise forms.ValidationError("This NFC tag is already registered to another card.")
        return nfc_tag_id


class CardTransactionForm(forms.ModelForm):
    """Form for recording loyalty card transactions"""
    class Meta:
        model = CardTransaction
        fields = ('points', 'transaction_type', 'description', 'location')
        widgets = {
            'points': forms.NumberInput(attrs={'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transaction description'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transaction location (optional)'}),
        }


class NFCTagReadForm(forms.Form):
    """Form for reading NFC tags from mobile app"""
    nfc_tag_id = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Scan NFC tag'}),
        required=True
    )
    
    device_id = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=True
    )


class CustomerMobileRegistrationForm(forms.ModelForm):
    """Form for registering customers via mobile app"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
        required=True
    )
    
    firstName = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
        required=True
    )
    
    lastName = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        required=True
    )
    
    phoneNumber = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
        required=True
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        required=True
    )
    
    nfc_tag_id = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NFC tag ID'}),
        required=True
    )
    
    class Meta:
        model = User
        fields = ('email', 'firstName', 'lastName', 'phoneNumber')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email
    
    def clean_nfc_tag_id(self):
        nfc_tag_id = self.cleaned_data.get('nfc_tag_id')
        if LoyaltyCard.objects.filter(nfc_tag_id=nfc_tag_id).exists():
            raise forms.ValidationError("This NFC tag is already registered.")
        return nfc_tag_id
