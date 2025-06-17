import pandas as pd
from mlxtend.frequent_patterns import apriori
from mlxtend.frequent_patterns import association_ seCommand
from marketplace.models import Purchase, Product, ProductAssociation
from django.db import transaction

class Command(BaseCommand):
    help = 'Generate product suggestions using Apriori algorithm based on purchase history'

    def add_arguments(self, parser):
      
    def handle(self, *args, **options):
        # Get parameters
        min_support = options['min_support']
        min_lift = options['min_lift']
        min_confidence = options['min_confidence']
        save_to_db = options['save']
        
        self.stdout.write(self.style.SUCCESS(f'Starting Apriori analysis with min_support={min_support}, min_lift={min_lift}'))
        
        # Check if we have enough purchase data
        purchase_count = Purchase.objects.count()
        
        if purchase_count == 0:
            self.stdout.write(self.style.WARNING('No purchase data found. Please collect more data before running this command.'))
            return
        
        self.stdout.write(f'Found {purchase_count} purchase records')
        
        # Get all purchases and convert to DataFrame
        purchases = Purchase.objects.all().values('order_id', 'product_id')
        df = pd.DataFrame(list(purchases))
        
        if df.empty:
            self.stdout.write(self.style.WARNING('No purchase data found after filtering.'))
            return
        
        # Create a one-hot encoded matrix (transaction × product)
        basket = pd.crosstab(df['order_id'], df['product_id'])
        
        # Convert to binary representation (product purchased or not)
        basket_binary = (basket > 0).astype(int)
        
        # Apply Apriori algorithm to find frequent itemsets
        try:
            self.stdout.write('Running Apriori algorithm...')
            frequent_itemsets = apriori(basket_binary, 
                                       min_support=min_support, 
                                       use_colnames=True)
            
            if frequent_itemsets.empty:
                self.stdout.write(self.style.WARNING(
                    f'No frequent itemsets found with min_support={min_support}. Try lowering the threshold.'))
                return
                
            self.stdout.write(f'Found {len(frequent_itemsets)} frequent itemsets')
            
            # Generate association rules
            rules = association_rules(frequent_itemsets, 
                                     metric="lift", 
                                     min_threshold=min_lift)
            
            # Filter by minimum confidence
            rules = rules[rules['confidence'] >= min_confidence]
            
            if rules.empty:
                self.stdout.write(self.style.WARNING(
                    f'No association rules found with min_lift={min_lift} and min_confidence={min_confidence}. Try adjusting thresholds.'))
                return
                
            self.stdout.write(f'Generated {len(rules)} association rules')
            
            # Map product IDs to product names for better readability
            product_id_to_name = {
                p.id: p.name for p in Product.objects.all()
            }
            
            # Print the rules in a readable format
            self.stdout.write(self.style.SUCCESS('Top product association rules:'))
            self.stdout.write('----------------------------------------------------------------')
            self.stdout.write('| If customer buys | They might also buy | Confidence | Lift |')
            self.stdout.write('----------------------------------------------------------------')
            
            # Sort rules by lift (strongest associations first)
            sorted_rules = rules.sort_values('lift', ascending=False)
            
            # Save rules to database if requested
            if save_to_db:
                self.save_rules_to_db(sorted_rules)
            
            # Print top 20 rules
            for _, row in sorted_rules.head(20).iterrows():
                antecedents = list(row['antecedents'])
                consequents = list(row['consequents'])
                
                # Convert product IDs to names
                antecedent_names = [product_id_to_name.get(int(a), f"Product {a}") for a in antecedents]
                consequent_names = [product_id_to_name.get(int(c), f"Product {c}") for c in consequents]
                
                # Format the output
                antecedent_str = ', '.join(antecedent_names)
                consequent_str = ', '.join(consequent_names)
                confidence = row['confidence']
                lift = row['lift']
                
                self.stdout.write(f'| {antecedent_str} | {consequent_str} | {confidence:.2f} | {lift:.2f} |')
            
            self.stdout.write('----------------------------------------------------------------')
            self.stdout.write(self.style.SUCCESS('Apriori analysis completed successfully.'))
            
            if save_to_db:
                self.stdout.write(self.style.SUCCESS(
                    'Rules have been saved to the database and will be used for product suggestions.'))
            else:
                self.stdout.write(self.style.WARNING(
                    'Rules were only printed, not saved. Use --save to save them to the database.'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during Apriori analysis: {str(e)}'))
            
    @transaction.atomic
    def save_rules_to_db(self, rules):
        """Save the generated rules to the ProductAssociation model."""
        try:
            # Start by clearing existing associations
            ProductAssociation.objects.all().delete()
            self.stdout.write('Cleared existing product associations')
            
            # Keep track of how many rules we've saved
            created_count = 0
            
            # Process each rule and save to the database
            for _, row in rules.iterrows():
                # Currently we only handle rules with single item in antecedent and consequent
                # since that's most useful for product recommendations
                antecedents = list(row['antecedents'])
                consequents = list(row['consequents'])
                
                # Skip rules with multiple products in antecedent or consequent
                if len(antecedents) != 1 or len(consequents) != 1:
                    continue
                
                # Get product IDs
                product_id = int(antecedents[0])
                recommendation_id = int(consequents[0])
                
                # Skip if product is recommending itself
                if product_id == recommendation_id:
                    continue
                
                try:
                    # Get the actual product objects
                    product = Product.objects.get(id=product_id)
                    recommendation = Product.objects.get(id=recommendation_id)
                    
                    # Create the association record
                    ProductAssociation.objects.create(
                        product=product,
                        recommendation=recommendation,
                        confidence=float(row['confidence']),
                        lift=float(row['lift']),
                        support=float(row['support'])
                    )
                    created_count += 1
                except Product.DoesNotExist:
                    # Skip if one of the products doesn't exist
                    continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Error saving rule: {str(e)}"))
            
            self.stdout.write(self.style.SUCCESS(f'Successfully saved {created_count} product associations'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error saving rules to database: {str(e)}'))