from rest_framework import serializers
from .models import MarketPriceResearch, Market, Source, Commodity, UnsyncedData, SyncLog

class MarketPriceResearchSerializer(serializers.ModelSerializer):
    """Serializer for market price research data submitted by agents"""
    class Meta:
        model = MarketPriceResearch
        fields = '__all__'
        read_only_fields = ['agent', 'date_collected']
        
    def to_representation(self, instance):
        # Get the default representation
        representation = super().to_representation(instance)
        
        # If source is available, include source information
        if instance.source:
            representation['source_name'] = instance.source.name
            representation['source_type'] = instance.source.source_type
            
        return representation
        
class MarketSerializer(serializers.ModelSerializer):
    """Serializer for market information"""
    has_source = serializers.SerializerMethodField()
    
    class Meta:
        model = Market
        fields = ['id', 'name', 'location', 'region', 'latitude', 'longitude', 'is_active', 'has_source']
    
    def get_has_source(self, obj):
        return hasattr(obj, 'source_link') and obj.source_link is not None

class SourceSerializer(serializers.ModelSerializer):
    """Serializer for source information"""
    linked_market = MarketSerializer(source='market', read_only=True)
    linked_market_id = serializers.PrimaryKeyRelatedField(
        queryset=Market.objects.all(),
        source='market',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Source
        fields = ['id', 'name', 'source_type', 'location', 'region', 'latitude', 'longitude', 
                'is_active', 'transportation_cost', 'created_at', 'updated_at',
                'linked_market', 'linked_market_id']

class CommoditySerializer(serializers.ModelSerializer):
    """Serializer for commodity information"""
    class Meta:
        model = Commodity
        fields = ['id', 'name', 'category', 'default_unit', 'description']

# Sync serializers
class SyncDataItemSerializer(serializers.Serializer):
    """Serializer for individual data items in a sync request"""
    data_type = serializers.ChoiceField(choices=UnsyncedData.DATA_TYPE_CHOICES)
    payload = serializers.JSONField()
    sync_id = serializers.UUIDField()

class SyncRequestSerializer(serializers.Serializer):
    """Serializer for batch sync requests"""
    device_id = serializers.CharField(max_length=255)
    data = SyncDataItemSerializer(many=True)

class SyncErrorSerializer(serializers.Serializer):
    """Serializer for sync errors"""
    sync_id = serializers.UUIDField()
    error = serializers.CharField()

class SyncResponseSerializer(serializers.Serializer):
    """Serializer for responses to sync requests"""
    status = serializers.CharField()
    message = serializers.CharField()
    failed_sync_ids = SyncErrorSerializer(many=True, required=False)

class ConflictResolutionSerializer(serializers.Serializer):
    """Serializer for conflict resolution requests"""
    sync_id = serializers.UUIDField()
    resolution = serializers.DictField(
        child=serializers.DictField(
            child=serializers.Field()
        )
    )
    
    def validate_resolution(self, value):
        if 'action' not in value:
            raise serializers.ValidationError("Resolution must contain an 'action' field.")
        if value['action'] not in ['overwrite', 'discard', 'merge']:
            raise serializers.ValidationError("Action must be one of 'overwrite', 'discard', or 'merge'.")
        if value['action'] in ['overwrite', 'merge'] and 'payload' not in value:
            raise serializers.ValidationError("For 'overwrite' or 'merge' actions, a 'payload' field is required.")
        
        return value

class UnsyncedDataSerializer(serializers.ModelSerializer):
    """Serializer for unsynced data records"""
    class Meta:
        model = UnsyncedData
        fields = '__all__'

class SyncLogSerializer(serializers.ModelSerializer):
    """Serializer for sync logs"""
    class Meta:
        model = SyncLog
        fields = '__all__'