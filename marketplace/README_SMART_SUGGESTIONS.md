# Smart Product Suggestion System (Apriori-Based)

This document provides information about the Smart Product Suggestion System implemented for Kikapu Marketplace.

## Overview

The Smart Product Suggestion System uses a multi-tiered approach to recommend products to users:

1. **Apriori Algorithm (Market Basket Analysis)**: Automatically suggests products based on actual purchase patterns.
2. **Manual Product Relationships**: Allows administrators to define complementary product relationships.
3. **Popular Product Fallback**: Ensures recommendations are always available even with limited data.

When customers add products to their cart, the system shows "You Might Also Like" recommendations using this layered strategy.

## Features

1. **Automated Data Collection**: Every time a purchase is completed, the system records which products were bought together in that order.

2. **Market Basket Analysis**: The Apriori algorithm analyzes purchase patterns to discover product associations.

3. **Manual Relationship Definition**: Administrators can define custom product relationships through the admin panel.

4. **Dynamic Recommendations**: Personalized product suggestions appear in the cart and checkout pages.

5. **Three-tier Recommendation Strategy**:
   - First tries to use Apriori-generated associations from purchase history
   - Then falls back to manually defined product relationships
   - Finally uses trending/popular products if needed

6. **Self-Learning System**: As more purchases are made, the system continuously improves its recommendations.

## Technical Implementation

The system consists of:

1. **Purchase Model**: Records products bought together with a shared order_id.

2. **ProductAssociation Model**: Stores Apriori-generated association rules for quick lookups.

3. **RelatedProduct Model**: Stores manually defined product relationships for when there isn't enough purchase data.

4. **Management Commands**: 
   - `generate_suggestions`: Runs the Apriori algorithm on purchase data
   - `save_associations`: Saves the generated rules to the database

5. **Recommendation Engine**: Presents related products to users in the cart view.

## Usage Instructions

### Running the Suggestion Generator

To generate product suggestions using the Apriori algorithm:

```bash
# Just print the rules (does not save to database):
python manage.py generate_suggestions

# Print rules with custom parameters:
python manage.py generate_suggestions --min-support=0.03 --min-lift=1.5 --min-confidence=0.4

# Generate and save rules to database:
python manage.py generate_suggestions --save
```

### Using the Save Command (Recommended)

For production use, the `save_associations` command is recommended:

```bash
# Interactive mode (will ask for confirmation)
python manage.py save_associations

# Non-interactive mode (for scheduled tasks)
python manage.py save_associations --run-auto
```

### Defining Manual Product Relationships

To create manual product relationships (used when there isn't enough purchase data):

1. Go to the Django Admin Panel
2. Navigate to "Marketplace > Related products"
3. Click "Add Related product"
4. Select the main product and the related product
5. Choose a relationship type (e.g., "complementary", "substitute", "accessory")
6. Set a relevance score (1-10, with 10 being highest relevance)
7. Add optional notes explaining the relationship
8. Save the relationship

For example, if you want to suggest cooking oil, salt, and flour to customers who buy eggs:
- Create a relationship: "Eggs → Cooking Oil" (complementary, score: 9)
- Create a relationship: "Eggs → Salt" (complementary, score: 8)
- Create a relationship: "Eggs → Flour" (complementary, score: 7)

### Parameters Explained

- `min-support`: Minimum percentage of orders that must contain a product set (default: 0.05 or 5%)
- `min-lift`: Minimum lift value for a rule to be considered useful (default: 1.0)
- `min-confidence`: Minimum confidence value for a rule (default: 0.3 or 30%)

### Setting Up Scheduled Tasks

For optimal results, set up a scheduled task to regularly update the product recommendations:

#### Using Cron (Linux/Mac):

```bash
# Example: Run every Sunday at 1 AM
0 1 * * 0 /path/to/python /path/to/manage.py save_associations --run-auto
```

#### Using Windows Task Scheduler:

Create a batch file with:
```batch
cd /d C:\path\to\project
python manage.py save_associations --run-auto
```

Then schedule it to run weekly.

## Required Packages

This system requires:

```
pandas
mlxtend
```

Install with: `pip install pandas mlxtend`

## Troubleshooting

1. **No suggestions appear**: 
   - Check if you have sufficient purchase data
   - Try reducing min-support to generate more rules
   - Add manual product relationships through the admin panel

2. **Poor quality suggestions**:
   - Try increasing min-lift and min-confidence
   - Collect more purchase data
   - Review and update manual product relationships

3. **Performance issues**:
   - Ensure you're using the ProductAssociation model for lookups
   - Add appropriate indexes to the database

## Future Enhancements

- Save rules to Redis cache for faster lookups
- Add weighting based on recency of purchases
- Implement A/B testing framework for suggestion quality
- Add product category filtering in recommendations
- Implement a visual relationship editor for manual relationships