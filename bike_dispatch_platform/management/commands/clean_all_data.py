from django.core.management.base import BaseCommand
from data_process.models import BikeRideData
from operation_management.models import Vehicle, ScheduleTask, ParkingSpot
from demand_prediction.models import PredictionResult

class Command(BaseCommand):
    help = 'Clear all data from the database'

    def handle(self, *args, **options):
        self.stdout.write('===== Starting to clear database tables =====')
        
        # Clear bike ride data
        try:
            count = BikeRideData.objects.count()
            BikeRideData.objects.all().delete()
            self.stdout.write(f'Cleared BikeRideData table, deleted {count} records')
        except Exception as e:
            self.stdout.write(f'Error clearing BikeRideData table: {e}')
        
        # Clear vehicle data
        try:
            count = Vehicle.objects.count()
            Vehicle.objects.all().delete()
            self.stdout.write(f'Cleared Vehicle table, deleted {count} records')
        except Exception as e:
            self.stdout.write(f'Error clearing Vehicle table: {e}')
        
        # Clear schedule task data
        try:
            count = ScheduleTask.objects.count()
            ScheduleTask.objects.all().delete()
            self.stdout.write(f'Cleared ScheduleTask table, deleted {count} records')
        except Exception as e:
            self.stdout.write(f'Error clearing ScheduleTask table: {e}')
        
        # Clear parking spot data
        try:
            count = ParkingSpot.objects.count()
            ParkingSpot.objects.all().delete()
            self.stdout.write(f'Cleared ParkingSpot table, deleted {count} records')
        except Exception as e:
            self.stdout.write(f'Error clearing ParkingSpot table: {e}')
        
        # Clear prediction result data
        try:
            count = PredictionResult.objects.count()
            PredictionResult.objects.all().delete()
            self.stdout.write(f'Cleared PredictionResult table, deleted {count} records')
        except Exception as e:
            self.stdout.write(f'Error clearing PredictionResult table: {e}')
        
        self.stdout.write('===== Database tables clearing completed =====')
