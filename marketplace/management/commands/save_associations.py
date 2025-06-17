from django.db import transaction
from django.core.management.base import BaseCommand
from marketplace.models import ProductAssociation

class SaveAssociationsCommand(BaseCommand):
    help = 'Save the Apriori-generated product associations to database for quick lookups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-auto',
            action='store_true',
            help='Run this automatically without manual confirmation (useful for scheduled tasks)'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """
        This command runs the generate_suggestions command with the --save flag
        and provides appropriate user feedback.
        """
        run_auto = options['run_auto']
        
        if not run_auto:
            self.stdout.write(
                "This will run the Apriori algorithm and save product associations to the database.\n"
                "Existing associations will be replaced. Continue? (y/n)"
            )
            confirm = input().lower()
            if confirm != 'y':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return
        
        # Run the generate_suggestions command with --save flag
        from django.core.management import call_command
        
        self.stdout.write("Running Apriori algorithm and generating association rules...")
        call_command('generate_suggestions', '--save')
        
        # Count how many associations were saved
        association_count = ProductAssociation.objects.count()
        
        if association_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f"Successfully saved {association_count} product associations to the database."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "No product associations were saved. This could be due to insufficient purchase data "
                "or the algorithm's thresholds being too high."
            ))