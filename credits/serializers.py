from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from credits.models import NFCCard, CreditTransaction, CardApplication
from registration.models import CustomerProfile, DeliveryAgent, AgentRecommendation, CreditEvent, AdminUser

User = get_user_model()

class NFCCardSerializer(serializers.ModelSerializer):
    """Serializer for registering new NFC cards (pre-customer)"""
    
    class Meta:
        model = NFCCard
        fields = ['id', 'card_number', 'card_type', 'is_active', 'issued_at']
        read_only_fields = ['card_number', 'issued_at']

class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for registering new customers and linking them to a card"""
    name = serializers.CharField(write_only=True)
    phoneNumber = serializers.CharField(write_only=True)
    pin = serializers.CharField(write_only=True, min_length=4, max_length=4)
    card_type = serializers.ChoiceField(choices=[('PREPAID', 'Prepaid'), ('POSTPAID', 'Postpaid')], default='PREPAID')
    # Use is_active field instead of status which doesn't exist in the model
    linked_card = serializers.PrimaryKeyRelatedField(queryset=NFCCard.objects.filter(is_active=True, user__isnull=True))
    
    class Meta:
        model = CustomerProfile
        fields = ['id', 'name', 'phoneNumber', 'pin', 'card_type', 'linked_card']
    
    def validate_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("PIN must contain only digits")
        return value
    
    def create(self, validated_data):
        # Extract data for User model
        name_parts = validated_data.pop('name').split(' ', 1)
        firstName = name_parts[0]
        lastName = name_parts[1] if len(name_parts) > 1 else ''
        phoneNumber = validated_data.pop('phoneNumber')
        pin = validated_data.pop('pin')
        card_type = validated_data.pop('card_type')
        nfc_card = validated_data.pop('linked_card')
        
        # Create or get User
        user, created = User.objects.get_or_create(
            phoneNumber=phoneNumber,
            defaults={
                'username': phoneNumber,
                'firstName': firstName,
                'lastName': lastName,
                'user_type': 'CUSTOMER',
            }
        )
        
        if created:
            user.set_password(pin)  # Use PIN as initial password
            user.save()
        
        # Create or update CustomerProfile
        customer_profile, created = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                'card_type': card_type,
                'joined_date': nfc_card.issued_at,
            }
        )
        
        # Set PIN for NFC card
        customer_profile.set_pin(pin)
        
        # Link card to customer
        nfc_card.user = user
        nfc_card.card_type = card_type
        nfc_card.is_active = True
        nfc_card.save()
        
        return customer_profile

class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for handling payment transactions"""
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    agent = serializers.PrimaryKeyRelatedField(queryset=DeliveryAgent.objects.all(), required=False)
    transaction_type = serializers.ChoiceField(choices=[
        ('PURCHASE', 'Purchase'),
        ('TOPUP', 'Top-up'),
        ('REPAYMENT', 'Repayment'),
        ('FEE', 'Fee'),
    ])
    status = serializers.ChoiceField(choices=[
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled')
    ], default='PENDING')
    pin = serializers.CharField(write_only=True, required=True, min_length=4, max_length=4)
    nfc_uid = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = CreditTransaction
        fields = ['id', 'customer', 'agent', 'amount', 'transaction_type', 'status', 'timestamp', 'pin', 'nfc_uid']
        read_only_fields = ['timestamp']
        extra_kwargs = {
            'amount': {'required': True},
        }
    
    def validate(self, attrs):
        # Validate PIN
        pin = attrs.pop('pin')
        nfc_uid = attrs.pop('nfc_uid')
        customer = attrs.get('customer')
        
        try:
            # Verify the NFC card exists and belongs to the customer
            card = NFCCard.objects.get(uid=nfc_uid)
            if card.user != customer:
                raise serializers.ValidationError({"nfc_uid": "Card does not belong to this customer"})
            
            # Verify card is active
            if not card.is_active:
                raise serializers.ValidationError({"nfc_uid": "Card is not active"})
            
            # Verify PIN
            customer_profile = CustomerProfile.objects.get(user=customer)
            pin_valid, message = customer_profile.verify_pin(pin)
            if not pin_valid:
                raise serializers.ValidationError({"pin": message})
            
            # For purchase transactions, verify sufficient funds
            if attrs.get('transaction_type') == 'PURCHASE':
                if card.card_type == 'PREPAID' and card.balance < attrs.get('amount'):
                    raise serializers.ValidationError({"amount": "Insufficient funds"})
                elif card.card_type == 'POSTPAID' and card.get_available_credit() < attrs.get('amount'):
                    raise serializers.ValidationError({"amount": "Insufficient credit"})
            
            # Add card to validated data for processing in create/update
            attrs['card'] = card
            
        except NFCCard.DoesNotExist:
            raise serializers.ValidationError({"nfc_uid": "Invalid NFC card"})
        except CustomerProfile.DoesNotExist:
            raise serializers.ValidationError({"customer": "Customer profile not found"})
        
        return attrs
    
    def create(self, validated_data):
        card = validated_data.pop('card')
        customer = validated_data.get('customer')
        amount = validated_data.get('amount')
        transaction_type = validated_data.get('transaction_type')
        
        # Process the transaction based on type
        if transaction_type == 'PURCHASE':
            # Deduct amount from balance
            if card.card_type == 'PREPAID':
                card.balance -= amount
            else:  # POSTPAID
                card.balance -= amount  # Will become negative for postpaid
            
            # Update customer total_spent
            try:
                profile = CustomerProfile.objects.get(user=customer)
                profile.total_spent += amount
                profile.save(update_fields=['total_spent'])
                
                # Add credit score points (5 points per 10,000 TZS spent)
                points = min(20, int(amount / 10000) * 5)
                if points > 0:
                    profile.update_credit_score(points, 'PURCHASE')
            except CustomerProfile.DoesNotExist:
                pass
            
        elif transaction_type == 'TOPUP':
            # Add amount to balance
            card.balance += amount
            
        elif transaction_type == 'REPAYMENT':
            # Add amount to balance for postpaid cards
            if card.card_type == 'POSTPAID':
                card.balance += amount
                
                # Add credit score points for on-time payment
                try:
                    profile = CustomerProfile.objects.get(user=customer)
                    profile.update_credit_score(10, 'REPAYMENT')
                except CustomerProfile.DoesNotExist:
                    pass
        
        # Update card last_used_at and save
        from django.utils import timezone
        card.last_used_at = timezone.now()
        card.save()
        
        # Create transaction record
        transaction = CreditTransaction.objects.create(**validated_data)
        
        return transaction

class PostpaidApplicationSerializer(serializers.ModelSerializer):
    """Serializer for customers applying for Postpaid upgrade"""
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    agent_recommendation = serializers.BooleanField(default=False, required=False)
    reason = serializers.CharField(required=True, write_only=True)
    
    class Meta:
        model = CardApplication
        fields = ['id', 'customer', 'status', 'agent_recommendation', 'notes', 'application_date', 'reason']
        read_only_fields = ['application_date', 'status', 'notes']
    
    def validate(self, attrs):
        customer = attrs.get('customer')
        
        try:
            # Check if customer is eligible for postpaid
            profile = CustomerProfile.objects.get(user=customer)
            is_eligible, message = profile.is_eligible_for_postpaid()
            
            if not is_eligible:
                raise serializers.ValidationError({"customer": message})
            
            # Check if customer already has a postpaid card
            if profile.card_type == 'POSTPAID':
                raise serializers.ValidationError({"customer": "Already has a Postpaid card"})
                
            # Check if there's a pending application
            if profile.postpaid_status == 'PENDING':
                raise serializers.ValidationError({"customer": "Already has a pending Postpaid application"})
                
            # Add profile to validated data for processing in create
            attrs['profile'] = profile
            
        except CustomerProfile.DoesNotExist:
            raise serializers.ValidationError({"customer": "Customer profile not found"})
        
        return attrs
    
    def create(self, validated_data):
        profile = validated_data.pop('profile')
        reason = validated_data.pop('reason')
        
        # Update profile status to pending
        profile.postpaid_status = 'PENDING'
        profile.save(update_fields=['postpaid_status'])
        
        # Create application with reason in notes
        validated_data['notes'] = reason
        application = CardApplication.objects.create(**validated_data)
        
        return application

class CreditEventSerializer(serializers.ModelSerializer):
    """Serializer for tracking credit score changes"""
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    
    class Meta:
        model = CreditEvent
        fields = ['id', 'customer', 'event_type', 'points_change', 'timestamp', 'notes']
        read_only_fields = ['timestamp']

class AgentRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for agents recommending customers for Postpaid"""
    agent_id = serializers.PrimaryKeyRelatedField(source='agent', queryset=DeliveryAgent.objects.all())
    customer_id = serializers.PrimaryKeyRelatedField(source='customer', queryset=User.objects.all())
    
    class Meta:
        model = AgentRecommendation
        fields = ['id', 'agent_id', 'customer_id', 'status', 'recommendation_date', 'notes']
        read_only_fields = ['status', 'recommendation_date']
    
    def validate(self, attrs):
        agent = attrs.get('agent')
        customer = attrs.get('customer')
        
        # Check if agent is active
        if not agent.is_active:
            raise serializers.ValidationError({"agent_id": "Agent is not active"})
        
        # Check if customer exists and has a profile
        try:
            profile = CustomerProfile.objects.get(user=customer)
        except CustomerProfile.DoesNotExist:
            raise serializers.ValidationError({"customer_id": "Customer profile not found"})
        
        # Check if recommendation already exists
        if AgentRecommendation.objects.filter(agent=agent, customer=customer, status='PENDING').exists():
            raise serializers.ValidationError({"customer_id": "Recommendation already exists for this customer"})
        
        return attrs
    
    def create(self, validated_data):
        recommendation = AgentRecommendation.objects.create(**validated_data)
        
        # Update agent total recommendations
        agent = validated_data.get('agent')
        agent.total_recommendations += 1
        agent.save(update_fields=['total_recommendations'])
        
        return recommendation

class NFCCardRegistrationSerializer(serializers.Serializer):
    """Serializer for agent registering new blank NFC cards (with auto-generated KP Number)"""
    uid = serializers.CharField(max_length=32)
    registered_by = serializers.CharField(max_length=20, required=False)
    kpNumber = serializers.CharField(max_length=20, required=False)  # Optional field from mobile app in camelCase
    kp_number = serializers.CharField(max_length=20, required=False)  # Optional field from mobile app in snake_case
    overwrite = serializers.BooleanField(default=False)  # Option to overwrite existing card with same UID
    
    def validate_uid(self, value):
        # Check if UID already exists (only raise error if overwrite=False)
        if NFCCard.objects.filter(uid=value).exists() and not self.initial_data.get('overwrite', False):
            raise serializers.ValidationError("This card UID already exists in the system. Use overwrite=true to replace it.")
        return value
    
    def create(self, validated_data):
        uid = validated_data.get('uid')
        registered_by = validated_data.get('registered_by')
        overwrite = validated_data.get('overwrite', False)
        
        # Handle both kpNumber and kp_number field naming conventions
        card_number = validated_data.get('kpNumber') or validated_data.get('kp_number')
        
        # Check if a card with this UID already exists and overwrite is True
        if overwrite:
            try:
                existing_card = NFCCard.objects.get(uid=uid)
                # Log the card details before overwriting
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Overwriting existing card with UID {uid}. Old details: {existing_card.card_number}, status: {existing_card.status}")
                
                # Update the existing card instead of creating a new one
                existing_card.registered_by = registered_by
                if card_number:  # Only update card_number if a new one is provided
                    existing_card.card_number = card_number
                existing_card.status = 'unassigned'  # Reset status
                existing_card.user = None  # Remove any user association
                existing_card.balance = 0  # Reset balance
                existing_card.save()
                return existing_card
            except NFCCard.DoesNotExist:
                # Card doesn't exist despite the overwrite flag, just continue to create a new one
                pass
        
        # Create new card with status "unassigned"
        card = NFCCard.objects.create(
            uid=uid,
            registered_by=registered_by,
            card_number=card_number,  # Use the provided card number if available
            status='unassigned'  # Explicit status setting
        )
        
        return card


class CustomerAssignmentSerializer(serializers.Serializer):
    """Serializer for registering a customer and assigning (but not activating) a card"""
    card_id = serializers.CharField(max_length=32, required=False)
    card_uid = serializers.CharField(max_length=32, required=False)
    name = serializers.CharField(required=False)
    phoneNumber = serializers.CharField(required=False)  # Make this optional
    phone_number = serializers.CharField(required=False)  # Add the frontend name
    customer_firstname = serializers.CharField(required=False)  # Support frontend naming
    customer_lastname = serializers.CharField(required=False)  # Support frontend naming
    customer_id = serializers.IntegerField(required=False)  # Support frontend sending customer ID
    initial_balance = serializers.FloatField(required=False)  # Support initial balance
    pin = serializers.CharField(min_length=4, max_length=4)
    card_type = serializers.ChoiceField(choices=[('PREPAID', 'Prepaid'), ('POSTPAID', 'Postpaid')], default='PREPAID')
    
    def validate(self, data):
        """Validate that either card_id or card_uid is provided and the card is available"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Check for phone number in either field
        if not data.get('phoneNumber') and not data.get('phone_number'):
            raise serializers.ValidationError("A phone number is required")
            
        # If we have phone_number but not phoneNumber, copy it
        if data.get('phone_number') and not data.get('phoneNumber'):
            data['phoneNumber'] = data.get('phone_number')
            logger.warning(f"Using phone_number as phoneNumber: {data.get('phone_number')}")
            
        # Handle frontend customer name fields
        if data.get('customer_firstname') and data.get('customer_lastname'):
            data['name'] = f"{data.get('customer_firstname')} {data.get('customer_lastname')}"
            logger.warning(f"Using customer_firstname and customer_lastname to set name: {data['name']}")
            
        # Log initial balance if provided
        if data.get('initial_balance'):
            logger.warning(f"Initial balance provided: {data.get('initial_balance')}")
            
        # If customer_id is provided, we can use it instead of phone number lookup
        if data.get('customer_id'):
            logger.warning(f"Customer ID provided: {data.get('customer_id')}")
            try:
                from registration.models import User
                user = User.objects.get(id=data.get('customer_id'), user_type='CUSTOMER')
                logger.warning(f"Found user by ID: {user.firstName} {user.lastName}, phone: {user.phoneNumber}")
                # If we don't have a phone number yet, use the one from the found user
                if not data.get('phoneNumber'):
                    data['phoneNumber'] = user.phoneNumber
                    logger.warning(f"Using phone number from found user: {data['phoneNumber']}")
            except User.DoesNotExist:
                logger.warning(f"No user found with ID: {data.get('customer_id')}")
                # We'll continue with phone number lookup if available
        
        # Check if we have either card_id or card_uid
        if not data.get('card_id') and not data.get('card_uid'):
            raise serializers.ValidationError("Either card_id or card_uid must be provided")
        
        # If we have card_id, use it to look up the card
        if data.get('card_id'):
            try:
                card = NFCCard.objects.get(card_number=data.get('card_id'))
                logger.warning(f"Found card by card_id: {card.card_number} with UID: {card.uid}")
                data['card_uid'] = card.uid
            except NFCCard.DoesNotExist:
                raise serializers.ValidationError(f"Card with ID {data.get('card_id')} does not exist")
        
        # Now validate the card_uid (which we either received directly or looked up)
        try:
            card = NFCCard.objects.get(uid=data.get('card_uid'))
            if card.status != 'unassigned':
                raise serializers.ValidationError(f"Card is already {card.get_status_display()} and cannot be assigned.")
        except NFCCard.DoesNotExist:
            raise serializers.ValidationError("Card with this UID does not exist.")
        
        # If phone number is provided, try to look up the user
        if data.get('phoneNumber'):
            from registration.models import User
            try:
                user = User.objects.get(phoneNumber=data.get('phoneNumber'), user_type='CUSTOMER')
                logger.warning(f"Found existing user: {user.firstName} {user.lastName}")
                if not data.get('name'):
                    data['name'] = f"{user.firstName} {user.lastName}".strip()
                    logger.warning(f"Using existing user name: {data['name']}")
            except User.DoesNotExist:
                # We don't create new customers through this API
                logger.warning(f"No existing user found with phone: {data.get('phoneNumber')}")
                raise serializers.ValidationError(f"Customer with phone number {data.get('phoneNumber')} does not exist")
        
        # PIN validation
        if data.get('pin') and not data.get('pin').isdigit():
            raise serializers.ValidationError("PIN must contain only digits")
            
        return data
    
    def create(self, validated_data):
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract data
        card_uid = validated_data.get('card_uid')
        phoneNumber = validated_data.get('phoneNumber')
        pin = validated_data.get('pin')
        card_type = validated_data.get('card_type')
        
        # Get the existing user (validation already ensures the user exists)
        from registration.models import User
        user = User.objects.get(phoneNumber=phoneNumber, user_type='CUSTOMER')
        logger.warning(f"Using existing user for card assignment: {user.firstName} {user.lastName}")
        
        # Get the card by UID
        card = NFCCard.objects.get(uid=card_uid)
        
        # Assign the card to the user
        card.user = user
        card.status = 'assigned'  # Update status to assigned (not activated yet)
        card.save()
        
        # Create customer profile if it doesn't exist
        from registration.models import CustomerProfile
        profile, created = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                'card_type': card_type,
                'loyalty_points': 0,
                'joined_date': timezone.now()
            }
        )
        
        if created:
            logger.warning(f"Created new customer profile with card type: {card_type}")
        else:
            logger.warning(f"Using existing customer profile")
            # Update the card type if needed
            if profile.card_type != card_type:
                profile.card_type = card_type
                profile.save()
                logger.warning(f"Updated card type to: {card_type}")
        
        # Handle initial balance if provided
        initial_balance = validated_data.get('initial_balance')
        if initial_balance and initial_balance > 0:
            try:
                # Update the balance field directly in the CustomerProfile
                profile.balance = initial_balance
                profile.save()
                logger.warning(f"Updated customer balance to: {initial_balance} for user {user.phoneNumber}")
            except Exception as e:
                logger.warning(f"Error updating customer balance: {e}")
        
        return {
            'user': user,
            'card': card,
            'profile': profile
        }

class CardActivationSerializer(serializers.Serializer):
    """Serializer for activating an assigned card via physical NFC tap"""
    card_uid = serializers.CharField(max_length=32)
    
    def validate_card_uid(self, value):
        try:
            card = NFCCard.objects.get(uid=value)
            if card.status != 'assigned':
                raise serializers.ValidationError(f"Card with status '{card.get_status_display()}' cannot be activated. Only assigned cards can be activated.")
            if card.user is None:
                raise serializers.ValidationError("Card must be assigned to a customer before activation.")
        except NFCCard.DoesNotExist:
            raise serializers.ValidationError("Card with this UID does not exist.")
        return value
    
    def create(self, validated_data):
        card_uid = validated_data.get('card_uid')
        card = NFCCard.objects.get(uid=card_uid)
        
        # Activate the card
        success, message = card.activate()
        if not success:
            raise serializers.ValidationError(message)
        
        return card