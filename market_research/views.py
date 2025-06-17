from rest_framework import viewsets, status, permissions, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from django.utils import timezone
from django.shortcuts import render
from django.db.models import Avg, Max, Min, Count, Q
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from datetime import timedelta
import requests
import json
import math
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import MarketPriceResearch, Market, Source, Commodity
from .serializers import (MarketPriceResearchSerializer, MarketSerializer, 
                        SourceSerializer, CommoditySerializer)
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages

class SourceViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint to view available sources (markets, processors, etc.)"""
    queryset = Source.objects.filter(is_active=True)
    serializer_class = SourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get a list of all active sources",
        responses={200: SourceSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        # Support filtering by source_type
        source_type = request.query_params.get('source_type', None)
        if source_type:
            self.queryset = self.queryset.filter(source_type=source_type)
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Get details for a specific source",
        responses={200: SourceSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class MarketViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint to view available markets"""
    queryset = Market.objects.filter(is_active=True)
    serializer_class = MarketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get a list of all active markets",
        responses={200: MarketSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Get details for a specific market",
        responses={200: MarketSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

class CommodityViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint to view available commodities"""
    queryset = Commodity.objects.all().order_by('name')
    serializer_class = CommoditySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get a list of all commodities",
        responses={200: CommoditySerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Get details for a specific commodity",
        responses={200: CommoditySerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class SourceCreateAPIView(generics.CreateAPIView):
    """API endpoint to register a new source (market, processor, etc.)"""
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # Add explicit tags for Swagger grouping
    swagger_tags = ['Sources']
    
    @swagger_auto_schema(
        operation_description="Register a new source (market, processor, kiosk, etc.)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['name', 'source_type', 'region', 'location'],
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the source"),
                'source_type': openapi.Schema(type=openapi.TYPE_STRING, description="Type of source (market, processor, kiosk, etc.)", 
                                            enum=[choice[0] for choice in Source.SOURCE_TYPE_CHOICES]),
                'location': openapi.Schema(type=openapi.TYPE_STRING, description="Location address or description"),
                'region': openapi.Schema(type=openapi.TYPE_STRING, description="Region where the source is located"),
                'latitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="GPS latitude of the source"),
                'longitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="GPS longitude of the source"),
                'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Whether the source is active", default=True),
                'transportation_cost': openapi.Schema(type=openapi.TYPE_NUMBER, description="Cost to transport goods to/from this source"),
                'market': openapi.Schema(type=openapi.TYPE_INTEGER, description="Optional: ID of a market to link to this source"),
            }
        ),
        responses={
            201: SourceSerializer(),
            400: "Bad Request - Invalid data",
            401: "Unauthorized - Authentication required"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MarketCreateAPIView(generics.CreateAPIView):
    """API endpoint to register a new market"""
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # Add explicit tags for Swagger grouping
    swagger_tags = ['Markets']
    
    @swagger_auto_schema(
        operation_description="Register a new market",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['name', 'region', 'location'],
            properties={
                'name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the market"),
                'location': openapi.Schema(type=openapi.TYPE_STRING, description="Location address or description"),
                'region': openapi.Schema(type=openapi.TYPE_STRING, description="Region where the market is located"),
                'latitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="GPS latitude of the market"),
                'longitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="GPS longitude of the market"),
                'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Whether the market is active", default=True),
            }
        ),
        responses={
            201: MarketSerializer(),
            400: "Bad Request - Invalid data",
            401: "Unauthorized - Authentication required"
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
        
    def perform_create(self, serializer):
        # Create the market
        market = serializer.save()
        
        # Optionally create a corresponding Source entry linked to this market
        if self.request.data.get('create_source', True):
            Source.objects.create(
                name=market.name,
                source_type='market',
                location=market.location,
                region=market.region,
                latitude=market.latitude,
                longitude=market.longitude,
                is_active=market.is_active,
                market=market
            )

@swagger_auto_schema(
    method='post',
    operation_description="Mobile app endpoint for submitting market price research data. All fields from the mobile form are supported.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['source_type', 'source_name', 'product_name', 'price', 'unit'],
        properties={
            'source_type': openapi.Schema(type=openapi.TYPE_STRING, description="Type of source (market, processor, kiosk, etc.)", enum=[choice[0] for choice in MarketPriceResearch.SOURCE_TYPE_CHOICES]),
            'source_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the market/store/source"),
            'product_name': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the product"),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER, description="Price observed"),
            'quantity': openapi.Schema(type=openapi.TYPE_NUMBER, description="Quantity (defaults to 1 if not provided)", default=1),
            'unit': openapi.Schema(type=openapi.TYPE_STRING, description="Unit of measurement", enum=[choice[0] for choice in MarketPriceResearch.UNIT_CHOICES]),
            'region': openapi.Schema(type=openapi.TYPE_STRING, description="Region in Tanzania"),
            'country': openapi.Schema(type=openapi.TYPE_STRING, description="Country (defaults to Tanzania)", default="Tanzania"),
            'latitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="GPS latitude"),
            'longitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="GPS longitude"),
            'quality_rating': openapi.Schema(type=openapi.TYPE_INTEGER, description="Quality rating (1-4)", enum=[1, 2, 3, 4]),
            'notes': openapi.Schema(type=openapi.TYPE_STRING, description="Additional notes"),
            'submission_date': openapi.Schema(type=openapi.TYPE_STRING, format="date-time", description="Date and time of submission (optional, will default to now)"),
            'temperature': openapi.Schema(type=openapi.TYPE_NUMBER, description="Temperature at location (optional)"),
            'rainfall': openapi.Schema(type=openapi.TYPE_NUMBER, description="Rainfall at location (optional)"),
        }
    ),
    responses={
        201: MarketPriceResearchSerializer,
        400: openapi.Response('Invalid data', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'error': openapi.Schema(type=openapi.TYPE_STRING),
                'field_errors': openapi.Schema(type=openapi.TYPE_OBJECT, additional_properties=openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)))
            }
        )),
        403: openapi.Response('Not authorized', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'error': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ))
    }
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_market_price(request):
    """Endpoint for agents to submit market price research data from mobile app"""
    if not hasattr(request.user, 'is_agent') or not request.user.is_agent:
        return Response(
            {"error": "Only authorized agents can submit market price data"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Create a copy of the data to avoid modifying the original
    data = request.data.copy()
    
    # Set the agent as the current user
    data['agent'] = request.user.id
    
    # Ensure quantity is provided, default to 1 if not
    if 'quantity' not in data or not data['quantity']:
        data['quantity'] = 1.0
    
    # Ensure date_observed is timezone-aware if provided
    if 'date_observed' in data and data['date_observed']:
        # Try to parse string to datetime if it's a string
        if isinstance(data['date_observed'], str):
            try:
                from django.utils.dateparse import parse_datetime
                from datetime import datetime
                
                # Parse the string to datetime
                dt = parse_datetime(data['date_observed'])
                
                # If parsing failed or returned naive datetime, try other formats
                if dt is None:
                    # Try common date formats
                    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y']:
                        try:
                            dt = datetime.strptime(data['date_observed'], fmt)
                            break
                        except ValueError:
                            continue
                
                # Make timezone aware if it's still naive
                if dt and timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                    data['date_observed'] = dt
            except Exception as e:
                print(f"Error parsing date_observed: {str(e)}")
        # If it's already a datetime but naive, make it aware
        elif hasattr(data['date_observed'], 'tzinfo') and timezone.is_naive(data['date_observed']):
            data['date_observed'] = timezone.make_aware(data['date_observed'])
    else:
        # If not provided, set to current time
        data['date_observed'] = timezone.now()
        
    # Set submission_date if not provided (ensure it's timezone-aware)
    if 'submission_date' not in data or not data['submission_date']:
        data['submission_date'] = timezone.now()
    elif isinstance(data['submission_date'], str):
        try:
            from django.utils.dateparse import parse_datetime
            from datetime import datetime
            
            # Parse the string to datetime
            dt = parse_datetime(data['submission_date'])
            
            # If parsing failed or returned naive datetime, try other formats
            if dt is None:
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(data['submission_date'], fmt)
                        break
                    except ValueError:
                        continue
            
            # Make timezone aware if it's still naive
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
                data['submission_date'] = dt
        except Exception as e:
            print(f"Error parsing submission_date: {str(e)}")
            data['submission_date'] = timezone.now()
    # If it's already a datetime but naive, make it aware
    elif hasattr(data['submission_date'], 'tzinfo') and timezone.is_naive(data['submission_date']):
        data['submission_date'] = timezone.make_aware(data['submission_date'])
    
    # If weather data is not provided, try to fetch it if coordinates are available
    if (not data.get('temperature') or not data.get('rainfall')) and data.get('latitude') and data.get('longitude'):
        try:
            weather_data = fetch_weather_data(data['latitude'], data['longitude'])
            if weather_data:
                data['temperature'] = data.get('temperature', weather_data.get('temperature'))
                data['rainfall'] = data.get('rainfall', weather_data.get('rainfall'))
        except Exception as e:
            # Log the error but continue with the submission
            print(f"Error fetching weather data: {str(e)}")
    
    # DEBUG INFO: Print expected fields and received data
    print("\n==== MARKET PRICE SUBMIT DEBUG INFO =====")
    print("EXPECTED FIELDS:")
    print("Required fields: source_type, source_name, product_name, price, unit")
    print("Optional fields: quantity, region, country, latitude, longitude, quality_rating, notes, submission_date, temperature, rainfall")
    print("\nRECEIVED DATA:")
    for key, value in data.items():
        print(f"  {key}: {value}")
    
    # Validate and save the data
    serializer = MarketPriceResearchSerializer(data=data)
    if serializer.is_valid():
        serializer.save(agent=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    # Print validation errors
    print("\nVALIDATION ERRORS:")
    for field, errors in serializer.errors.items():
        print(f"  {field}: {errors}")
    print("============================================\n")
    
    # Return detailed error information
    return Response({
        'error': 'Invalid data provided', 
        'field_errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

def fetch_weather_data(latitude, longitude):
    """Helper function to fetch current weather data from a weather API"""
    # Note: This is a placeholder. In a real implementation, you would use an actual weather API
    # such as OpenWeatherMap, AccuWeather, etc.
    
    # Example implementation using OpenWeatherMap (you would need an API key)
    try:
        # Replace with your actual API key
        api_key = "YOUR_OPENWEATHERMAP_API_KEY"
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
        
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                'temperature': data['main']['temp'],
                'rainfall': data.get('rain', {}).get('1h', 0)  # Rain in last hour, if available
            }
    except Exception:
        # Just return None if there's any issue with the API
        pass
    
    return None


@login_required
def market_research_dashboard(request):
    """Custom dashboard view for market research data visualization"""
    # Date filters
    end_date = now()
    start_date = end_date - timedelta(days=30)  # Default to last 30 days
    
    # Get list of commodities and sources for the management section
    commodity_list = Commodity.objects.all().order_by('name')
    source_list = Source.objects.all().order_by('name')
    
    # Source types for the form
    source_types = MarketPriceResearch.SOURCE_TYPE_CHOICES
    
    # Get filter parameters from request
    commodity_filter = request.GET.get('commodity', '')
    region_filter = request.GET.get('region', '')
    time_period = request.GET.get('time_period', '30')  # Default 30 days
    
    # Adjust time period based on filter
    if time_period and time_period.isdigit():
        start_date = end_date - timedelta(days=int(time_period))
    elif time_period == 'custom':
        # Handle custom date range if provided
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if date_from:
            try:
                start_date = timezone.datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                pass
        if date_to:
            try:
                end_date = timezone.datetime.strptime(date_to, '%Y-%m-%d')
            except ValueError:
                pass
    
    # Base queryset with time filter
    queryset = MarketPriceResearch.objects.filter(
        date_observed__gte=start_date,
        date_observed__lte=end_date
    )
    
    # Apply additional filters if provided
    if commodity_filter:
        queryset = queryset.filter(product_name__icontains=commodity_filter)
    if region_filter:
        queryset = queryset.filter(Q(source_name__icontains=region_filter) | Q(market__region__icontains=region_filter))
    
    # Get data for summary cards
    total_commodities = queryset.values('product_name').distinct().count()
    recent_updates = MarketPriceResearch.objects.filter(date_observed__gte=now() - timedelta(hours=24)).count()
    
    # Get price data for maize (as an example of a common commodity)
    maize_prices = queryset.filter(product_name__icontains='maize').order_by('-date_observed')
    avg_maize_price = maize_prices.aggregate(Avg('price'))['price__avg'] or 0
    
    # Format as whole number TSh value
    avg_maize_price = int(avg_maize_price)
    
    # Get highest and lowest priced regions
    price_data = queryset.order_by('-date_observed')[:100]  # Limit to recent entries for display
    
    # Get highest and lowest prices
    highest_price_obj = queryset.order_by('-price').first()
    lowest_price_obj = queryset.filter(price__gt=0).order_by('price').first()  # Avoid zero prices
    
    highest_price = {
        'price': int(highest_price_obj.price) if highest_price_obj else 0,
        'region': highest_price_obj.source_name if highest_price_obj else 'N/A',
        'product': highest_price_obj.product_name if highest_price_obj else ''
    }
    
    lowest_price = {
        'price': int(lowest_price_obj.price) if lowest_price_obj else 0,
        'region': lowest_price_obj.source_name if lowest_price_obj else 'N/A',
        'product': lowest_price_obj.product_name if lowest_price_obj else ''
    }
    
    # Get list of all commodities and regions for filters
    commodities = queryset.values_list('product_name', flat=True).distinct()
    regions = queryset.values_list('source_name', flat=True).distinct()
    
    # Generate price alerts for significant changes
    price_alerts = []
    
    # Find commodities with significant price changes
    for commodity in commodities[:5]:  # Limit to top 5 commodities
        # Get average price a week ago
        week_ago = end_date - timedelta(days=7)
        old_avg = queryset.filter(
            product_name=commodity,
            date_observed__lt=week_ago
        ).aggregate(Avg('price'))['price__avg'] or 0
        
        # Get current average price
        current_avg = queryset.filter(
            product_name=commodity,
            date_observed__gte=week_ago
        ).aggregate(Avg('price'))['price__avg'] or 0
        
        if old_avg > 0:
            percent_change = ((current_avg - old_avg) / old_avg) * 100
            if abs(percent_change) >= 10:  # Alert for 10% or more change
                alert_type = 'price-alert price-spike' if percent_change > 0 else 'price-alert price-drop'
                price_alerts.append({
                    'type': alert_type,
                    'title': f"{commodity} Price {'Increase' if percent_change > 0 else 'Decrease'}",
                    'message': f"Average price has {'increased' if percent_change > 0 else 'decreased'} in the last week",
                    'change': f"{int(abs(percent_change))}%"
                })
    
    # Prepare chart data
    # 1. Trend data - example for one commodity over time
    trend_data = {
        'dates': [],
        'datasets': []
    }
    
    # For demonstration, create sample data for visualization
    # In production, this would be actual database data
    if commodities:
        default_commodity = list(commodities)[0] if commodity_filter == '' else commodity_filter
        
        # Get dates for the chart (last 30 days)
        date_range = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, 0, -1)]
        trend_data['dates'] = date_range
        
        # Create dataset for the commodity
        commodity_data = []
        for date_str in date_range:
            # Convert string to datetime and make it timezone-aware
            date_obj = timezone.datetime.strptime(date_str, '%Y-%m-%d')
            # Apply timezone info to avoid naive datetime warnings
            date_obj = timezone.make_aware(date_obj)
            next_day = date_obj + timedelta(days=1)
            
            # Get average price for this day
            day_avg = queryset.filter(
                product_name=default_commodity,
                date_observed__gte=date_obj,
                date_observed__lt=next_day
            ).aggregate(Avg('price'))['price__avg'] or 0
            
            commodity_data.append(int(day_avg) if day_avg else None)
        
        trend_data['datasets'] = [{
            'label': default_commodity,
            'data': commodity_data,
            'borderColor': '#4E6C50',
            'backgroundColor': 'rgba(78, 108, 80, 0.1)',
            'tension': 0.4
        }]
    
    # 2. Comparison data - different regions for one commodity
    comparison_data = {
        'regions': [],
        'prices': []
    }
    
    # Get top regions by data volume
    top_regions = list(queryset.values('source_name').annotate(count=Count('id')).order_by('-count')[:5])
    region_names = [r['source_name'] for r in top_regions]
    comparison_data['regions'] = region_names
    
    # Default to first commodity if filter not specified
    comparison_commodity = list(commodities)[0] if commodities and commodity_filter == '' else commodity_filter
    
    # Get average prices for each region for the selected commodity
    for region in region_names:
        avg_price = queryset.filter(
            product_name=comparison_commodity,
            source_name=region
        ).aggregate(Avg('price'))['price__avg'] or 0
        comparison_data['prices'].append(int(avg_price))
    
    # Get product analysis data for the selected commodity
    product_analysis = {}
    if commodity_filter:
        target_commodity = commodity_filter
    elif commodities:
        target_commodity = list(commodities)[0]
    else:
        target_commodity = None

    if target_commodity:
        # Perform detailed product analysis
        commodity_data = queryset.filter(product_name=target_commodity)
        
        if commodity_data.exists():
            # Price statistics
            price_stats = commodity_data.aggregate(
                avg=Avg('price'),
                min=Min('price'),
                max=Max('price')
            )
            
            # Calculate price volatility
            prices = list(commodity_data.values_list('price', flat=True))
            mean_price = sum(float(p) for p in prices) / len(prices) if prices else 0
            sum_squared_diff = sum((float(price) - mean_price) ** 2 for price in prices)
            std_dev = math.sqrt(sum_squared_diff / len(prices)) if prices else 0
            volatility = (std_dev / mean_price * 100) if mean_price else 0
            
            # Regional comparison
            regions_data = {}
            for item in commodity_data:
                region = item.source_name or 'Unknown'
                if region not in regions_data:
                    regions_data[region] = []
                regions_data[region].append(float(item.price))
            
            regional_analysis = [{
                'region': region,
                'avg_price': int(sum(prices) / len(prices)) if prices else 0,
                'sample_count': len(prices)
            } for region, prices in regions_data.items()]
            
            # Sort by price
            regional_analysis.sort(key=lambda x: x['avg_price'], reverse=True)
            
            # Calculate price trend
            if len(commodity_data) > 1:
                # Group by date for trend calculation
                date_prices = {}
                for item in commodity_data:
                    date_key = item.date_observed.strftime('%Y-%m-%d')
                    if date_key not in date_prices:
                        date_prices[date_key] = []
                    date_prices[date_key].append(float(item.price))
                
                # Get daily averages in order
                daily_avgs = []
                for date in sorted(date_prices.keys()):
                    daily_avgs.append(sum(date_prices[date]) / len(date_prices[date]))
                
                # Simple linear regression for trend
                if len(daily_avgs) > 1:
                    x = list(range(len(daily_avgs)))
                    y = daily_avgs
                    
                    n = len(x)
                    sum_x = sum(x)
                    sum_y = sum(y)
                    sum_xy = sum(x_i * y_i for x_i, y_i in zip(x, y))
                    sum_xx = sum(x_i * x_i for x_i in x)
                    
                    # Calculate slope
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
                    
                    # Determine trend
                    if slope > 0:
                        price_trend = "increasing"
                    elif slope < 0:
                        price_trend = "decreasing"
                    else:
                        price_trend = "stable"
                else:
                    price_trend = "unknown"
            else:
                price_trend = "unknown"
            
            # Full product analysis data
            product_analysis = {
                'commodity': target_commodity,
                'sample_count': commodity_data.count(),
                'price_stats': {
                    'average': int(price_stats['avg']) if price_stats['avg'] else 0,
                    'minimum': int(price_stats['min']) if price_stats['min'] else 0,
                    'maximum': int(price_stats['max']) if price_stats['max'] else 0,
                    'range': int(price_stats['max'] - price_stats['min']) if price_stats['max'] and price_stats['min'] else 0,
                    'volatility': round(volatility, 2),
                    'trend': price_trend
                },
                'regional_analysis': regional_analysis[:5]  # Top 5 regions
            }

    context = {
        'price_data': price_data,
        'total_commodities': total_commodities,
        'avg_maize_price': avg_maize_price,
        'highest_price': highest_price,
        'lowest_price': lowest_price,
        'recent_updates': recent_updates,
        'commodities': commodities,
        'regions': regions,
        'price_alerts': price_alerts,
        'trend_data': json.dumps(trend_data),
        'comparison_data': json.dumps(comparison_data),
        'commodity_list': commodity_list,
        'source_list': source_list,
        'source_types': source_types,
        'product_analysis': json.dumps(product_analysis)
    }
    
    return render(request, 'market_research/dashboard.html', context)


@login_required
def add_commodity(request):
    """Add or edit a commodity"""
    if request.method == 'POST':
        commodity_id = request.POST.get('commodity_id')
        
        # If commodity_id is provided, we're editing an existing commodity
        if commodity_id:
            commodity = get_object_or_404(Commodity, id=commodity_id)
        else:
            commodity = Commodity()
        
        # Update commodity with form data
        commodity.name = request.POST.get('commodity_name')
        commodity.category = request.POST.get('category')
        commodity.default_unit = request.POST.get('default_unit')
        commodity.description = request.POST.get('description')
        commodity.save()
        
        messages.success(request, f"Commodity '{commodity.name}' has been {'updated' if commodity_id else 'added'} successfully.")
        return redirect('market_research_dashboard')
    
    # If not POST, redirect to dashboard
    return redirect('market_research_dashboard')


@login_required
def delete_commodity(request, commodity_id):
    """Delete a commodity"""
    commodity = get_object_or_404(Commodity, id=commodity_id)
    name = commodity.name
    commodity.delete()
    
    messages.success(request, f"Commodity '{name}' has been deleted successfully.")
    return redirect('market_research_dashboard')


@login_required
def submit_price_data(request):
    """Submit price data from the dashboard"""
    if request.method == 'POST':
        # Handle the case where 'other' is selected as the product
        product_name = request.POST.get('product_name')
        if product_name == 'other':
            product_name = request.POST.get('other_product')
        
        # Handle the case where 'other' is selected as the source name
        source_name = request.POST.get('source_name')
        if source_name == 'other':
            source_name = request.POST.get('other_source')
        
        # Create a new price research entry
        price_data = {
            'product_name': product_name,
            'source_type': request.POST.get('source_type'),
            'source_name': source_name,
            'price': request.POST.get('price'),
            'quantity': request.POST.get('quantity', 1),
            'unit': request.POST.get('unit'),
            'quality_rating': request.POST.get('quality_rating') or None,
            'notes': request.POST.get('notes') or None,
        }
        
        # Associate with source if we have a source_id
        source_id = request.POST.get('source_id')
        if source_id:
            try:
                source = Source.objects.get(id=source_id)
                price_data['source'] = source
                # If this is a market source, use its linked market
                if source.source_type == 'market' and source.market:
                    price_data['market'] = source.market
            except Source.DoesNotExist:
                pass
        
        # Always ensure we have a market (required field)
        if price_data['source_type'] == 'market':
            # Try to get an existing market with this name
            market_name = price_data['source_name']
            market, created = Market.objects.get_or_create(
                name=market_name,
                defaults={
                    'location': market_name,
                    'region': 'Unknown',
                    'is_active': True
                }
            )
            price_data['market'] = market
        else:
            # For non-market sources, get or create a default market
            default_market, created = Market.objects.get_or_create(
                name="Default Market",
                defaults={
                    'location': "Default Location",
                    'region': "Default Region",
                    'is_active': True
                }
            )
            price_data['market'] = default_market
        
        # Associate with commodity if we have a commodity_id
        commodity_id = request.POST.get('commodity_id')
        if commodity_id:
            try:
                commodity = Commodity.objects.get(id=commodity_id)
                price_data['commodity'] = commodity
            except Commodity.DoesNotExist:
                pass
        
        # Create the price research object
        price_research = MarketPriceResearch(**price_data)
        
        if request.user.is_authenticated:
            price_research.agent = request.user
        
        price_research.save()
        
        messages.success(request, f"Price data for {product_name} successfully recorded!")
        return redirect('market_research_dashboard')
    
    return redirect('market_research_dashboard')

@swagger_auto_schema(
    method='get',
    operation_description="API endpoint to get comparison data for charts",
    manual_parameters=[
        openapi.Parameter('commodity', openapi.IN_QUERY, description="Name of the commodity to filter by", type=openapi.TYPE_STRING),
    ],
    responses={200: openapi.Response('Comparison data', schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'regions': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
            'prices': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)),
            'commodity': openapi.Schema(type=openapi.TYPE_STRING)
        }
    ))}
)
@api_view(['GET'])
def get_comparison_data(request):
    """API endpoint to get comparison data for charts"""
    commodity_name = request.GET.get('commodity', '')
    
    # Default time period: last 30 days
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Base query for recent data
    query = MarketPriceResearch.objects.filter(
        date_observed__gte=start_date,
        date_observed__lte=end_date
    )
    
    # Filter by commodity if provided
    if commodity_name:
        query = query.filter(product_name__icontains=commodity_name)
    
    # Get top regions by data volume
    top_regions = list(query.values('source_name').annotate(count=Count('id')).order_by('-count')[:5])
    region_names = [r['source_name'] for r in top_regions]
    
    # Get average prices for each region
    prices = []
    for region in region_names:
        avg_price = query.filter(source_name=region).aggregate(Avg('price'))['price__avg'] or 0
        prices.append(int(avg_price))
    
    return Response({
        'regions': region_names,
        'prices': prices,
        'commodity': commodity_name
    })

@swagger_auto_schema(
    method='get',
    operation_description="API endpoint to get profit data with transportation costs",
    manual_parameters=[
        openapi.Parameter('product', openapi.IN_QUERY, description="Product ID to filter by", type=openapi.TYPE_STRING),
        openapi.Parameter('farm_location', openapi.IN_QUERY, description="Farm location", type=openapi.TYPE_STRING),
        openapi.Parameter('regions[]', openapi.IN_QUERY, description="List of region names", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
        openapi.Parameter('cost_per_km', openapi.IN_QUERY, description="Transportation cost per kilometer", type=openapi.TYPE_NUMBER, default=500),
    ],
    responses={200: 'Regional profit data'}
)
@api_view(['GET'])
def get_regional_profit_data(request):
    """API endpoint to get profit data with transportation costs"""
    product_id = request.GET.get('product', '')
    farm_location = request.GET.get('farm_location', '')
    selected_regions = request.GET.getlist('regions[]', [])
    cost_per_km = float(request.GET.get('cost_per_km', 500))
    
    # Get recent price data (last 30 days)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Base query for price data
    query = MarketPriceResearch.objects.filter(
        date_observed__gte=start_date,
        date_observed__lte=end_date
    )
    
    # Filter by product name if provided
    if product_id:
        try:
            commodity = Commodity.objects.get(id=product_id)
            query = query.filter(product_name__icontains=commodity.name)
        except Commodity.DoesNotExist:
            pass
    
    # If no regions selected, get top regions by data volume from database
    if not selected_regions:
        top_regions = list(query.values('source_name').annotate(count=Count('id')).order_by('-count')[:5])
        selected_regions = [r['source_name'] for r in top_regions]
        
        # If still no regions (empty database), provide at least one default region
        if not selected_regions:
            # Use regions from Market model if available
            market_regions = list(Market.objects.values_list('region', flat=True).distinct())
            if market_regions:
                selected_regions = market_regions[:5]
            else:
                # Last resort - use a single default
                selected_regions = ['Local Market']
            
    result_data = {
        'labels': [],
        'prices': [],
        'distances': [],
        'transport_costs': [],
        'profits': []
    }
    
    # Dictionary to store distance data calculated from the farm location
    distance_data = {}
    
    # Get all markets from database for distance calculations
    # In a real app, you'd use a distance API or stored distances
    # For now, use market data if available, otherwise calculate
    markets = Market.objects.all()
    for market in markets:
        # Use dynamic distances if available in your data model
        # For now, simulate based on region names to ensure consistent results
        region_name = market.region
        
        # Simple algorithm to generate consistent distances based on name
        # This ensures consistent numbers between page refreshes
        import hashlib
        # Create hash from region name
        name_hash = hashlib.md5(region_name.encode()).hexdigest()
        # Convert first 4 hex characters to integer (0-65535)
        hash_value = int(name_hash[:4], 16)
        # Scale to reasonable distance (10-1000 km)
        distance = 10 + (hash_value % 990)
        
        # If this is the farm location, distance is 0
        if region_name == farm_location:
            distance = 0
            
        distance_data[region_name] = distance
    
    # For each selected region, calculate metrics
    for region in selected_regions:
        # Get average price in this region
        region_price = query.filter(source_name__icontains=region).aggregate(Avg('price'))['price__avg'] or 0
        if region_price == 0:
            # If no price data exists for this region, use a random but reasonable price
            import random
            region_price = random.randint(1000, 5000)  # Random price between 1000-5000 TSh
        else:
            region_price = int(region_price)
        
        # Get distance from farm
        # If we don't have distance data for this region, generate a consistent one
        if region not in distance_data:
            import hashlib
            # Create hash from region name
            name_hash = hashlib.md5(region.encode()).hexdigest()
            # Convert first 4 hex characters to integer (0-65535)
            hash_value = int(name_hash[:4], 16)
            # Scale to reasonable distance (50-800 km)
            distance = 50 + (hash_value % 750)
            
            # If this is the farm location, distance is 0
            if region == farm_location:
                distance = 0
        else:
            distance = distance_data[region]
        
        # Calculate transport cost per kg
        # Simplified model: cost_per_km * distance / 1000kg (assumed load)
        transport_cost = (cost_per_km * distance) / 1000
        
        # Calculate profit (price - transport cost)
        profit = region_price - transport_cost
        
        # Add to results
        result_data['labels'].append(region)
        result_data['prices'].append(region_price)
        result_data['distances'].append(distance)
        result_data['transport_costs'].append(round(transport_cost))
        result_data['profits'].append(round(profit))
    
    return Response(result_data)

@swagger_auto_schema(
    method='get',
    operation_description="API endpoint to get seasonal price trends for commodities",
    manual_parameters=[
        openapi.Parameter('commodities[]', openapi.IN_QUERY, description="List of commodity IDs", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER)),
    ],
    responses={200: 'Seasonal trend data'}
)
@api_view(['GET'])
def get_seasonal_data(request):
    """API endpoint to get seasonal price trends for commodities"""
    # Get up to 3 commodities to display
    commodity_ids = request.GET.getlist('commodities[]', [])
    
    # If no specific commodities are requested, get the top commodities by volume
    if not commodity_ids:
        # Get the most common commodities in the database
        top_commodities = MarketPriceResearch.objects.values('product_name') \
                         .annotate(count=Count('id')) \
                         .order_by('-count')[:3]
        commodity_names = [item['product_name'] for item in top_commodities]
    else:
        # Get the requested commodities
        try:
            commodities = Commodity.objects.filter(id__in=commodity_ids)
            commodity_names = [commodity.name for commodity in commodities]
        except:
            commodity_names = []
    
    # Define quarters (for simplicity, we use fixed date ranges)
    current_year = timezone.now().year
    quarters = [
        {
            'name': 'Q1',
            'start': timezone.datetime(current_year, 1, 1),
            'end': timezone.datetime(current_year, 3, 31)
        },
        {
            'name': 'Q2',
            'start': timezone.datetime(current_year, 4, 1),
            'end': timezone.datetime(current_year, 6, 30)
        },
        {
            'name': 'Q3',
            'start': timezone.datetime(current_year, 7, 1),
            'end': timezone.datetime(current_year, 9, 30)
        },
        {
            'name': 'Q4',
            'start': timezone.datetime(current_year, 10, 1),
            'end': timezone.datetime(current_year, 12, 31)
        }
    ]
    
    # Prepare result structure
    result = {
        'labels': [q['name'] for q in quarters],
        'datasets': []
    }
    
    # Generate color pairs for each dataset
    colors = [
        {'border': '#AA8B56', 'background': 'rgba(170, 139, 86, 0.2)'}, 
        {'border': '#4E6C50', 'background': 'rgba(78, 108, 80, 0.2)'}, 
        {'border': '#395144', 'background': 'rgba(57, 81, 68, 0.2)'}
    ]
    
    # For each commodity, get seasonal data
    for index, commodity_name in enumerate(commodity_names):
        # Placeholder for actual data retrieval logic
        # For now, generate dummy data that simulates seasonal trends
        
        dataset = {
            'label': commodity_name,
            'data': [],
            'borderColor': colors[index % len(colors)]['border'],
            'backgroundColor': colors[index % len(colors)]['background'],
            'tension': 0.4
        }
        
        # For each quarter, generate a simulated average price
        for quarter in quarters:
            # Simulate a base price around 1000 TSh
            base_price = 1000
            
            # Adjust price based on quarter (simulate seasonality)
            if quarter['name'] == 'Q1':
                # Q1: Lower prices (e.g., post-harvest)
                adjusted_price = base_price * (0.8 + 0.2 * index)
            elif quarter['name'] == 'Q2':
                # Q2: Gradual increase (e.g., pre-harvest)
                adjusted_price = base_price * (1.0 + 0.2 * index)
            elif quarter['name'] == 'Q3':
                # Q3: Higher prices (e.g., scarcity)
                adjusted_price = base_price * (1.2 + 0.3 * index)
            elif quarter['name'] == 'Q4':
                # Q4: Decrease as new harvest comes in
                adjusted_price = base_price * (1.0 + 0.1 * index)
            
            # Append the simulated price to the dataset
            dataset['data'].append(adjusted_price)
        
        # Add the dataset to the result
        result['datasets'].append(dataset)
    
    return Response(result)

@login_required
def market_map_view(request):
    """View function for displaying market locations on a map"""
    # Get market data with location information
    markets_with_location = MarketPriceResearch.objects.filter(
        latitude__isnull=False, 
        longitude__isnull=False
    ).order_by('-date_observed')
    
    # Create a dict to store the latest data for each market/commodity combination
    market_data = {}
    
    for price in markets_with_location:
        key = f"{price.source_name}_{price.product_name}"
        
        # If this market/commodity hasn't been seen yet or this record is newer
        if key not in market_data or price.date_observed > market_data[key]['date_observed']:
            market_data[key] = {
                'name': price.source_name,
                'region': price.region or "Unknown",
                'latitude': float(price.latitude),  # Convert to float for JSON serialization
                'longitude': float(price.longitude),
                'commodity': price.product_name,
                'avg_price': float(price.price),
                'unit': price.unit,
                'date_observed': price.date_observed,
                'last_updated': price.date_observed.strftime('%Y-%m-%d')
            }
    
    # Convert to list for template
    market_list = list(market_data.values())
    
    # Create JSON-serializable version of the market list
    json_market_list = []
    for market in market_list:
        # Create a copy of the market data without the datetime object
        market_copy = market.copy()
        # Remove the datetime object that can't be serialized
        market_copy.pop('date_observed', None)
        # Add to the list for JSON serialization
        json_market_list.append(market_copy)
    
    # Get unique commodity names for filter dropdown
    commodities = MarketPriceResearch.objects.values_list(
        'product_name', flat=True
    ).distinct()
    
    context = {
        'market_data': json.dumps(json_market_list),
        'commodities': commodities
    }
    
    return render(request, 'market_research/enhanced_map_view.html', context)

@swagger_auto_schema(
    method='get',
    operation_description="Mobile-optimized endpoint for listing available markets",
    manual_parameters=[
        openapi.Parameter('region', openapi.IN_QUERY, description="Filter markets by region", type=openapi.TYPE_STRING, required=False),
    ],
    responses={
        200: openapi.Response('List of markets', schema=openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                    'location': openapi.Schema(type=openapi.TYPE_STRING),
                    'region': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ))
    }
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def mobile_market_list(request):
    """Mobile-optimized endpoint for listing available markets"""
    region_filter = request.GET.get('region', None)
    
    # Filter markets by region if specified
    if region_filter:
        markets = Market.objects.filter(is_active=True, region__icontains=region_filter)
    else:
        markets = Market.objects.filter(is_active=True)
    
    # Serialize market data
    serializer = MarketSerializer(markets, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_description="Mobile-optimized endpoint for listing available commodities",
    manual_parameters=[
        openapi.Parameter('category', openapi.IN_QUERY, description="Filter commodities by category", type=openapi.TYPE_STRING, required=False),
    ],
    responses={
        200: openapi.Response('List of commodities', schema=openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                    'category': openapi.Schema(type=openapi.TYPE_STRING),
                    'default_unit': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ))
    }
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def mobile_commodity_list(request):
    """Mobile-optimized endpoint for listing available commodities"""
    category_filter = request.GET.get('category', None)
    
    # Filter commodities by category if specified
    if category_filter:
        commodities = Commodity.objects.filter(category__icontains=category_filter)
    else:
        commodities = Commodity.objects.all()
    
    # Serialize commodity data
    serializer = CommoditySerializer(commodities, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_description="Mobile-optimized endpoint for getting recent market prices",
    manual_parameters=[
        openapi.Parameter('commodity', openapi.IN_QUERY, description="Filter prices by commodity name", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('region', openapi.IN_QUERY, description="Filter prices by region/source name", type=openapi.TYPE_STRING, required=False),
        openapi.Parameter('days', openapi.IN_QUERY, description="Number of days of data to return (default: 7)", type=openapi.TYPE_INTEGER, required=False),
    ],
    responses={
        200: openapi.Response('Recent price data', schema=openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'product_name': openapi.Schema(type=openapi.TYPE_STRING),
                    'source_name': openapi.Schema(type=openapi.TYPE_STRING),
                    'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'unit': openapi.Schema(type=openapi.TYPE_STRING),
                    'date_observed': openapi.Schema(type=openapi.TYPE_STRING, format='date-time'),
                    'region': openapi.Schema(type=openapi.TYPE_STRING),
                    'latitude': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'longitude': openapi.Schema(type=openapi.TYPE_NUMBER),
                }
            )
        ))
    }
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def mobile_recent_prices(request):
    """Mobile-optimized endpoint for getting recent market prices"""
    commodity_filter = request.GET.get('commodity', None)
    region_filter = request.GET.get('region', None)
    days = int(request.GET.get('days', 7))  # Default to 7 days of data
    
    # Get recent price data
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Base query
    query = MarketPriceResearch.objects.filter(
        date_observed__gte=start_date,
        date_observed__lte=end_date
    ).order_by('-date_observed')
    
    # Apply filters if specified
    if commodity_filter:
        query = query.filter(product_name__icontains=commodity_filter)
    if region_filter:
        query = query.filter(
            Q(source_name__icontains=region_filter) | 
            Q(region__icontains=region_filter)
        )
    
    # Limit to 100 most recent entries to avoid overwhelming the mobile app
    query = query[:100]
    
    # Prepare response data (simplified for mobile)
    result = []
    for price in query:
        result.append({
            'product_name': price.product_name,
            'source_name': price.source_name,
            'source_type': price.source_type,
            'price': float(price.price),
            'quantity': float(price.quantity),
            'unit': price.unit,
            'unit_price': float(price.unit_price),
            'date_observed': price.date_observed,
            'region': price.region,
            'latitude': price.latitude,
            'longitude': price.longitude,
        })
    
    return Response(result)
